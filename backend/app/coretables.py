"""Core records as real tables: employees, projects, tasks, assignments, approvals, decisions, users and the audit ledger.

The app still works on Store's in-memory lists and writes through on save, so only rows that changed touch the database.
`seq` keeps each list's order, which allocation results depend on. Nested values with no use as columns stay JSON text.
"""
import json
from dataclasses import dataclass
from typing import Callable, Dict, FrozenSet, List, Optional, Tuple

from pydantic import BaseModel

from . import db
from .audit import utcnow
from .models import AgentDecision, ApprovalRecord, AuditLog, Deliverable, Employee, EmployeeSkill, IntegrationEvent, Project, Task, TaskAssignment, TeamRole, User, WeightConfig


@dataclass(frozen=True)
class Spec:
    table: str
    attr: str
    model: type
    pk: Tuple[str, ...]
    json_columns: FrozenSet[str] = frozenset()
    children: FrozenSet[str] = frozenset()      # model fields stored in their own table
    append_only: bool = False


def _spec(table, attr, model, pk="id", json_columns=(), children=(), append_only=False) -> Spec:
    return Spec(table, attr, model, (pk,), frozenset(json_columns), frozenset(children), append_only)


# Parents first: saved in this order, deleted in reverse.
PARENTS: List[Spec] = [
    _spec("team_roles", "roles", TeamRole, json_columns=["role_eval_weights"]),
    _spec("employees", "employees", Employee, json_columns=["preferred_tasks", "learning_goals", "availability"], children=["skills"]),
    _spec("projects", "projects", Project, json_columns=["manager_usernames"]),
    _spec("tasks", "tasks", Task, json_columns=["acceptance_criteria", "deliverables", "subtasks", "activity"], children=["required_skills", "dependencies"]),
    _spec("task_assignments", "assignments", TaskAssignment, json_columns=["factor_breakdown", "tradeoffs_flagged"]),
    _spec("deliverables", "deliverables", Deliverable),
    _spec("integration_events", "integration_events", IntegrationEvent),
    _spec("agent_decisions", "decisions", AgentDecision, json_columns=["shortlist"]),
    _spec("approvals", "approvals", ApprovalRecord, pk="approval_id", json_columns=["shortlist"]),
    _spec("org_users", "users", User, pk="username"),
    _spec("audit_log", "", AuditLog, json_columns=["details"], append_only=True),
]
CHILD_COLUMNS = {
    "employee_skills": ("employee_id", "skill_name", "level", "is_verified", "evidence_source", "seq"),
    "task_required_skills": ("task_id", "skill_name", "level", "seq"),
    "task_dependencies": ("task_id", "depends_on", "seq"),
}
CHILD_KEYS = {"employee_skills": ("employee_id", "skill_name"), "task_required_skills": ("task_id", "skill_name"), "task_dependencies": ("task_id", "depends_on")}
TABLE_NAMES = [s.table for s in PARENTS] + list(CHILD_COLUMNS) + ["org_settings"]
# Children before parents, so foreign keys hold when a company's records are cleared.
CLEAR_ORDER = list(CHILD_COLUMNS) + [s.table for s in reversed(PARENTS)] + ["org_settings"]


def _columns(spec: Spec) -> List[str]:
    return [name for name in spec.model.model_fields if name not in spec.children]


def _value(spec: Spec, name: str, item) -> object:
    value = getattr(item, name)
    if name in spec.json_columns:
        return json.dumps(value.model_dump() if isinstance(value, BaseModel) else value, default=str, sort_keys=True)
    return value


def _items(store, spec: Spec) -> list:
    return store.ledger.all() if spec.table == "audit_log" else getattr(store, spec.attr)


def _build_rows(store) -> Dict[str, Dict[tuple, tuple]]:
    """Everything the store holds as {table: {key: columns}}, ready to compare with what was last written."""
    org = store.org_id
    rows: Dict[str, Dict[tuple, tuple]] = {}
    for spec in PARENTS:
        cols = _columns(spec)
        rows[spec.table] = {tuple(getattr(i, k) for k in spec.pk): (org, *[_value(spec, c, i) for c in cols], seq) for seq, i in enumerate(_items(store, spec))}
    rows["employee_skills"] = {(e.id, s.skill_name): (org, e.id, s.skill_name, s.level, s.is_verified, s.evidence_source, n) for e in store.employees for n, s in enumerate(e.skills)}
    rows["task_required_skills"] = {(t.id, k): (org, t.id, k, v, n) for t in store.tasks for n, (k, v) in enumerate(t.required_skills.items())}
    rows["task_dependencies"] = {(t.id, d): (org, t.id, d, n) for t in store.tasks for n, d in enumerate(t.dependencies)}
    return rows


def _upsert(table: str, columns: List[str], keys: Tuple[str, ...], append_only: bool) -> str:
    all_columns = ["org_id", *columns]
    insert = f"INSERT INTO {table} ({', '.join(all_columns)}) VALUES ({', '.join('?' * len(all_columns))}) ON CONFLICT (org_id, {', '.join(keys)}) "
    if append_only:     # the app role has no right to rewrite history
        return insert + "DO NOTHING"
    updates = [c for c in columns if c not in keys]
    return insert + "DO UPDATE SET " + ", ".join(f"{c} = excluded.{c}" for c in updates)


def save(store) -> None:
    """One transaction, writing only what differs from the last save."""
    org = store.org_id
    current = _build_rows(store)
    previous = getattr(store, "_rows", {})
    with db.as_org(org), db.tx() as c:
        for table in list(CHILD_COLUMNS) + [s.table for s in reversed(PARENTS) if not s.append_only]:
            gone = [k for k in previous.get(table, {}) if k not in current[table]]
            if gone:
                keys = CHILD_KEYS.get(table) or next(s.pk for s in PARENTS if s.table == table)
                where = " AND ".join(f"{k} = ?" for k in keys)
                c.executemany(f"DELETE FROM {table} WHERE org_id = ? AND {where}", [(org, *k) for k in gone])
        for spec in PARENTS:
            changed = [v for k, v in current[spec.table].items() if previous.get(spec.table, {}).get(k) != v]
            if changed:
                c.executemany(_upsert(spec.table, _columns(spec) + ["seq"], spec.pk, spec.append_only), changed)
        for table, columns in CHILD_COLUMNS.items():
            changed = [v for k, v in current[table].items() if previous.get(table, {}).get(k) != v]
            if changed:
                c.executemany(_upsert(table, list(columns), CHILD_KEYS[table], False), changed)
        c.execute("INSERT INTO org_settings (org_id, weights_json, counters_json, processed_event_keys_json, updated_at) VALUES (?,?,?,?,?) ON CONFLICT (org_id) DO UPDATE SET "
                  "weights_json = excluded.weights_json, counters_json = excluded.counters_json, processed_event_keys_json = excluded.processed_event_keys_json, updated_at = excluded.updated_at",
                  (org, json.dumps(store.weights.model_dump()), json.dumps(store.counters), json.dumps(sorted(store.processed_event_keys)), utcnow()))
    store._rows = current


def _select(table: str, order: str = "seq") -> List[Dict]:
    return db.rows(f"SELECT * FROM {table} WHERE org_id = ? ORDER BY {order}", (db.org(),))


def _revive(spec: Spec, row: Dict, extra: Optional[Dict] = None):
    values = {c: json.loads(row[c]) if c in spec.json_columns else row[c] for c in _columns(spec)}
    return spec.model(**values, **(extra or {}))


def load(store) -> bool:
    """False when this company has not been written to these tables yet."""
    with db.as_org(store.org_id):
        settings = db.one("SELECT * FROM org_settings WHERE org_id = ?", (db.org(),))
        if not settings:
            return False
        skills: Dict[str, List[EmployeeSkill]] = {}
        for r in _select("employee_skills"):
            skills.setdefault(r["employee_id"], []).append(EmployeeSkill(skill_name=r["skill_name"], level=r["level"], is_verified=bool(r["is_verified"]), evidence_source=r["evidence_source"]))
        required: Dict[str, Dict[str, str]] = {}
        for r in _select("task_required_skills"):
            required.setdefault(r["task_id"], {})[r["skill_name"]] = r["level"]
        dependencies: Dict[str, List[str]] = {}
        for r in _select("task_dependencies"):
            dependencies.setdefault(r["task_id"], []).append(r["depends_on"])
        by_table = {s.table: s for s in PARENTS}
        store.roles = [_revive(by_table["team_roles"], r) for r in _select("team_roles")]
        store.employees = [_revive(by_table["employees"], r, {"skills": skills.get(r["id"], [])}) for r in _select("employees")]
        store.projects = [_revive(by_table["projects"], r) for r in _select("projects")]
        store.tasks = [_revive(by_table["tasks"], r, {"required_skills": required.get(r["id"], {}), "dependencies": dependencies.get(r["id"], [])}) for r in _select("tasks")]
        store.assignments = [_revive(by_table["task_assignments"], r) for r in _select("task_assignments")]
        store.deliverables = [_revive(by_table["deliverables"], r) for r in _select("deliverables")]
        store.integration_events = [_revive(by_table["integration_events"], r) for r in _select("integration_events")]
        store.decisions = [_revive(by_table["agent_decisions"], r) for r in _select("agent_decisions")]
        store.approvals = [_revive(by_table["approvals"], r) for r in _select("approvals")]
        store.users = [_revive(by_table["org_users"], r) for r in _select("org_users")]
        store.ledger.load([_revive(by_table["audit_log"], r).model_dump() for r in _select("audit_log")])
        store.weights = WeightConfig(**json.loads(settings["weights_json"]))
        store.counters = json.loads(settings["counters_json"])
        store.processed_event_keys = set(json.loads(settings["processed_event_keys_json"]))
    store._rows = _build_rows(store)
    return True
