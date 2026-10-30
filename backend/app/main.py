"""AF-07 Enterprise Workforce Intelligence & Task Allocation API (API gateway + RBAC layer)."""
import os
from typing import Dict

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import engine
from .agents import (CoordinationAgent, PerformanceEvaluationAgent, ProgressMonitoringAgent, ProjectAnalysisAgent,
                     RiskPredictionAgent, TaskAllocationAgent, WorkforceIntelligenceAgent)
from .audit import utcnow
from .auth import assert_self_or_admin, current_user, issue_token, require_admin, verify_password
from .models import (ChatQueryRequest, DecisionRequest, DisputeRequest, DisputeResolveRequest, DisruptionRequest,
                     IntegrationEvent, IntegrationEventRequest, LoginRequest, ProgressUpdateRequest, Project,
                     ProjectCreateRequest, Task, WeightConfig, WhatIfRequest)
from .state import STORE

app = FastAPI(title="AF-07 Enterprise Workforce Intelligence & Task Allocation API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("AF07_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

coordinator = CoordinationAgent()
analyst = ProjectAnalysisAgent()
workforce = WorkforceIntelligenceAgent()
allocator = TaskAllocationAgent()
monitor = ProgressMonitoringAgent()
evaluator = PerformanceEvaluationAgent()
risk = RiskPredictionAgent()


# ------------------------------------------------------------------ auth
@app.get("/api/v1/health")
def health():
    return {"status": "ok", "time": utcnow(), "ledger": STORE.ledger.verify()["valid"]}


@app.post("/api/v1/auth/login")
def login(req: LoginRequest):
    user = STORE.user(req.username)
    if user is None or not verify_password(req.password, user):
        STORE.ledger.record(req.username[:64], "LOGIN_FAILED", "AUTH", {})
        raise HTTPException(401, "Invalid username or password")
    STORE.ledger.record(user.username, "LOGIN_SUCCESS", "AUTH", {"role": user.role})
    return {"token": issue_token(user), "user": {"username": user.username, "display_name": user.display_name,
                                                 "role": user.role, "employee_id": user.employee_id}}


@app.get("/api/v1/auth/me")
def me(user: Dict = Depends(current_user)):
    u = STORE.user(user["sub"])
    return {"username": u.username, "display_name": u.display_name, "role": u.role, "employee_id": u.employee_id}


# ------------------------------------------------------------------ dashboards
def _summary() -> Dict:
    evals = [engine.compute_6_scores(e) for e in STORE.employees]
    return {
        "total_employees": len(evals),
        "total_tasks": len(STORE.tasks),
        "workload_gini_index": engine.team_gini(STORE.employees),
        "overloaded_count": sum(1 for e in evals if e["workload_score"] > engine.HITL_LOAD_THRESHOLD),
        "on_leave_count": sum(1 for e in evals if e["status"] == "On Leave"),
        "team_free_hrs": round(sum(e["free_capacity_hrs"] for e in evals), 1),
        "weights": STORE.weights.model_dump(),
        "employees": evals,
        "tasks": [t.model_dump() for t in STORE.tasks],
        "projects": [p.model_dump() for p in STORE.projects],
        "pending_approvals": [a.model_dump() for a in STORE.approvals if a.status == "PENDING"],
        "decided_approvals": [a.model_dump() for a in STORE.approvals if a.status != "PENDING"][-10:],
        "assignments": [a.model_dump() for a in STORE.assignments],
        "decisions": [d.model_dump() for d in STORE.decisions[:20]],
        "recent_audits": STORE.ledger.latest(25),
        "ledger_status": STORE.ledger.verify(),
    }


@app.get("/api/v1/dashboard/summary")
def dashboard_summary(_: Dict = Depends(require_admin)):
    with STORE.lock:
        return _summary()


@app.get("/api/v1/team/directory")
def team_directory(_: Dict = Depends(current_user)):
    """Minimal, non-sensitive directory (names, roles, status) visible to every signed-in user."""
    return [{"employee_id": e.id, "name": e.name, "designation": e.designation, "department": e.department, "status": e.status}
            for e in STORE.employees]


@app.get("/api/v1/employees/{employee_id}/evaluation")
def employee_evaluation(employee_id: str, user: Dict = Depends(current_user)):
    assert_self_or_admin(user, employee_id)
    return evaluator.evaluate(employee_id)


@app.get("/api/v1/me/portal")
def my_portal(user: Dict = Depends(current_user)):
    if not user.get("emp"):
        raise HTTPException(400, "This account is not linked to an employee profile")
    data = evaluator.evaluate(user["emp"])
    by_id = {t.id: t for t in STORE.tasks}
    for t in data["tasks"]:
        t["dependency_status"] = [{"task_id": d, "status": by_id[d].status if d in by_id else "UNKNOWN"} for d in t["dependencies"]]
        asg = next((a for a in reversed(STORE.assignments) if a.task_id == t["id"] and a.employee_id == user["emp"]), None)
        t["why_me"] = asg.explanation_rationale if asg else None
        t["suitability_score"] = asg.suitability_score if asg else None
    gaps = workforce.skill_gaps()["gaps"]
    data["growth"] = [{"skill": g["skill"], "recommendation": r["recommendation"]} for g in gaps
                      for r in g["training_recommendations"] if r["employee_id"] == user["emp"]]
    return data


# ------------------------------------------------------------------ admin config
@app.post("/api/v1/admin/weights")
def update_weights(w: WeightConfig, user: Dict = Depends(require_admin)):
    with STORE.lock:
        before = STORE.weights.model_dump()
        STORE.weights = w
        STORE.ledger.record(user["sub"], "UPDATED_SCORING_WEIGHTS", "ORG_CONFIG", {"before": before, "after": w.model_dump()})
    return {"status": "UPDATED", "weights": w}


@app.post("/api/v1/reset")
def reset_state(user: Dict = Depends(require_admin)):
    STORE.reset()
    STORE.ledger.record(user["sub"], "DEMO_STATE_RESET", "ORG", {})
    return {"status": "RESET_COMPLETE"}


@app.get("/api/v1/audit")
def audit(limit: int = 100, _: Dict = Depends(require_admin)):
    return {"entries": STORE.ledger.latest(min(limit, 500)), "verification": STORE.ledger.verify()}


# ------------------------------------------------------------------ projects & tasks
@app.post("/api/v1/projects/analyze")
def analyze_project(req: ProjectCreateRequest, _: Dict = Depends(require_admin)):
    drafts, source = analyst.decompose(req.name, req.objective, req.priority, req.deadline_days)
    total = sum(d["estimated_hours"] for d in drafts)
    team_free = sum(engine.net_free_hrs(e) for e in STORE.employees)
    return {"agent": analyst.name, "source": source, "draft_tasks": drafts, "total_effort_hrs": total,
            "team_free_hrs_this_week": round(team_free, 1),
            "feasibility": "OK" if total <= team_free * max(1, req.deadline_days / 7) else "RESOURCE_SHORTAGE"}


@app.post("/api/v1/projects")
def create_project(req: ProjectCreateRequest, user: Dict = Depends(require_admin)):
    """Analyse the brief and persist the approved DAG as a new project (manager approves by creating)."""
    drafts, source = analyst.decompose(req.name, req.objective, req.priority, req.deadline_days)
    with STORE.lock:
        pid = STORE.next_id("PRJ")
        project = Project(id=pid, name=req.name, business_objective=req.objective, priority=req.priority,
                          deadline_days=req.deadline_days, created_by=user["sub"])
        key_to_id = {d["key"]: STORE.next_id("TSK") for d in drafts}
        new_tasks = [Task(id=key_to_id[d["key"]], project_id=pid, title=d["title"], description=d["description"],
                          required_skills=d["required_skills"], estimated_hours=d["estimated_hours"], priority=d["priority"],
                          deadline_days=d["deadline_days"], dependencies=[key_to_id[k] for k in d["depends_on_keys"] if k in key_to_id],
                          deliverable_criteria=d["deliverable_criteria"], status="READY_FOR_ALLOCATION") for d in drafts]
        cycle = engine.detect_cycle(new_tasks)
        if cycle:
            raise HTTPException(422, f"Dependency cycle detected: {' -> '.join(cycle)}")
        STORE.projects.append(project)
        STORE.tasks.extend(new_tasks)
        cp = engine.critical_path(new_tasks)
        STORE.ledger.record(user["sub"], "PROJECT_CREATED_FROM_BRIEF", pid,
                            {"tasks": [t.id for t in new_tasks], "source": source, "critical_path": cp["path"]})
        return {"project": project.model_dump(), "tasks": [t.model_dump() for t in new_tasks], "critical_path": cp, "source": source}


@app.get("/api/v1/projects/{project_id}/dag")
def project_dag(project_id: str, _: Dict = Depends(current_user)):
    tasks = [t for t in STORE.tasks if t.project_id == project_id]
    if not tasks:
        raise HTTPException(404, "Project not found")
    return {"tasks": [t.model_dump() for t in engine.topo_sort(tasks)], "critical_path": engine.critical_path(tasks)}


@app.post("/api/v1/tasks/allocate-all")
def allocate_all(user: Dict = Depends(require_admin)):
    return allocator.allocate_all(user["sub"])


@app.get("/api/v1/tasks/{task_id}/candidates")
def task_candidates(task_id: str, _: Dict = Depends(require_admin)):
    task = STORE.task(task_id)
    return {"task": task.model_dump(), "candidates": engine.rank_candidates(STORE.employees, task, STORE.weights)}


@app.post("/api/v1/simulate/what-if")
def what_if(req: WhatIfRequest, _: Dict = Depends(require_admin)):
    return allocator.what_if(req.task_id, req.employee_id)


@app.post("/api/v1/tasks/{task_id}/progress")
def update_progress(task_id: str, req: ProgressUpdateRequest, user: Dict = Depends(current_user)):
    if not user.get("emp"):
        raise HTTPException(403, "Only the assigned employee can report progress")
    return monitor.update_progress(task_id, user["emp"], req.progress_pct, req.status, user["sub"])


@app.post("/api/v1/tasks/{task_id}/accept")
def accept_deliverable(task_id: str, user: Dict = Depends(require_admin)):
    return monitor.accept_deliverable(task_id, user["sub"])


@app.get("/api/v1/progress")
def progress(_: Dict = Depends(require_admin)):
    return monitor.report()


# ------------------------------------------------------------------ disruption, risk, approvals
@app.post("/api/v1/disruptions/simulate")
def simulate_disruption(req: DisruptionRequest, user: Dict = Depends(require_admin)):
    return risk.disruption(req.employee_id, req.new_status, req.leave_days, req.reason, user["sub"])


@app.get("/api/v1/risks")
def risks(_: Dict = Depends(require_admin)):
    return risk.scan()


@app.get("/api/v1/skills/gaps")
def skill_gaps(_: Dict = Depends(require_admin)):
    return workforce.skill_gaps()


@app.post("/api/v1/approvals/{approval_id}/approve")
def approve(approval_id: str, req: DecisionRequest = DecisionRequest(), user: Dict = Depends(require_admin)):
    return coordinator.decide(approval_id, True, req.comments, user["sub"])


@app.post("/api/v1/approvals/{approval_id}/reject")
def reject(approval_id: str, req: DecisionRequest = DecisionRequest(), user: Dict = Depends(require_admin)):
    return coordinator.decide(approval_id, False, req.comments, user["sub"])


# ------------------------------------------------------------------ disputes
@app.post("/api/v1/employees/dispute")
def file_dispute(req: DisputeRequest, user: Dict = Depends(current_user)):
    emp_id = req.employee_id or user.get("emp")
    if not emp_id:
        raise HTTPException(400, "employee_id required")
    assert_self_or_admin(user, emp_id)
    return evaluator.file_dispute(emp_id, req.reason, user["sub"])


@app.post("/api/v1/employees/{employee_id}/dispute/resolve")
def resolve_dispute(employee_id: str, req: DisputeResolveRequest, user: Dict = Depends(require_admin)):
    return evaluator.resolve_dispute(employee_id, req.resolution, req.note, user["sub"])


# ------------------------------------------------------------------ integrations (evidence adapters)
@app.post("/api/v1/integrations/events")
def ingest_event(req: IntegrationEventRequest, user: Dict = Depends(require_admin)):
    """Authorized GitHub / Jira / Calendar evidence intake. Duplicate deliveries are ignored."""
    key = f"{req.source_system}:{req.external_id}"
    with STORE.lock:
        if key in STORE.processed_event_keys:
            return {"status": "DUPLICATE_IGNORED", "key": key}
        emp = STORE.employee(req.employee_id)
        ev = IntegrationEvent(id=STORE.next_id("INT"), employee_id=emp.id, source_system=req.source_system, external_id=req.external_id,
                              pr_review_score=req.pr_review_score, defect_rate=req.defect_rate, summary=req.summary, received_at=utcnow())
        STORE.integration_events.append(ev)
        STORE.processed_event_keys.add(key)
        before = {"collaboration_review_score": emp.collaboration_review_score, "meeting_hrs": emp.meeting_hrs}
        if req.pr_review_score is not None:   # exponential smoothing so one event can't swing the score
            emp.collaboration_review_score = round(0.8 * emp.collaboration_review_score + 0.2 * req.pr_review_score, 1)
        if req.defect_rate is not None:
            emp.work_quality_acceptance_rate = round(0.9 * emp.work_quality_acceptance_rate + 0.1 * (100 - req.defect_rate), 1)
        if req.meeting_hrs_delta is not None:
            emp.meeting_hrs = max(0.0, emp.meeting_hrs + req.meeting_hrs_delta)
        STORE.ledger.record(f"ADAPTER_{req.source_system.upper()}", "EVIDENCE_INGESTED", emp.id,
                            {"event": ev.id, "key": key, "before": before,
                             "after": {"collaboration_review_score": emp.collaboration_review_score, "meeting_hrs": emp.meeting_hrs}})
        return {"status": "INGESTED", "event": ev.model_dump()}


# ------------------------------------------------------------------ AI coordinator
@app.post("/api/v1/chat/coordinator")
def coordinator_chat(req: ChatQueryRequest, user: Dict = Depends(current_user)):
    return coordinator.chat(req.query, user)
