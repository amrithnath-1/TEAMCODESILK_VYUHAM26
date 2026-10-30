"""Routes for companies, roles, skills review, project overview, team rooms, budgets and the optimizer."""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import budget, db, documents, org, progress, rooms, skillreview
from .auth import assert_self_or_admin, current_user, require_admin
from .ratelimit import rate_limit
from .state import STORE

router = APIRouter(prefix="/api/v1")


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class RegisterRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=120)
    admin_name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class JoinRequest(BaseModel):
    code: str = Field(min_length=10, max_length=200)
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)
    department: str = Field(default="", max_length=120)
    designation: str = Field(default="", max_length=120)


class OnboardingMessage(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class InvitationRequest(BaseModel):
    role: str = "STAFF"
    email: Optional[str] = Field(default=None, max_length=200)


class ReauthRequest(BaseModel):
    password: str = Field(max_length=200)


class RoleChangeRequest(BaseModel):
    role: str
    reauth_token: str


class ProjectManagerRequest(BaseModel):
    username: str
    add: bool = True


class SkillScoreRequest(BaseModel):
    skill: str = Field(min_length=1, max_length=100)
    score: float
    confidence: str = "medium"
    reason: str = Field(min_length=1, max_length=1000)
    evidence: Optional[str] = Field(default=None, max_length=2000)


class SkillRequestCreate(BaseModel):
    skill: str = Field(min_length=1, max_length=100)
    kind: str
    requested_score: Optional[float] = None
    explanation: str = Field(min_length=1, max_length=2000)
    evidence: Optional[str] = Field(default=None, max_length=2000)


class SkillRequestReview(BaseModel):
    status: str
    notes: str = Field(default="", max_length=2000)
    score: Optional[float] = None
    confidence: str = "medium"


class SkillRequestResponse(BaseModel):
    explanation: str = Field(min_length=1, max_length=2000)
    evidence: Optional[str] = Field(default=None, max_length=2000)


class RoomMessage(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MinutesRequest(BaseModel):
    title: str = Field(default="Meeting minutes", max_length=160)
    text: str = Field(min_length=10, max_length=100_000)


class BudgetRequest(BaseModel):
    currency: str
    total_minor: int
    labor_minor: Optional[int] = None
    non_labor_minor: int = 0
    reserve_minor: int = 0
    includes_tax: bool = False
    hard_limit: bool = False


class RateRequest(BaseModel):
    employee_id: Optional[str] = None
    role_name: Optional[str] = None
    project_id: Optional[str] = None
    currency: str
    hourly_minor: int


class CostEntryRequest(BaseModel):
    kind: str
    amount_minor: int
    task_id: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=500)
    hours: Optional[float] = None


class PolicyRequest(BaseModel):
    delivery_risk: Optional[float] = Field(default=None, ge=0)
    schedule_risk: Optional[float] = Field(default=None, ge=0)
    imbalance: Optional[float] = Field(default=None, ge=0)
    reassignment: Optional[float] = Field(default=None, ge=0)
    min_suitability: Optional[float] = Field(default=None, ge=0, le=100)

    def overrides(self) -> Dict:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class ApplyRequest(PolicyRequest):
    proposal_id: str


# ------------------------------------------------------------------ registration and onboarding
@router.post("/org/register")
def register(req: RegisterRequest, request: Request):
    rate_limit(f"register:{_ip(request)}", 10, 3600)
    return org.register(req.company_name, req.admin_name, req.email, req.password)


@router.post("/org/join")
def join(req: JoinRequest, request: Request):
    rate_limit(f"join:{_ip(request)}", 20, 3600)    # codes are long enough that guessing fails anyway; this keeps attempts visible and slow
    return org.join(req.code, req.name, req.email, req.password, req.department, req.designation)


@router.get("/org/onboarding")
def onboarding(_: Dict = Depends(require_admin)):
    return org.onboarding_status()


@router.post("/org/onboarding/message")
def onboarding_message(req: OnboardingMessage, user: Dict = Depends(require_admin)):
    return org.onboarding_message(req.message, user["sub"])


# ------------------------------------------------------------------ members, invitations and roles
@router.get("/org/roles")
def roles(_: Dict = Depends(current_user)):
    return org.ROLE_PERMISSIONS


@router.get("/org/members")
def members(_: Dict = Depends(require_admin)):
    return org.list_members()


@router.post("/org/invitations")
def create_invitation(req: InvitationRequest, user: Dict = Depends(require_admin)):
    return org.create_invitation(req.role, req.email, user["sub"])


@router.get("/org/invitations")
def invitations(_: Dict = Depends(require_admin)):
    return org.list_invitations()


@router.delete("/org/invitations/{invitation_id}")
def revoke_invitation(invitation_id: str, user: Dict = Depends(require_admin)):
    return org.revoke_invitation(invitation_id, user["sub"])


@router.post("/org/reauth")
def reauth(req: ReauthRequest, user: Dict = Depends(current_user)):
    rate_limit(f"reauth:{user['sub']}", 5, 300)
    return org.reauthenticate(user, req.password)


@router.post("/org/members/{username}/role")
def change_role(username: str, req: RoleChangeRequest, user: Dict = Depends(require_admin)):
    return org.change_role(user, username, req.role, req.reauth_token)


@router.post("/projects/{project_id}/managers")
def project_manager(project_id: str, req: ProjectManagerRequest, user: Dict = Depends(require_admin)):
    return org.set_project_manager(project_id, req.username, req.add, user["sub"])


# ------------------------------------------------------------------ skills
@router.get("/skills/scale")
def skill_scale(_: Dict = Depends(current_user)):
    return {"scale": skillreview.SCALE, "confidence": skillreview.CONFIDENCE, "note": "A skill score says nothing about workload, availability, experience or delivery record."}


@router.post("/employees/{employee_id}/skills/score")
def set_skill_score(employee_id: str, req: SkillScoreRequest, user: Dict = Depends(require_admin)):
    return skillreview.set_score(employee_id, req.skill, req.score, req.confidence, req.reason, req.evidence, user["sub"])


@router.get("/employees/{employee_id}/skills/history")
def skill_history(employee_id: str, user: Dict = Depends(current_user)):
    assert_self_or_admin(user, employee_id)
    return skillreview.history(employee_id)


@router.post("/skill-requests")
def submit_skill_request(req: SkillRequestCreate, user: Dict = Depends(current_user)):
    if not user.get("emp"):
        raise HTTPException(400, "This account has no employee profile")
    return skillreview.submit(user["emp"], req.skill, req.kind, req.requested_score, req.explanation, req.evidence, user["sub"])


@router.get("/skill-requests")
def skill_requests(status: Optional[str] = None, user: Dict = Depends(current_user)):
    return skillreview.list_requests(user, status)


@router.post("/skill-requests/{request_id}/review")
def review_skill_request(request_id: str, req: SkillRequestReview, user: Dict = Depends(require_admin)):
    return skillreview.review(request_id, req.status, req.notes, req.score, req.confidence, user["sub"])


@router.post("/skill-requests/{request_id}/respond")
def respond_skill_request(request_id: str, req: SkillRequestResponse, user: Dict = Depends(current_user)):
    return skillreview.respond(request_id, user.get("emp"), req.explanation, req.evidence, user["sub"])


# ------------------------------------------------------------------ project overview
@router.get("/projects/overview")
def projects_overview(user: Dict = Depends(current_user)):
    return progress.overview(user)


@router.get("/projects/{project_id}/transitions")
def project_transitions(project_id: str, user: Dict = Depends(current_user)):
    progress.assert_project_access(user, project_id)
    return db.rows("SELECT from_stage, to_stage, actor, created_at FROM project_transitions WHERE project_id = ? AND org_id = ? ORDER BY id", (project_id, db.org()))


# ------------------------------------------------------------------ rooms
@router.get("/projects/{project_id}/room")
def room(project_id: str, user: Dict = Depends(current_user)):
    return rooms.room_view(user, project_id)


@router.get("/projects/{project_id}/room/messages")
def room_messages(project_id: str, after: Optional[str] = None, q: Optional[str] = None, user: Dict = Depends(current_user)):
    return rooms.list_messages(user, project_id, after, q)


@router.post("/projects/{project_id}/room/messages")
def post_room_message(project_id: str, req: RoomMessage, user: Dict = Depends(current_user)):
    rate_limit(f"room:{user['sub']}", 60, 60)
    return rooms.post_message(user, project_id, req.content)


@router.post("/projects/{project_id}/room/files")
async def upload_room_file(project_id: str, file: UploadFile = File(...), user: Dict = Depends(current_user)):
    rate_limit(f"upload:{user['sub']}", 40, 60)
    return rooms.add_attachment(user, project_id, file.filename or "", await file.read(documents.MAX_BYTES + 1))


@router.get("/projects/{project_id}/room/files/{attachment_id}")
def download_room_file(project_id: str, attachment_id: str, user: Dict = Depends(current_user)):
    row = rooms.get_attachment(user, project_id, attachment_id)
    from pathlib import Path
    if not Path(row["stored_path"]).exists():       # hosts can clear local disk on restart
        raise HTTPException(404, "This file is no longer available on the server. Please upload it again.")
    # Always a download, never rendered: an uploaded file must not run as a page on this site.
    return Response(Path(row["stored_path"]).read_bytes(), media_type="application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{row["filename"]}"'})


@router.delete("/projects/{project_id}/room/files/{attachment_id}")
def delete_room_file(project_id: str, attachment_id: str, user: Dict = Depends(current_user)):
    return rooms.remove_attachment(user, project_id, attachment_id)


@router.post("/projects/{project_id}/room/minutes")
def add_minutes(project_id: str, req: MinutesRequest, user: Dict = Depends(current_user)):
    return rooms.add_minutes(user, project_id, req.title, req.text)


@router.post("/projects/{project_id}/room/minutes/file")
async def add_minutes_file(project_id: str, file: UploadFile = File(...), title: str = Form("Meeting minutes"), user: Dict = Depends(current_user)):
    data = await file.read(documents.MAX_BYTES + 1)
    try:
        ext = documents.validate_upload(file.filename or "", data, documents.RESUME_ALLOWED)
        text = "\n".join(t for _, t in documents.extract(ext, data))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except Exception:
        raise HTTPException(422, "The minutes could not be read. Try pasting them as text.")
    return rooms.add_minutes(user, project_id, title, text)


@router.post("/projects/{project_id}/room/minutes/{minutes_id}/approve")
def approve_minutes(project_id: str, minutes_id: str, user: Dict = Depends(current_user)):
    progress.assert_can_manage(user, project_id)
    return rooms.approve_minutes(user, project_id, minutes_id)


@router.get("/projects/{project_id}/knowledge")
def project_knowledge(project_id: str, q: str = "", user: Dict = Depends(current_user)):
    return rooms.knowledge(user, project_id, q[:400])


# ------------------------------------------------------------------ budget and optimizer
@router.get("/projects/{project_id}/budget")
def get_budget(project_id: str, user: Dict = Depends(current_user)):
    progress.assert_can_manage(user, project_id)
    return budget.report(project_id)


@router.put("/projects/{project_id}/budget")
def set_budget(project_id: str, req: BudgetRequest, user: Dict = Depends(require_admin)):
    return budget.set_budget(project_id, req.model_dump(), user["sub"])


@router.post("/projects/{project_id}/costs")
def add_cost(project_id: str, req: CostEntryRequest, user: Dict = Depends(current_user)):
    progress.assert_can_manage(user, project_id)
    return budget.add_entry(project_id, req.model_dump(), user["sub"])


@router.get("/cost-rates")
def cost_rates(_: Dict = Depends(require_admin)):
    return budget.list_rates()


@router.post("/cost-rates")
def add_cost_rate(req: RateRequest, user: Dict = Depends(require_admin)):
    return budget.add_rate(req.model_dump(), user["sub"])


@router.post("/projects/{project_id}/optimize")
def optimize(project_id: str, req: PolicyRequest = PolicyRequest(), user: Dict = Depends(current_user)):
    progress.assert_can_manage(user, project_id)
    return budget.propose(project_id, req.overrides())


@router.post("/projects/{project_id}/optimize/apply")
def apply_optimized(project_id: str, req: ApplyRequest, user: Dict = Depends(current_user)):
    progress.assert_can_manage(user, project_id)
    return budget.apply(project_id, req.proposal_id, user["sub"], req.overrides())
