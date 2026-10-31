"""Companies: registration, conversational onboarding, invitations, roles and verified role changes."""
import hashlib
import json
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import HTTPException

from . import db, llm
from .audit import utcnow
from .auth import check_reauth, coarse_role, hash_password, issue_reauth, issue_token, verify_password
from .models import AvailabilitySchedule, Employee, User
from .state import STORE

ROLE_CHANGE = "role_change"
INVITE_DAYS = 7
ROLE_PERMISSIONS = {
    "OWNER": ["Everything an administrator can do", "Manage administrators", "Change organization and security settings", "Transfer ownership"],
    "ADMIN": ["Manage employees and invitations", "Manage all company projects", "Review skill requests", "Approve plans and allocations"],
    "MANAGER": ["Manage projects they are assigned to", "Update project progress", "Review deliverables", "Approve assignments on their projects"],
    "STAFF": ["See assigned projects and tasks", "Use project rooms they belong to", "Submit deliverables and progress", "Request skill reviews"],
}

# Answers kept in the profile. "required" must be present before <start> is accepted.
QUESTIONS = [
    {"key": "description", "required": True, "ask": "What does your company do?"},
    {"key": "services", "required": True, "ask": "What products or services do you provide?"},
    {"key": "project_types", "required": True, "ask": "What kinds of projects do you typically receive or develop?"},
    {"key": "methods", "required": False, "ask": None},
    {"key": "roles", "required": True, "ask": "What departments or professional roles does your company have?"},
    {"key": "team_size", "required": False, "ask": "Roughly how many employees or teams do you have today?"},
    {"key": "constraints", "required": False, "ask": "What budget and schedule constraints are common on your projects? Say skip if you would rather not share them."},
]
TECH_WORDS = r"\b(software|app|apps|web|saas|platform|data|cloud|it|tech|technology|digital|ai|machine learning|cyber)\b"
ONBOARDING_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "answers": {"type": "object", "additionalProperties": False, "properties": {k["key"]: {"type": ["string", "null"]} for k in QUESTIONS}, "required": [k["key"] for k in QUESTIONS]},
        "next_question": {"type": ["string", "null"]},
    },
    "required": ["answers", "next_question"],
}


def session_user(u: User) -> Dict:
    organization = db.one("SELECT id, name, onboarding_state FROM organizations WHERE id = ?", (db.org(),))
    return {"username": u.username, "display_name": u.display_name, "role": coarse_role(u.role), "org_role": u.role, "employee_id": u.employee_id,
            "org_id": organization["id"], "org_name": organization["name"], "onboarding_state": organization["onboarding_state"]}


def _check_new_login(email: str, password: str) -> str:
    username = email.lower().strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", username):
        raise HTTPException(422, "Enter a valid email address")
    if len(password) < 10:
        raise HTTPException(422, "Use a password of at least 10 characters")
    if db.account_org(username):
        raise HTTPException(409, "An account with this email already exists")
    return username


# ------------------------------------------------------------------ registration
def register(company_name: str, admin_name: str, email: str, password: str) -> Dict:
    username = _check_new_login(email, password)
    name = company_name.strip()
    if len(name) < 2:
        raise HTTPException(422, "Enter the company name")
    org_id = f"ORG-{uuid.uuid4().hex[:12]}"
    seq = (db.one("SELECT MAX(seq) AS s FROM organizations")["s"] or 0) + 1
    with db.as_org(org_id):
        with db.tx() as c:
            c.execute("INSERT INTO organizations (id, seq, name, onboarding_state, created_by, created_at) VALUES (?,?,?,?,?,?)",
                      (org_id, seq, name, "collecting", username, utcnow()))
        store = STORE.register(org_id, seq * 1_000_000)
        user = User(username=username, display_name=admin_name.strip() or name, role="OWNER", **hash_password(password))
        store.users.append(user)
        db.add_account(username)
        store.ledger.record(username, "ORGANIZATION_REGISTERED", org_id, {"name": name})
        store.save()
        _say("assistant", f"Welcome to VYUHAM. Let's understand {name} so I can set up workforce and project coordination for you.\n\nFirst, tell me about your company. What does your company do?")
        return {"token": issue_token(user), "user": session_user(user)}


# ------------------------------------------------------------------ onboarding
def _say(role: str, content: str) -> None:
    with db.tx() as c:
        c.execute("INSERT INTO onboarding_messages (id, org_id, role, content, created_at) VALUES (?,?,?,?,?)", (db.ordered_id("ONB"), db.org(), role, content, utcnow()))


def _org_row() -> Dict:
    row = db.one("SELECT * FROM organizations WHERE id = ?", (db.org(),))
    if not row:
        raise HTTPException(404, "Organization not found")
    return row


def onboarding_status() -> Dict:
    row = _org_row()
    profile = json.loads(row["profile_json"])
    return {"state": row["onboarding_state"], "org_name": row["name"], "profile": profile, "missing": _missing(profile),
            "messages": db.rows("SELECT role, content, created_at FROM onboarding_messages WHERE org_id = ? ORDER BY id", (db.org(),))}


def _missing(profile: Dict) -> List[str]:
    return [q["key"] for q in QUESTIONS if q["required"] and not profile.get(q["key"])]


def _next_rule_based(profile: Dict) -> Optional[Dict]:
    """The next unanswered question that applies to this company. Asked questions are recorded so skips stick."""
    technical = re.search(TECH_WORDS, f"{profile.get('description', '')} {profile.get('services', '')}".lower())
    for q in QUESTIONS:
        if q["key"] in profile:
            continue
        if q["key"] == "methods":
            return {"key": "methods", "ask": "Which technologies and technical skills do your projects usually need?" if technical
                    else "Which operational methods, certifications or professional skills do your projects usually need?"}
        return q
    return None


def _summary_text(row_name: str, profile: Dict) -> str:
    labels = {"description": "What you do", "services": "Products and services", "project_types": "Typical projects", "methods": "Skills and methods",
              "roles": "Departments and roles", "team_size": "Team size", "constraints": "Budget and schedule"}
    lines = [f"- **{labels[k]}:** {v}" for k, v in profile.items() if k in labels and v]
    return (f"Here is the company profile I have for **{row_name}**:\n\n" + "\n".join(lines) +
            "\n\nReview your company profile. Type `<start>` to continue to your account dashboard. To change something, just tell me what to correct.")


def onboarding_message(message: str, actor: str) -> Dict:
    row = _org_row()
    if row["onboarding_state"] == "complete":
        raise HTTPException(409, "Onboarding is already complete")
    text = message.strip()
    profile = json.loads(row["profile_json"])
    _say("user", text)
    if text == "<start>":
        return _handle_start(row, profile, actor)
    if row["onboarding_state"] == "review":     # a correction: never overwrite silently, keep the corrections beside the answers
        profile["corrections"] = "; ".join(x for x in (profile.get("corrections"), text) if x)
    else:
        pending = _next_rule_based(profile)
        reply = None
        if llm.is_configured():
            try:
                result = llm.structured("onboarding", system="You run a company onboarding interview. Extract only what the administrator actually said into answers; use null for anything not stated. "
                                        "Never invent company information. next_question is the single most useful next question given what is known, or null when nothing important is left.",
                                        prompt=f"Known so far: {json.dumps(profile)}\nMost recent question topic: {pending['key'] if pending else 'none'}\nAdministrator said: {text}", schema=ONBOARDING_SCHEMA, max_tokens=2000)
                profile.update({k: v for k, v in result["answers"].items() if v})
                reply = result["next_question"]
            except llm.LLMUnavailable:
                reply = None
        if pending and pending["key"] not in profile:
            profile[pending["key"]] = "" if text.lower() in ("skip", "n/a", "none", "no") and not pending.get("required") else text
        following = _next_rule_based(profile)
        if following:
            _save(profile, "collecting")
            _say("assistant", reply or following["ask"])
            return onboarding_status()
    _save(profile, "review")
    _say("assistant", _summary_text(row["name"], profile))
    return onboarding_status()


def _handle_start(row: Dict, profile: Dict, actor: str) -> Dict:
    """<start> only means something at the review step, and only with every required answer saved."""
    if row["onboarding_state"] != "review":
        _say("assistant", "We are not at the review step yet, so I did not treat that as a command. " + (_next_rule_based(profile) or {"ask": "Please continue."})["ask"])
        return onboarding_status()
    missing = _missing(profile)
    if missing:
        _save(profile, "collecting")
        _say("assistant", f"I still need: {', '.join(missing)}. " + next(q["ask"] for q in QUESTIONS if q["key"] == missing[0]))
        return onboarding_status()
    with db.tx() as c:
        c.execute("UPDATE organizations SET onboarding_state = 'complete', onboarded_at = ? WHERE id = ?", (utcnow(), db.org()))
    with STORE.lock:
        STORE.ledger.record(actor, "ONBOARDING_COMPLETED", db.org(), {"fields": sorted(profile)})
    _say("assistant", "Your company profile is saved. Welcome to your dashboard.")
    return onboarding_status()


def _save(profile: Dict, state: str) -> None:
    with db.tx() as c:
        c.execute("UPDATE organizations SET profile_json = ?, onboarding_state = ? WHERE id = ?", (db.dumps(profile), state, db.org()))


# ------------------------------------------------------------------ invitations
def _hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def create_invitation(role: str, email: Optional[str], actor: str) -> Dict:
    if role not in ("STAFF", "MANAGER"):     # higher roles go through verified promotion after joining
        raise HTTPException(422, "Invitations can only grant the employee or manager role")
    code = secrets.token_urlsafe(24)
    invitation_id = db.new_id("INV")
    expires = (datetime.now(timezone.utc) + timedelta(days=INVITE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with db.tx() as c:
        c.execute("INSERT INTO invitations (id, org_id, token_hash, email, role, created_by, created_at, expires_at) VALUES (?,?,?,?,?,?,?,?)",
                  (invitation_id, db.org(), _hash(code), email.lower().strip() if email else None, role, actor, utcnow(), expires))
    with STORE.lock:
        STORE.ledger.record(actor, "INVITATION_CREATED", invitation_id, {"role": role, "email_bound": bool(email)})
    return {"id": invitation_id, "code": code, "role": role, "email": email, "expires_at": expires}     # the code is shown once and only its hash is stored


def list_invitations() -> List[Dict]:
    return db.rows("SELECT id, email, role, created_by, created_at, expires_at, used_by, used_at, revoked_at FROM invitations WHERE org_id = ? ORDER BY created_at DESC", (db.org(),))


def revoke_invitation(invitation_id: str, actor: str) -> Dict:
    row = db.one("SELECT id, used_at FROM invitations WHERE id = ? AND org_id = ?", (invitation_id, db.org()))
    if not row:
        raise HTTPException(404, "Invitation not found")
    if row["used_at"]:
        raise HTTPException(409, "This invitation has already been used")
    with db.tx() as c:
        c.execute("UPDATE invitations SET revoked_at = ? WHERE id = ?", (utcnow(), invitation_id))
    with STORE.lock:
        STORE.ledger.record(actor, "INVITATION_REVOKED", invitation_id, {})
    return {"status": "REVOKED"}


def join(code: str, name: str, email: str, password: str, department: str, designation: str) -> Dict:
    """The company comes only from the invitation; nobody can join by naming a company id."""
    invalid = HTTPException(403, "This invitation is not valid")
    row = db.one("SELECT * FROM invitations WHERE token_hash = ?", (_hash(code.strip()),))
    if not row or row["used_at"] or row["revoked_at"] or row["expires_at"] < utcnow():
        raise invalid
    username = _check_new_login(email, password)
    if row["email"] and row["email"] != username:
        raise invalid
    with db.as_org(row["org_id"]):
        with STORE.lock:
            number = max([int(e.id.split("-")[1]) for e in STORE.employees] + [STORE.counters.get("EMP", 0)]) + 1
            # Only an invitation tied to this exact email can claim an existing record, so nobody can take over someone else's.
            existing = next((e for e in STORE.employees if row["email"] and e.email.lower() == username and not any(u.employee_id == e.id for u in STORE.users)), None)
            employee = existing or Employee(id=f"EMP-{number:02d}", name=name.strip(), email=username, department=department.strip() or "General", designation=designation.strip() or "Team member",
                                manager="", team_role_id="", years_exp=0, skills=[], committed_hrs=0, meeting_hrs=0, delivery_completion_rate=0, work_quality_acceptance_rate=0,
                                deadline_reliability_rate=0, collaboration_review_score=0, learning_improvement_score=0, preferred_tasks=[], learning_goals=[], sufficient_evidence=False,
                                availability=AvailabilitySchedule(meeting_hrs_week=0))
            user = User(username=username, display_name=employee.name, role=row["role"], employee_id=employee.id, **hash_password(password))
            with db.tx() as c:
                changed = c.execute("UPDATE invitations SET used_by = ?, used_at = ? WHERE id = ? AND used_at IS NULL", (username, utcnow(), row["id"]))
                if changed.rowcount != 1:      # lost a race with another use of the same code
                    raise invalid
            if not existing:
                STORE.employees.append(employee)
            STORE.users.append(user)
            db.add_account(username)
            STORE.ledger.record(username, "EMPLOYEE_JOINED", employee.id, {"invitation": row["id"], "role": row["role"]})
            STORE.save()
        db.notify("employee", "New employee joined", f"{employee.name} joined using an invitation.", audience_role="ADMIN", link_view="employee", link_id=employee.id)
        return {"token": issue_token(user), "user": session_user(user)}


# ------------------------------------------------------------------ roles
def list_members() -> List[Dict]:
    return [{"username": u.username, "display_name": u.display_name, "role": u.role, "employee_id": u.employee_id} for u in STORE.users]


def reauthenticate(user: Dict, password: str) -> Dict:
    account = STORE.user(user["sub"])
    if account is None or not verify_password(password, account):
        with STORE.lock:
            STORE.ledger.record(user["sub"], "REAUTHENTICATION_FAILED", "AUTH", {})
        raise HTTPException(403, "That password is not correct")
    return {"reauth_token": issue_reauth(user["sub"], ROLE_CHANGE), "expires_in_seconds": 300}


def change_role(actor: Dict, username: str, new_role: str, reauth_token: str) -> Dict:
    if new_role not in ROLE_PERMISSIONS:
        raise HTTPException(422, "Unknown role")
    if actor["org_role"] not in ("OWNER", "ADMIN"):
        raise HTTPException(403, "Only an owner or administrator can change roles")
    check_reauth(reauth_token, actor["sub"], ROLE_CHANGE)
    with STORE.lock:
        target = STORE.user(username)
        if target is None:      # same answer for another company's user and a user that does not exist
            raise HTTPException(404, "Member not found")
        if target.username == actor["sub"]:
            raise HTTPException(403, "You cannot change your own role")
        if actor["org_role"] != "OWNER" and (target.role == "OWNER" or new_role in ("OWNER", "ADMIN")):
            raise HTTPException(403, "Only an owner can grant or remove administrator and owner roles")
        previous = target.role
        if new_role == "OWNER":     # transfer: exactly one step, with the previous owner stepping down
            me = STORE.user(actor["sub"])
            me.role = "ADMIN"
        elif previous == "OWNER" and sum(1 for u in STORE.users if u.role == "OWNER") <= 1:
            raise HTTPException(409, "The organization must keep at least one owner")
        target.role = new_role
        STORE.ledger.record(actor["sub"], "ROLE_CHANGED", target.username, {"from": previous, "to": new_role})
    db.notify("role", "Your role changed", f"Your role is now {new_role.title()}. Sign in again if anything looks out of date.", audience_user=target.username)
    db.notify("role", "Role changed", f"{target.display_name} is now {new_role.title()} (changed by {actor['sub']}).", audience_role="ADMIN", link_view="team")
    return {"username": target.username, "role": target.role, "previous": previous}


def set_project_manager(project_id: str, username: str, add: bool, actor: str) -> Dict:
    with STORE.lock:
        project = STORE.project(project_id)
        member = STORE.user(username)
        if member is None:
            raise HTTPException(404, "Member not found")
        if add and member.role != "MANAGER":
            raise HTTPException(422, "Only a member with the manager role can manage a project")
        current = set(project.manager_usernames)
        (current.add if add else current.discard)(username)
        project.manager_usernames = sorted(current)
        STORE.ledger.record(actor, "PROJECT_MANAGER_CHANGED", project_id, {"username": username, "added": add})
    return {"project_id": project_id, "manager_usernames": project.manager_usernames}
