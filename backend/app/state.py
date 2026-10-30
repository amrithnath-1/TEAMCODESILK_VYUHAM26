"""In-memory enterprise store. A single re-entrant lock serialises every mutation so
concurrent allocation / approval requests can never double-assign a task."""
import hashlib
import json
import threading
from typing import Dict, List, Optional, Set

from fastapi import HTTPException

from .audit import AuditLedger
from .models import (AgentDecision, ApprovalRecord, Deliverable, Employee, IntegrationEvent, Project, Task,
                     TaskAssignment, TeamRole, User, WeightConfig)
from . import db, seed
from .audit import utcnow


class Store:
    """One organization's core records. Only the demo organization is ever seeded."""

    def __init__(self, org_id: str = db.DEFAULT_ORG, id_offset: int = 0) -> None:
        self.org_id = org_id
        self.key = "store" if org_id == db.DEFAULT_ORG else f"store:{org_id}"
        self.lock = threading.RLock()
        self.ledger = AuditLedger()
        if self.load():
            return
        if org_id != db.DEFAULT_ORG:
            self._start_empty(id_offset)
            return
        if db.has_business_data():   # a missing snapshot is damage to investigate, not a fresh install
            raise RuntimeError("core_state is missing but the database holds data. Restore a backup from "
                               "data/backups; refusing to overwrite it with seed data.")
        self.reset()

    def _start_empty(self, id_offset: int) -> None:
        self.weights = WeightConfig()
        self.employees: List[Employee] = []
        self.tasks: List[Task] = []
        self.projects: List[Project] = []
        self.roles: List[TeamRole] = []
        self.deliverables: List[Deliverable] = []
        self.integration_events: List[IntegrationEvent] = []
        self.processed_event_keys: Set[str] = set()
        self.users: List[User] = []
        self.approvals: List[ApprovalRecord] = []
        self.decisions: List[AgentDecision] = []
        self.assignments: List[TaskAssignment] = []
        # Numbering starts high per company, so a project or task id is unique across all of them.
        self.counters: Dict[str, int] = {p: id_offset for p in ("APR", "DEC", "ASG", "TSK", "INT", "PRJ", "EMP")}
        self.ledger.reset()
        self.ledger.record("SYSTEM_INIT", "ORGANIZATION_CREATED", self.org_id, {})

    # Core entities are written through to SQLite as one transactional JSON snapshot after every
    # successful mutating request (see main.py), so they survive restarts.
    def _collections(self) -> Dict[str, list]:
        return {"employees": self.employees, "tasks": self.tasks, "projects": self.projects, "roles": self.roles,
                "deliverables": self.deliverables, "integration_events": self.integration_events, "users": self.users,
                "approvals": self.approvals, "decisions": self.decisions, "assignments": self.assignments}

    def save(self, force: bool = False) -> bool:
        """Returns whether anything changed. Skips the database write when nothing did, because each one is a network round trip."""
        with self.lock:
            payload = {k: [i.model_dump() for i in v] for k, v in self._collections().items()}
            payload.update(weights=self.weights.model_dump(), counters=self.counters, audit=self.ledger.dump(),
                           processed_event_keys=sorted(self.processed_event_keys))
            text = json.dumps(payload, default=str)
            digest = hashlib.sha256(text.encode()).digest()
            if not force and digest == getattr(self, "_saved_digest", None):
                return False
            with db.as_org(self.org_id), db.tx() as c:
                c.execute("INSERT INTO core_state (key, json, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET json = excluded.json, "
                          "updated_at = excluded.updated_at", (self.key, text, utcnow()))
            self._saved_digest = digest
            return True

    def load(self) -> bool:
        with db.as_org(self.org_id):
            row = db.one("SELECT json FROM core_state WHERE key = ?", (self.key,))
        if not row:
            return False
        p = json.loads(row["json"])
        with self.lock:
            self.weights = WeightConfig(**p["weights"])
            self.employees = [Employee(**x) for x in p["employees"]]
            self.tasks = [Task(**x) for x in p["tasks"]]
            self.projects = [Project(**x) for x in p["projects"]]
            self.roles = [TeamRole(**x) for x in p["roles"]]
            self.deliverables = [Deliverable(**x) for x in p["deliverables"]]
            self.integration_events = [IntegrationEvent(**x) for x in p["integration_events"]]
            self.users = [User(**x) for x in p["users"]]
            self.approvals = [ApprovalRecord(**x) for x in p["approvals"]]
            self.decisions = [AgentDecision(**x) for x in p["decisions"]]
            self.assignments = [TaskAssignment(**x) for x in p["assignments"]]
            self.counters = p["counters"]
            self.processed_event_keys = set(p["processed_event_keys"])
            self.ledger.load(p["audit"])
            if self.users and not any(u.role == "OWNER" for u in self.users):     # records from before organization roles
                next(u for u in self.users if u.role == "ADMIN").role = "OWNER"
        self._register_accounts()
        return True

    def _register_accounts(self) -> None:
        with db.as_org(self.org_id):
            for u in self.users:
                db.add_account(u.username, self.org_id)

    def project(self, project_id: str) -> Project:
        p = next((p for p in self.projects if p.id == project_id), None)
        if p is None:
            raise HTTPException(404, f"Project {project_id} not found")
        return p

    def reset(self) -> None:
        db.require_development("Resetting to seed data")
        with self.lock:
            db.clear_business_data()
            self.weights = WeightConfig()
            self.employees: List[Employee] = seed.seed_employees()
            self.tasks: List[Task] = seed.seed_tasks()
            self.projects: List[Project] = seed.seed_projects()
            self.roles: List[TeamRole] = seed.seed_roles()
            self.deliverables: List[Deliverable] = seed.seed_deliverables()
            self.integration_events: List[IntegrationEvent] = seed.seed_integration_events()
            self.processed_event_keys: Set[str] = {f"{e.source_system}:{e.external_id}" for e in self.integration_events}
            self.users: List[User] = seed.seed_users(self.employees)
            self.approvals: List[ApprovalRecord] = []
            self.decisions: List[AgentDecision] = []
            self.assignments: List[TaskAssignment] = []
            self.counters: Dict[str, int] = {"APR": 500, "DEC": 700, "ASG": 900, "TSK": 200, "INT": 3, "PRJ": 1}
            self.ledger.reset()
            self.ledger.record("SYSTEM_INIT", "SEED_ENTERPRISE_DATA", "PRJ-CRM",
                               {"employees": len(self.employees), "tasks": len(self.tasks)})
            self._register_accounts()
            self.save()

    def next_id(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}-{self.counters[prefix]}"

    def employee(self, emp_id: str) -> Employee:
        emp = next((e for e in self.employees if e.id == emp_id), None)
        if emp is None:
            raise HTTPException(404, f"Employee {emp_id} not found")
        return emp

    def find_employee(self, emp_id: Optional[str]) -> Optional[Employee]:
        return next((e for e in self.employees if e.id == emp_id), None)

    def task(self, task_id: str) -> Task:
        t = next((t for t in self.tasks if t.id == task_id), None)
        if t is None:
            raise HTTPException(404, f"Task {task_id} not found")
        return t

    def user(self, username: str) -> Optional[User]:
        return next((u for u in self.users if u.username == username.lower().strip()), None)


class OrgStores:
    """STORE everywhere in the app: resolves to the current request's organization, so one company can never read another's records."""

    def __init__(self) -> None:
        object.__setattr__(self, "_stores", {})
        object.__setattr__(self, "_guard", threading.Lock())
        self._for(db.DEFAULT_ORG)

    def _for(self, org_id: str, id_offset: int = 0) -> Store:
        with self._guard:
            store = self._stores.get(org_id)
            if store is None:
                store = self._stores[org_id] = Store(org_id, id_offset)
            return store

    def register(self, org_id: str, id_offset: int) -> Store:
        store = self._for(org_id, id_offset)
        store.save()
        return store

    def _current(self) -> Store:
        org_id = db.org()
        if not org_id:
            raise HTTPException(401, "Authentication required")
        return self._for(org_id)

    def __getattr__(self, name: str):
        return getattr(self._current(), name)

    def __setattr__(self, name: str, value) -> None:
        setattr(self._current(), name, value)


STORE = OrgStores()
