"""AF-07 Enterprise Workforce Intelligence & Task Allocation API (API gateway + RBAC layer)."""
import csv
from datetime import date
import io
import os
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from . import assistant, db, documents, engine, llm, progress as progress_mod, services, skillreview, workflow, workforce as workforce_mod
from .agents import (CoordinationAgent, PerformanceEvaluationAgent, ProgressMonitoringAgent, ProjectAnalysisAgent,
                     RiskPredictionAgent, TaskAllocationAgent, WorkforceIntelligenceAgent)
from .audit import utcnow
from .org import session_user
from .ratelimit import _rate_windows, rate_check, rate_limit
from .routes_company import router as company_router
from .auth import assert_self_or_admin, check_config, current_user, decode_token, issue_token, organization_from, require_admin, verify_password
from .models import (ConversationUpdateRequest, DecisionRequest, DisputeRequest, DisputeResolveRequest, DisruptionRequest,
                     AssistantChatRequest, ChallengeResolveRequest, ChangeRequestCreate, ChangeRequestResolve, ClarificationAnswer,
                     EmployeeCreateRequest, EmployeeUpdateRequest, IntegrationEvent, IntegrationEventRequest, LoginRequest,
                     ProfessionalLinkRequest, ProfileUpdateRequest, ProgressReportRequest, ProgressUpdateRequest, Project, ProjectCreateRequest,
                     ProjectDraftRequest, ProjectUpdateRequest, ResetRequest, ReworkRequest, SkillChallengeRequest, SpecUpdateRequest, Task, TaskAssignRequest,
                     TaskCreateRequest, TaskUpdateRequest, WeightConfig, WhatIfRequest)
from .state import STORE

check_config()
_api_docs = {} if db.environment() == "development" else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="AF-07 Enterprise Workforce Intelligence & Task Allocation API", version="1.0.0", **_api_docs)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("AF07_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

def _actor_of(request: Request) -> str:
    try:
        return decode_token(request.headers.get("authorization", "").split(" ", 1)[1])["sub"]
    except (IndexError, HTTPException):
        return "SYSTEM"


@app.middleware("http")
async def persist_after_mutation(request: Request, call_next):
    response = await call_next(request)
    if request.method not in ("GET", "HEAD", "OPTIONS") and db.org():
        changed = STORE.save()     # write-through snapshot of core entities
        if changed or "/projects/" in request.url.path:     # specs, plans and documents move a project's stage without touching the snapshot
            progress_mod.snapshot_all()
            if response.status_code < 400:
                progress_mod.record_transitions(_actor_of(request))
    return response


@app.middleware("http")
async def idempotent_retries(request: Request, call_next):
    """A POST sent with an Idempotency-Key gives the first answer again on retry instead of repeating its effects."""
    key = request.headers.get("idempotency-key", "")[:128]
    if request.method != "POST" or not key or not db.org():
        return await call_next(request)
    path = request.url.path
    seen = db.one("SELECT status, body FROM idempotency_keys WHERE org_id = ? AND key = ? AND path = ?", (db.org(), key, path))
    if seen:
        return Response(seen["body"], status_code=seen["status"], media_type="application/json", headers={"Idempotent-Replay": "true"})
    response = await call_next(request)
    body = b"".join([chunk async for chunk in response.body_iterator])
    if response.status_code < 500:      # a server failure is safe to retry for real
        with db.tx() as c:
            c.execute("INSERT INTO idempotency_keys (org_id, key, path, status, body, created_at) VALUES (?,?,?,?,?,?) ON CONFLICT(org_id, key, path) DO NOTHING",
                      (db.org(), key, path, response.status_code, body.decode("utf-8", "replace"), utcnow()))
    return Response(body, status_code=response.status_code, headers=dict(response.headers))


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if request.url.path.startswith("/api/"):     # the /docs page loads its assets from a CDN
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def organization_context(request: Request, call_next):
    """Registered last so it runs first: everything below sees only this token's organization."""
    handle = db.set_org(organization_from(request.headers.get("authorization")))
    try:
        return await call_next(request)
    finally:
        db.reset_org(handle)


app.include_router(company_router)    # first, so /projects/overview wins over /projects/{project_id}

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
    return {"status": "ok", "time": utcnow()}


@app.post("/api/v1/auth/login")
def login(req: LoginRequest, request: Request):
    # Checked before the password, so a locked-out guess cannot succeed. Only failures count.
    user_key = f"login-user:{req.username.lower().strip()[:64]}"
    ip_key = f"login-ip:{request.client.host if request.client else 'unknown'}"
    rate_check(user_key, 10, 300)
    rate_check(ip_key, 30, 300)
    org_id = db.account_org(req.username)
    if org_id is None:      # no audit row: an unknown name belongs to no company's ledger
        rate_limit(user_key, 10, 300)
        rate_limit(ip_key, 30, 300)
        raise HTTPException(401, "Invalid username or password")
    with db.as_org(org_id):
        user = STORE.user(req.username)
        if user is None or not verify_password(req.password, user):
            rate_limit(user_key, 10, 300)
            rate_limit(ip_key, 30, 300)
            STORE.ledger.record(req.username[:64], "LOGIN_FAILED", "AUTH", {})
            STORE.save()
            raise HTTPException(401, "Invalid username or password")
        _rate_windows.pop(user_key, None)
        STORE.ledger.record(user.username, "LOGIN_SUCCESS", "AUTH", {"role": user.role})
        STORE.save()
        return {"token": issue_token(user), "user": session_user(user)}


@app.get("/api/v1/auth/me")
def me(user: Dict = Depends(current_user)):
    return session_user(STORE.user(user["sub"]))


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
        "change_requests": services.list_change_requests(),
        "pending_skill_requests": skillreview.pending_count(),
        "weights_updated_at": next((e.timestamp for e in reversed(STORE.ledger.all()) if e.action == "UPDATED_SCORING_WEIGHTS"), None),
        "ai": llm.status(),
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
    data["projects"] = [progress_mod.project_progress(p.id) for p in progress_mod.visible_projects(user)]
    data["change_requests"] = services.list_change_requests(user["emp"])
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
def reset_state(_: ResetRequest, user: Dict = Depends(require_admin)):
    try:
        db.require_development("Resetting to seed data")
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    if db.org() != db.DEFAULT_ORG:
        raise HTTPException(403, "Only the demo organization can be reset")
    saved = db.backup("pre-reset").name
    STORE.reset()
    STORE.ledger.record(user["sub"], "DEMO_STATE_RESET", "ORG", {"backup": saved})
    return {"status": "RESET_COMPLETE", "backup": saved}


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
                          deadline_days=req.deadline_days, created_by=user["sub"], start_date=date.today().isoformat())
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
def project_dag(project_id: str, user: Dict = Depends(current_user)):
    progress_mod.assert_project_access(user, project_id)
    tasks = [t for t in STORE.tasks if t.project_id == project_id]
    if not tasks:
        raise HTTPException(404, "Project not found")
    return {"tasks": [t.model_dump() for t in engine.topo_sort(tasks)], "critical_path": engine.critical_path(tasks)}


@app.post("/api/v1/tasks/allocate-all")
def allocate_all(project_id: Optional[str] = None, user: Dict = Depends(require_admin)):
    return services.run_allocation(user["sub"], project_id)


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
def accept_deliverable(task_id: str, user: Dict = Depends(current_user)):
    progress_mod.assert_can_manage(user, STORE.task(task_id).project_id)
    return monitor.accept_deliverable(task_id, user["sub"])


@app.get("/api/v1/progress")
def progress(_: Dict = Depends(require_admin)):
    return monitor.report()


# ------------------------------------------------------------------ disruption, risk, approvals
@app.post("/api/v1/disruptions/simulate")
def simulate_disruption(req: DisruptionRequest, user: Dict = Depends(require_admin)):
    result = risk.disruption(req.employee_id, req.new_status, req.leave_days, req.reason, user["sub"])
    if result["proposals_created"]:
        db.notify("approval", f"{result['disrupted_employee']}: {req.new_status}", f"{len(result['proposals_created'])} reallocation proposal(s) need approval.", audience_role="ADMIN", link_view="manager")
    return result


@app.get("/api/v1/risks")
def risks(_: Dict = Depends(require_admin)):
    return risk.scan()


@app.get("/api/v1/skills/gaps")
def skill_gaps(_: Dict = Depends(require_admin)):
    return workforce.skill_gaps()


def _assert_can_decide(user: Dict, approval_id: str) -> None:
    if user["role"] == "ADMIN":
        return
    approval = next((a for a in STORE.approvals if a.approval_id == approval_id), None)
    if approval is None:
        raise HTTPException(403, "Enterprise Admin / Project Manager role required")
    progress_mod.assert_can_manage(user, STORE.task(approval.task_id).project_id)


@app.post("/api/v1/approvals/{approval_id}/approve")
def approve(approval_id: str, req: DecisionRequest = DecisionRequest(), user: Dict = Depends(current_user)):
    _assert_can_decide(user, approval_id)
    result = coordinator.decide(approval_id, True, req.comments, user["sub"])
    services.decide_approval_notifications(result)
    return result


@app.post("/api/v1/approvals/{approval_id}/reject")
def reject(approval_id: str, req: DecisionRequest = DecisionRequest(), user: Dict = Depends(current_user)):
    _assert_can_decide(user, approval_id)
    return coordinator.decide(approval_id, False, req.comments, user["sub"])


# ------------------------------------------------------------------ disputes
@app.post("/api/v1/employees/dispute")
def file_dispute(req: DisputeRequest, user: Dict = Depends(current_user)):
    emp_id = req.employee_id or user.get("emp")
    if not emp_id:
        raise HTTPException(400, "employee_id required")
    assert_self_or_admin(user, emp_id)
    result = evaluator.file_dispute(emp_id, req.reason, user["sub"])
    db.notify("dispute", "Evidence dispute filed", f"{STORE.employee(emp_id).name}: {req.reason[:140]}", audience_role="ADMIN", link_view="employee", link_id=emp_id)
    return result


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


# ------------------------------------------------------------------ system & notifications
@app.get("/api/v1/system/status")
def system_status(_: Dict = Depends(require_admin)):
    usage = db.one("SELECT COUNT(*) AS calls, COALESCE(SUM(input_tokens), 0) AS input_tokens, COALESCE(SUM(output_tokens), 0) AS output_tokens, COALESCE(SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END), 0) AS failures FROM ai_usage WHERE org_id = ?", (db.org(),))
    return {"ai": llm.status(), "ai_usage": usage, "retrieval": f"{'Postgres full-text search' if db.DB_URL else 'SQLite FTS5 (BM25)'}, scoped per project; no embeddings",
            "database": db.database_label(), "ledger": STORE.ledger.verify(), "github_token": False,
            "oauth": {"linkedin": False, "instagram": False, "x": False}, "upload_limit_mb": documents.MAX_BYTES // (1024 * 1024)}


@app.get("/api/v1/notifications")
def notifications(user: Dict = Depends(current_user)):
    return db.rows("SELECT * FROM notifications WHERE org_id = ? AND (audience_user = ? OR audience_role = ?) ORDER BY created_at DESC, rowid DESC LIMIT 40", (db.org(), user["sub"], user["role"]))


@app.post("/api/v1/notifications/read-all")
def notifications_read_all(user: Dict = Depends(current_user)):
    with db.tx() as c:
        c.execute("UPDATE notifications SET is_read = 1 WHERE org_id = ? AND (audience_user = ? OR audience_role = ?)", (db.org(), user["sub"], user["role"]))
    return {"status": "OK"}


@app.post("/api/v1/notifications/{notification_id}/read")
def notification_read(notification_id: str, user: Dict = Depends(current_user)):
    with db.tx() as c:
        c.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND org_id = ? AND (audience_user = ? OR audience_role = ?)", (notification_id, db.org(), user["sub"], user["role"]))
    return {"status": "OK"}


# ------------------------------------------------------------------ projects workspace
@app.get("/api/v1/projects")
def list_projects(user: Dict = Depends(current_user)):
    return [progress_mod.project_progress(p.id) | {"objective": p.business_objective} for p in progress_mod.visible_projects(user)]


@app.post("/api/v1/projects/draft")
def create_draft_project(req: ProjectDraftRequest, user: Dict = Depends(require_admin)):
    return services.create_draft_project(req.name, req.objective, req.priority, req.deadline_days, user["sub"])


@app.get("/api/v1/projects/{project_id}")
def project_detail(project_id: str, user: Dict = Depends(current_user)):
    progress_mod.assert_project_access(user, project_id)
    project = STORE.project(project_id)
    tasks = [t for t in STORE.tasks if t.project_id == project_id]
    return {"project": project.model_dump(), "progress": progress_mod.project_progress(project_id), "tasks": [t.model_dump() for t in tasks],
            "critical_path": engine.critical_path(tasks) if tasks else {"path": [], "total_hours": 0}}


@app.patch("/api/v1/projects/{project_id}")
def update_project(project_id: str, req: ProjectUpdateRequest, user: Dict = Depends(require_admin)):
    return services.update_project(project_id, req.model_dump(exclude_none=True), user["sub"])


@app.post("/api/v1/projects/{project_id}/progress-report")
def report_progress(project_id: str, req: ProgressReportRequest, user: Dict = Depends(current_user)):
    progress_mod.assert_can_manage(user, project_id)
    return progress_mod.report_progress(project_id, req.reported_pct, req.note, user["sub"])


@app.get("/api/v1/projects/{project_id}/evaluation")
def evaluate_project(project_id: str, user: Dict = Depends(current_user)):
    progress_mod.assert_project_access(user, project_id)
    return progress_mod.evaluate_project(project_id)


@app.get("/api/v1/projects/{project_id}/export.csv")
def export_project(project_id: str, user: Dict = Depends(current_user)):
    progress_mod.assert_project_access(user, project_id)
    return _csv(f"{project_id}-tasks.csv", ["id", "title", "phase", "milestone", "priority", "status", "owner", "estimated_hours", "deadline_day", "reported_pct", "dependencies"],
                [[t.id, t.title, t.phase, t.milestone, t.priority, t.status, (STORE.find_employee(t.assigned_to).name if t.assigned_to else ""), t.estimated_hours,
                  t.deadline_days, t.progress_pct, " ".join(t.dependencies)] for t in STORE.tasks if t.project_id == project_id])


def _csv(filename: str, header: List[str], rows: List[List]) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    # Prefix values a spreadsheet would run as formulas.
    writer.writerows([[f"'{v}" if isinstance(v, str) and v[:1] in "=+-@" else v for v in row] for row in rows])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/api/v1/audit/export.csv")
def export_audit(_: Dict = Depends(require_admin)):
    return _csv("audit-ledger.csv", ["id", "timestamp", "actor", "action", "entity", "sha256"],
                [[e.id, e.timestamp, e.actor, e.action, e.entity_id, e.sha256_proof] for e in STORE.ledger.all()])


@app.get("/api/v1/employees/export.csv")
def export_employees(_: Dict = Depends(require_admin)):
    rows = [engine.compute_6_scores(e) for e in STORE.employees]
    return _csv("employees.csv", ["id", "name", "department", "designation", "status", "skill_score", "performance_score", "availability_score", "workload_score", "collaboration_score", "level"],
                [[r["employee_id"], r["name"], r["department"], r["designation"], r["status"], r["skill_score"], r["performance_score"], r["availability_score"], r["workload_score"], r["collaboration_score"], r["level"]] for r in rows])


# ------------------------------------------------------------------ documents
@app.get("/api/v1/projects/{project_id}/documents")
def list_documents(project_id: str, user: Dict = Depends(current_user)):
    progress_mod.assert_project_access(user, project_id)
    return documents.list_documents(project_id)


@app.post("/api/v1/projects/{project_id}/documents")
async def upload_documents(project_id: str, background: BackgroundTasks, files: List[UploadFile] = File(...), user: Dict = Depends(require_admin)):
    STORE.project(project_id)
    rate_limit(f"upload:{user['sub']}", 40, 60)
    results = []
    for f in files[:20]:
        data = await f.read(documents.MAX_BYTES + 1)
        try:
            doc = documents.store_upload(project_id, f.filename or "", data, user["sub"])
        except ValueError as exc:
            results.append({"filename": f.filename, "status": "rejected", "error": str(exc)})
            continue
        if doc.get("duplicate"):
            results.append({"filename": f.filename, "status": "duplicate", "document_id": doc["id"], "error": f"Identical to {doc['filename']} v{doc['version']}; not added again."})
            continue
        background.add_task(documents.process, doc["id"])
        results.append({"filename": doc["filename"], "status": "uploaded", "document_id": doc["id"], "version": doc["version"]})
    STORE.ledger.record(user["sub"], "DOCUMENTS_UPLOADED", project_id, {"files": [{"name": r["filename"], "status": r["status"]} for r in results]})
    return {"results": results}


@app.get("/api/v1/projects/{project_id}/documents/{document_id}/preview")
def document_preview(project_id: str, document_id: str, user: Dict = Depends(current_user)):
    progress_mod.assert_project_access(user, project_id)
    return documents.preview(project_id, document_id)


@app.delete("/api/v1/projects/{project_id}/documents/{document_id}")
def delete_document(project_id: str, document_id: str, user: Dict = Depends(require_admin)):
    doc = documents.get_document(project_id, document_id)
    documents.delete_document(project_id, document_id)
    STORE.ledger.record(user["sub"], "DOCUMENT_DELETED", project_id, {"filename": doc["filename"], "version": doc["version"]})
    return {"status": "DELETED"}


@app.post("/api/v1/projects/{project_id}/documents/{document_id}/reindex")
def reindex_document(project_id: str, document_id: str, background: BackgroundTasks, _: Dict = Depends(require_admin)):
    documents.get_document(project_id, document_id)
    background.add_task(documents.process, document_id)
    return {"status": "QUEUED"}


@app.get("/api/v1/projects/{project_id}/documents-search")
def search_documents(project_id: str, q: str, user: Dict = Depends(current_user)):
    progress_mod.assert_project_access(user, project_id)
    return documents.search(project_id, q[:400])


# ------------------------------------------------------------------ specification & plan
@app.post("/api/v1/projects/{project_id}/analyze")
def analyze_documents(project_id: str, user: Dict = Depends(require_admin)):
    return workflow.analyze(project_id, user["sub"])


@app.get("/api/v1/projects/{project_id}/spec")
def get_spec(project_id: str, _: Dict = Depends(require_admin)):
    return workflow.get_spec(project_id)


@app.patch("/api/v1/projects/{project_id}/spec")
def update_spec(project_id: str, req: SpecUpdateRequest, _: Dict = Depends(require_admin)):
    return workflow.update_spec(project_id, req.summary, req.notes)


@app.post("/api/v1/projects/{project_id}/spec/approve")
def approve_spec(project_id: str, user: Dict = Depends(require_admin)):
    return workflow.approve_spec(project_id, user["sub"])


@app.post("/api/v1/projects/{project_id}/clarifications/{clarification_id}")
def answer_clarification(project_id: str, clarification_id: str, req: ClarificationAnswer, user: Dict = Depends(require_admin)):
    return workflow.answer_clarification(project_id, clarification_id, req.answer, user["sub"])


@app.get("/api/v1/projects/{project_id}/plan")
def get_plan(project_id: str, _: Dict = Depends(require_admin)):
    return workflow.get_plan(project_id) or {"plan": None}


@app.post("/api/v1/projects/{project_id}/plan/generate")
def generate_plan(project_id: str, force: bool = False, user: Dict = Depends(require_admin)):
    return workflow.generate_plan(project_id, user["sub"], force)


@app.put("/api/v1/projects/{project_id}/plan/{plan_id}")
def update_plan(project_id: str, plan_id: str, body: Dict, _: Dict = Depends(require_admin)):
    return workflow.update_plan(project_id, plan_id, body)


@app.post("/api/v1/projects/{project_id}/plan/{plan_id}/approve")
def approve_plan(project_id: str, plan_id: str, user: Dict = Depends(require_admin)):
    return workflow.approve_plan(project_id, plan_id, user["sub"])


# ------------------------------------------------------------------ tasks
@app.post("/api/v1/projects/{project_id}/tasks")
def create_task(project_id: str, req: TaskCreateRequest, user: Dict = Depends(require_admin)):
    return services.create_task(project_id, req.model_dump(), user["sub"])


@app.patch("/api/v1/tasks/{task_id}")
def update_task(task_id: str, req: TaskUpdateRequest, user: Dict = Depends(require_admin)):
    return services.update_task(task_id, req.model_dump(exclude_none=True), user["sub"])


@app.delete("/api/v1/tasks/{task_id}")
def delete_task(task_id: str, user: Dict = Depends(require_admin)):
    return services.delete_task(task_id, user["sub"])


@app.post("/api/v1/tasks/{task_id}/assign")
def assign_task(task_id: str, req: TaskAssignRequest, user: Dict = Depends(require_admin)):
    return services.assign_task(task_id, req.employee_id, req.reason, user["sub"])


@app.post("/api/v1/tasks/{task_id}/rework")
def request_rework(task_id: str, req: ReworkRequest, user: Dict = Depends(current_user)):
    progress_mod.assert_can_manage(user, STORE.task(task_id).project_id)
    return services.request_rework(task_id, req.reason, user["sub"])


# ------------------------------------------------------------------ employees
@app.post("/api/v1/employees")
def create_employee(req: EmployeeCreateRequest, user: Dict = Depends(require_admin)):
    return services.create_employee(req.model_dump(), user["sub"])


@app.patch("/api/v1/employees/{employee_id}")
def update_employee(employee_id: str, req: EmployeeUpdateRequest, user: Dict = Depends(require_admin)):
    return services.update_employee(employee_id, req.model_dump(exclude_none=True), user["sub"])


@app.delete("/api/v1/employees/{employee_id}")
def deactivate_employee(employee_id: str, user: Dict = Depends(require_admin)):
    return services.deactivate_employee(employee_id, user["sub"])


@app.get("/api/v1/employees/{employee_id}/intelligence")
def employee_intelligence(employee_id: str, user: Dict = Depends(current_user)):
    assert_self_or_admin(user, employee_id)
    return {"employee": engine.compute_6_scores(STORE.employee(employee_id)), "profile": workforce_mod.get_profile(employee_id), "skills": workforce_mod.get_skills(employee_id),
            "resume": workforce_mod.get_resume(employee_id), "links": workforce_mod.list_links(employee_id), "challenges": workforce_mod.list_challenges(employee_id),
            "completed": [t.model_dump() for t in STORE.tasks if t.assigned_to == employee_id and t.status == "COMPLETED_AND_AUDITED"]}


@app.put("/api/v1/employees/{employee_id}/profile")
def save_profile(employee_id: str, req: ProfileUpdateRequest, user: Dict = Depends(current_user)):
    assert_self_or_admin(user, employee_id)
    return workforce_mod.save_profile(employee_id, req.model_dump(), user["sub"])


@app.post("/api/v1/employees/{employee_id}/skills/evaluate")
def evaluate_skills(employee_id: str, user: Dict = Depends(require_admin)):
    return workforce_mod.evaluate_skills(employee_id, user["sub"])


@app.post("/api/v1/employees/{employee_id}/skills/challenge")
def challenge_skill(employee_id: str, req: SkillChallengeRequest, user: Dict = Depends(current_user)):
    assert_self_or_admin(user, employee_id)
    return workforce_mod.challenge_skill(employee_id, req.skill, req.reason, user["sub"])


@app.post("/api/v1/skill-challenges/{challenge_id}/resolve")
def resolve_challenge(challenge_id: str, req: ChallengeResolveRequest, user: Dict = Depends(require_admin)):
    return workforce_mod.resolve_challenge(challenge_id, req.resolution, req.note, user["sub"])


@app.post("/api/v1/employees/{employee_id}/resume")
async def upload_resume(employee_id: str, file: UploadFile = File(...), target_text: Optional[str] = Form(None), task_id: Optional[str] = Form(None), user: Dict = Depends(current_user)):
    assert_self_or_admin(user, employee_id)
    rate_limit(f"resume:{user['sub']}", 10, 60)
    label = "Job description provided" if target_text else None
    if task_id:
        task = STORE.task(task_id)
        target_text, label = " ".join(task.required_skills), f"{task.id}: {task.title}"
    return workforce_mod.upload_resume(employee_id, file.filename or "", await file.read(documents.MAX_BYTES + 1), target_text, label, user["sub"])


@app.post("/api/v1/employees/{employee_id}/links")
def save_link(employee_id: str, req: ProfessionalLinkRequest, user: Dict = Depends(current_user)):
    if user.get("emp") != employee_id:     # consent: only the employee can link their own accounts
        raise HTTPException(403, "Only the employee can connect their own accounts")
    return workforce_mod.save_link(employee_id, req.provider, req.value, user["sub"])


@app.delete("/api/v1/employees/{employee_id}/links/{provider}")
def remove_link(employee_id: str, provider: str, user: Dict = Depends(current_user)):
    if user.get("emp") != employee_id:
        raise HTTPException(403, "Only the employee can disconnect their own accounts")
    return workforce_mod.remove_link(employee_id, provider, user["sub"])


# ------------------------------------------------------------------ change requests
@app.post("/api/v1/change-requests")
def create_change_request(req: ChangeRequestCreate, user: Dict = Depends(current_user)):
    if not user.get("emp"):
        raise HTTPException(400, "This account has no employee profile")
    return services.create_change_request(user["emp"], req.kind, req.task_id, req.details, user["sub"])


@app.post("/api/v1/change-requests/{request_id}/resolve")
def resolve_change_request(request_id: str, req: ChangeRequestResolve, user: Dict = Depends(require_admin)):
    return services.resolve_change_request(request_id, req.approve, req.note, req.new_deadline_days, req.leave_days, user["sub"])


# ------------------------------------------------------------------ assistant
@app.post("/api/v1/assistant/chat")
def assistant_chat(req: AssistantChatRequest, user: Dict = Depends(current_user)):
    rate_limit(f"chat:{user['sub']}", 30, 60)
    return assistant.chat(user, req.message, req.conversation_id, req.project_id)


@app.get("/api/v1/assistant/conversations")
def assistant_conversations(user: Dict = Depends(current_user)):
    return assistant.list_conversations(user)


@app.patch("/api/v1/assistant/conversations/{conversation_id}")
def assistant_conversation_update(conversation_id: str, req: ConversationUpdateRequest, user: Dict = Depends(current_user)):
    return assistant.update_conversation(conversation_id, user, req.title, req.status)


@app.get("/api/v1/assistant/conversations/{conversation_id}")
def assistant_conversation(conversation_id: str, user: Dict = Depends(current_user)):
    return assistant.get_messages(conversation_id, user)


@app.post("/api/v1/assistant/actions/{action_id}/approve")
def assistant_action_approve(action_id: str, user: Dict = Depends(current_user)):
    return assistant.decide_action(action_id, True, user)


@app.post("/api/v1/assistant/actions/{action_id}/reject")
def assistant_action_reject(action_id: str, user: Dict = Depends(current_user)):
    return assistant.decide_action(action_id, False, user)
