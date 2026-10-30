"""In-memory enterprise store. A single re-entrant lock serialises every mutation so
concurrent allocation / approval requests can never double-assign a task."""
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
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.ledger = AuditLedger()
        if not self.load():
            self.reset()

    # Core entities are written through to SQLite as one transactional JSON snapshot after every
    # successful mutating request (see main.py), so they survive restarts.
    def _collections(self) -> Dict[str, list]:
        return {"employees": self.employees, "tasks": self.tasks, "projects": self.projects, "roles": self.roles,
                "deliverables": self.deliverables, "integration_events": self.integration_events, "users": self.users,
                "approvals": self.approvals, "decisions": self.decisions, "assignments": self.assignments}

    def save(self) -> None:
        with self.lock:
            payload = {k: [i.model_dump() for i in v] for k, v in self._collections().items()}
            payload.update(weights=self.weights.model_dump(), counters=self.counters, audit=self.ledger.dump(),
                           processed_event_keys=sorted(self.processed_event_keys))
            with db.tx() as c:
                c.execute("INSERT INTO core_state VALUES ('store', ?, ?) ON CONFLICT(key) DO UPDATE SET json = excluded.json, "
                          "updated_at = excluded.updated_at", (json.dumps(payload, default=str), utcnow()))

    def load(self) -> bool:
        row = db.one("SELECT json FROM core_state WHERE key = 'store'")
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
        return True

    def project(self, project_id: str) -> Project:
        p = next((p for p in self.projects if p.id == project_id), None)
        if p is None:
            raise HTTPException(404, f"Project {project_id} not found")
        return p

    def reset(self) -> None:
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
            self.save()

    def next_id(self, prefix: str) -> str:
        self.counters[prefix] += 1
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


STORE = Store()
