"""In-memory enterprise store. A single re-entrant lock serialises every mutation so
concurrent allocation / approval requests can never double-assign a task."""
import threading
from typing import Dict, List, Optional, Set

from fastapi import HTTPException

from .audit import AuditLedger
from .models import (AgentDecision, ApprovalRecord, Deliverable, Employee, IntegrationEvent, Project, Task,
                     TaskAssignment, TeamRole, User, WeightConfig)
from . import seed


class Store:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.ledger = AuditLedger()
        self.reset()

    def reset(self) -> None:
        with self.lock:
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
