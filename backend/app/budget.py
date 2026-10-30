"""Project budgets and cost rates. Money is integer minor units, so totals are exact. Estimated, committed and actual costs never mix."""
import hashlib
import json
from typing import Dict, List, Optional

from fastapi import HTTPException

from . import db, optimizer
from .audit import utcnow
from .models import ApprovalRecord, TaskAssignment
from .state import STORE

MAX_MINOR = 10 ** 15
ENTRY_KINDS = ("committed", "actual", "non_labor_estimate")
MIN_HISTORY_FOR_RANGE = 5


def _amount(value: int, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_MINOR:
        raise HTTPException(422, f"{label} must be a whole number of minor currency units between 0 and {MAX_MINOR}")
    return value


def set_budget(project_id: str, body: Dict, actor: str) -> Dict:
    STORE.project(project_id)
    currency = body["currency"].strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise HTTPException(422, "Use a three-letter currency code, for example INR or USD")
    total = _amount(body["total_minor"], "The total budget")
    labor = None if body.get("labor_minor") is None else _amount(body["labor_minor"], "The labor budget")
    reserve = _amount(body.get("reserve_minor") or 0, "The reserve")
    non_labor = _amount(body.get("non_labor_minor") or 0, "The non-labor estimate")
    if reserve + non_labor + (labor or 0) > total:
        raise HTTPException(422, "Labor, non-labor and reserve add up to more than the total budget")
    with db.tx() as c:
        c.execute("INSERT INTO project_budgets (project_id, org_id, currency, total_minor, labor_minor, non_labor_minor, reserve_minor, includes_tax, hard_limit, updated_by, updated_at) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET currency = excluded.currency, total_minor = excluded.total_minor, labor_minor = excluded.labor_minor, "
                  "non_labor_minor = excluded.non_labor_minor, reserve_minor = excluded.reserve_minor, includes_tax = excluded.includes_tax, hard_limit = excluded.hard_limit, "
                  "updated_by = excluded.updated_by, updated_at = excluded.updated_at",
                  (project_id, db.org(), currency, total, labor, non_labor, reserve, int(bool(body.get("includes_tax"))), int(bool(body.get("hard_limit"))), actor, utcnow()))
    with STORE.lock:
        STORE.ledger.record(actor, "BUDGET_SET", project_id, {"currency": currency, "total_minor": total})
    return report(project_id)


def add_rate(body: Dict, actor: str) -> Dict:
    if not (body.get("employee_id") or body.get("role_name")):
        raise HTTPException(422, "A rate applies to an employee or a role")
    if body.get("employee_id"):
        STORE.employee(body["employee_id"])
    if body.get("project_id"):
        STORE.project(body["project_id"])
    rate_id = db.new_id("RATE")
    with db.tx() as c:
        c.execute("INSERT INTO cost_rates (id, org_id, employee_id, role_name, project_id, currency, hourly_minor, approved_by, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                  (rate_id, db.org(), body.get("employee_id"), body.get("role_name"), body.get("project_id"), body["currency"].strip().upper(), _amount(body["hourly_minor"], "The hourly rate"), actor, utcnow()))
    with STORE.lock:
        STORE.ledger.record(actor, "COST_RATE_ADDED", body.get("employee_id") or body.get("role_name"), {"rate": rate_id})     # the amount stays out of the audit trail
    return {"id": rate_id}


def list_rates() -> List[Dict]:
    return db.rows("SELECT * FROM cost_rates WHERE org_id = ? ORDER BY created_at DESC, id", (db.org(),))


def rate_map(project_id: str, currency: Optional[str]) -> Dict[str, int]:
    """Most specific approved rate per employee: project and person, then person, then role. Stays on the server; responses show only totals."""
    rows = db.rows("SELECT * FROM cost_rates WHERE org_id = ? ORDER BY created_at, id", (db.org(),))
    if currency:
        rows = [r for r in rows if r["currency"] == currency]
    rates: Dict[str, int] = {}
    for emp in STORE.employees:
        for test in (lambda r: r["employee_id"] == emp.id and r["project_id"] == project_id, lambda r: r["employee_id"] == emp.id and not r["project_id"],
                     lambda r: r["role_name"] == emp.designation and r["project_id"] == project_id, lambda r: r["role_name"] == emp.designation and not r["project_id"]):
            found = [r for r in rows if test(r)]
            if found:
                rates[emp.id] = found[-1]["hourly_minor"]
                break
    return rates


def add_entry(project_id: str, body: Dict, actor: str) -> Dict:
    STORE.project(project_id)
    if body["kind"] not in ENTRY_KINDS:
        raise HTTPException(422, f"Cost type must be one of {', '.join(ENTRY_KINDS)}")
    if body.get("task_id"):
        task = STORE.task(body["task_id"])
        if task.project_id != project_id:
            raise HTTPException(422, "That task belongs to a different project")
    budget = db.one("SELECT currency FROM project_budgets WHERE project_id = ? AND org_id = ?", (project_id, db.org()))
    if not budget:
        raise HTTPException(409, "Set the project budget first")
    with db.tx() as c:
        c.execute("INSERT INTO cost_entries (id, org_id, project_id, task_id, kind, amount_minor, currency, note, hours, created_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (db.new_id("CST"), db.org(), project_id, body.get("task_id"), body["kind"], _amount(body["amount_minor"], "The amount"), budget["currency"], body.get("note"), body.get("hours"), actor, utcnow()))
    with STORE.lock:
        STORE.ledger.record(actor, "COST_RECORDED", project_id, {"kind": body["kind"], "amount_minor": body["amount_minor"]})
    return report(project_id)


def report(project_id: str) -> Dict:
    project = STORE.project(project_id)
    budget = db.one("SELECT * FROM project_budgets WHERE project_id = ? AND org_id = ?", (project_id, db.org()))
    entries = db.rows("SELECT task_id, kind, amount_minor, hours FROM cost_entries WHERE project_id = ? AND org_id = ?", (project_id, db.org()))
    actual = sum(e["amount_minor"] for e in entries if e["kind"] == "actual")
    committed = sum(e["amount_minor"] for e in entries if e["kind"] == "committed")
    non_labor = sum(e["amount_minor"] for e in entries if e["kind"] == "non_labor_estimate") + (budget["non_labor_minor"] if budget else 0)
    rates = rate_map(project_id, budget["currency"] if budget else None)
    tasks = [t for t in STORE.tasks if t.project_id == project_id]
    planned, missing = 0, []
    for t in tasks:
        if t.assigned_to:
            if t.assigned_to in rates:
                planned += optimizer.labor_cost(t.estimated_hours, rates[t.assigned_to])
            else:
                missing.append(t.id)
    unassigned = [t.id for t in tasks if not t.assigned_to]
    estimate = planned + non_labor
    out: Dict = {"project_id": project.id, "has_budget": bool(budget), "currency": budget["currency"] if budget else None, "estimated_labor_minor": planned, "estimated_non_labor_minor": non_labor,
                 "committed_minor": committed, "actual_minor": actual, "tasks_without_rate": missing, "tasks_without_owner": unassigned,
                 "assumptions": ["Estimated labor is each assigned task's estimated hours times its owner's approved rate.", "Tasks without an owner or a rate are not in the estimate, so it can only be a lower bound while they exist."]}
    # A range needs evidence: only past estimate-versus-actual pairs on this project's completed work, and enough of them.
    pairs = [(t.estimated_hours, sum(e["hours"] or 0 for e in entries if e["task_id"] == t.id and e["kind"] == "actual")) for t in tasks]
    pairs = [(est, act) for est, act in pairs if act > 0 and est > 0]
    if len(pairs) >= MIN_HISTORY_FOR_RANGE:
        ratios = sorted(act / est for est, act in pairs)
        out["scenarios"] = {"basis": f"{len(pairs)} tasks with recorded actual hours", "optimistic_minor": round(planned * ratios[0]), "expected_minor": round(planned * ratios[len(ratios) // 2]), "conservative_minor": round(planned * ratios[-1])}
    else:
        out["scenarios"] = None
        out["assumptions"].append(f"No optimistic or conservative range is shown: that needs actual hours on at least {MIN_HISTORY_FOR_RANGE} tasks, and there are {len(pairs)}.")
    if budget:
        spent_or_held = actual + committed
        forecast = spent_or_held + max(0, estimate - spent_or_held)
        status = "over_budget" if forecast > budget["total_minor"] else "at_risk" if forecast > budget["total_minor"] - budget["reserve_minor"] else "within_budget"
        out.update(total_minor=budget["total_minor"], labor_budget_minor=budget["labor_minor"], reserve_minor=budget["reserve_minor"], includes_tax=bool(budget["includes_tax"]), hard_limit=bool(budget["hard_limit"]),
                   remaining_minor=budget["total_minor"] - spent_or_held, forecast_at_completion_minor=forecast, variance_minor=budget["total_minor"] - forecast, status=status)
    return out


def _policy() -> Dict:
    return {}


def propose(project_id: str, policy: Optional[Dict] = None) -> Dict:
    """Runs the optimizer and changes nothing. The proposal id ties a later approval to exactly this plan and these inputs."""
    STORE.project(project_id)
    budget = db.one("SELECT * FROM project_budgets WHERE project_id = ? AND org_id = ?", (project_id, db.org()))
    tasks = [t for t in STORE.tasks if t.project_id == project_id and not t.assigned_to and t.status in ("READY_FOR_ALLOCATION", "BLOCKED_BY_DEPENDENCY", "DRAFT_GENERATED")]
    rates = rate_map(project_id, budget["currency"] if budget else None)
    result = optimizer.optimize(tasks, STORE.employees, rates, STORE.tasks, budget["total_minor"] - budget["reserve_minor"] if budget else None, bool(budget["hard_limit"]) if budget else False, policy)
    result["currency"] = budget["currency"] if budget else None
    result["proposal_id"] = hashlib.sha256(json.dumps(sorted((a["task_id"], a["employee_id"]) for a in result["assignments"])).encode()).hexdigest()[:16]
    return result


def apply(project_id: str, proposal_id: str, actor: str, policy: Optional[Dict] = None) -> Dict:
    """Turns a proposal into approval requests. Nobody is committed to work until a manager approves each one."""
    proposal = propose(project_id, policy)
    if proposal["proposal_id"] != proposal_id or not proposal["assignments"]:
        raise HTTPException(409, "The team, tasks or rates changed since this plan was made. Review the new plan.")
    created = []
    with STORE.lock:
        for a in proposal["assignments"]:
            task, emp = STORE.task(a["task_id"]), STORE.employee(a["employee_id"])
            if task.assigned_to:
                continue
            emp.committed_hrs += task.estimated_hours
            task.assigned_to, task.status = emp.id, "PENDING_HITL_APPROVAL"
            impact = f" Estimated cost {a['estimated_cost_minor']} minor units." if a["estimated_cost_minor"] is not None else ""
            STORE.assignments.append(TaskAssignment(id=STORE.next_id("ASG"), task_id=task.id, employee_id=emp.id, suitability_score=a["suitability"]["score"],
                                                    factor_breakdown={"skill_match": a["suitability"]["skill"], "past_performance": a["suitability"]["record"]},
                                                    explanation_rationale=a["rationale"], tradeoffs_flagged=a["risks"], status="PENDING_HITL_APPROVAL"))
            approval = ApprovalRecord(approval_id=STORE.next_id("APR"), decision_id=f"OPT-{proposal_id}", kind="INITIAL_ALLOCATION", task_id=task.id, task_title=task.title, priority=task.priority,
                                      previous_owner=None, previous_owner_id=None, recommended_new_owner_id=emp.id, recommended_new_owner_name=emp.name, suitability_score=a["suitability"]["score"],
                                      post_utilization_pct=proposal["peak_utilization_pct"].get(emp.id, 0.0), explanation=f"Budget-aware plan {proposal_id}. {a['rationale']}{impact}", created_at=utcnow())
            STORE.approvals.append(approval)
            created.append(approval.approval_id)
        STORE.ledger.record(actor, "OPTIMIZED_PLAN_SUBMITTED", project_id, {"proposal": proposal_id, "approvals": created, "solver": proposal["solver"]["status"]})
    if created:
        db.notify("approval", f"{len(created)} assignment(s) need approval", "A budget-aware team plan is waiting for review.", audience_role="ADMIN", link_view="manager")
    return {"status": "SUBMITTED_FOR_APPROVAL", "approvals": created, "proposal_id": proposal_id}
