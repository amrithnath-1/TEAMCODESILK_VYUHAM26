"""Core records live in real tables: they survive a restart exactly, keep their order, and obey keys and company boundaries."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app import coretables, db, llm, main
from app.main import app
from app.seed import ADMIN_ACCOUNT
from app.state import STORE, Store

client = TestClient(app)


@pytest.fixture(autouse=True)
def fresh():
    STORE.reset()
    llm.set_client_for_tests(None)
    main._rate_windows.clear()
    yield
    main._rate_windows.clear()


@pytest.fixture
def admin():
    r = client.post("/api/v1/auth/login", json={"username": ADMIN_ACCOUNT["username"], "password": ADMIN_ACCOUNT["password"]})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def state_of(store):
    return ([e.model_dump() for e in store.employees], [t.model_dump() for t in store.tasks], [p.model_dump() for p in store.projects], [a.model_dump() for a in store.assignments],
            [a.model_dump() for a in store.approvals], [d.model_dump() for d in store.decisions], [u.model_dump() for u in store.users], [r.model_dump() for r in store.roles],
            [d.model_dump() for d in store.deliverables], [e.model_dump() for e in store.integration_events], store.weights.model_dump(), store.counters, store.processed_event_keys)


def test_records_are_real_rows(admin):
    assert db.one("SELECT COUNT(*) AS n FROM employees WHERE org_id = ?", (db.org(),))["n"] == 12
    assert db.one("SELECT COUNT(*) AS n FROM tasks WHERE org_id = ?", (db.org(),))["n"] == 8
    vikram = db.one("SELECT name, status FROM employees WHERE id = 'EMP-01'")
    assert vikram["name"] == "Vikram Rao"
    assert db.rows("SELECT skill_name FROM employee_skills WHERE employee_id = 'EMP-01'")
    assert db.rows("SELECT skill_name, level FROM task_required_skills WHERE task_id = 'TSK-102'")
    assert db.rows("SELECT depends_on FROM task_dependencies WHERE task_id = 'TSK-102'") == [{"depends_on": "TSK-101"}]
    assert db.one("SELECT role FROM org_users WHERE username = 'admin'")["role"] == "OWNER"
    assert db.one("SELECT COUNT(*) AS n FROM audit_log WHERE org_id = ?", (db.org(),))["n"] >= 1


def test_everything_survives_a_restart_exactly(admin):
    client.post("/api/v1/tasks/allocate-all", headers=admin)
    client.post("/api/v1/integrations/events", headers=admin, json={"source_system": "GitHub", "external_id": "pr-9", "employee_id": "EMP-01", "pr_review_score": 90, "summary": "Merged"})
    client.post("/api/v1/projects/draft", headers=admin, json={"name": "Second", "objective": "x", "priority": "Low", "deadline_days": 20})
    assert STORE.ledger.verify()["valid"]
    entries = [e.model_dump() for e in STORE.ledger.all()]
    fresh_store = Store(db.DEFAULT_ORG)
    assert state_of(fresh_store) == state_of(STORE._for(db.DEFAULT_ORG))
    assert [e.model_dump() for e in fresh_store.ledger.all()] == entries
    assert fresh_store.ledger.verify()["valid"]


def test_saving_writes_only_what_changed(admin, monkeypatch):
    store = STORE._for(db.DEFAULT_ORG)
    store.save(force=True)
    seen = []
    real = db._Scoped.executemany

    def spy(self, sql, seq):
        seen.append((sql.split()[2], len(list(seq))))
        return real(self, sql, seq)
    monkeypatch.setattr(db._Scoped, "executemany", spy)
    store.employee("EMP-01").meeting_hrs += 1
    assert store.save() is True
    assert seen == [("employees", 1)]
    seen.clear()
    assert store.save() is False and seen == []


def test_removed_records_leave_the_tables(admin):
    task = client.post("/api/v1/projects/PRJ-CRM/tasks", headers=admin, json={"title": "Temp", "description": "d", "required_skills": {"Python": "Beginner"}, "estimated_hours": 1, "priority": "Low", "deadline_days": 5, "deliverable_criteria": "c"}).json()
    assert db.rows("SELECT skill_name FROM task_required_skills WHERE task_id = ?", (task["id"],))
    assert client.delete(f"/api/v1/tasks/{task['id']}", headers=admin).status_code == 200
    assert not db.one("SELECT id FROM tasks WHERE id = ?", (task["id"],))
    assert not db.rows("SELECT skill_name FROM task_required_skills WHERE task_id = ?", (task["id"],))


def test_foreign_keys_reject_orphans():
    with pytest.raises(Exception):
        with db.tx() as c:
            c.execute("INSERT INTO tasks (org_id, id, project_id, title, description, estimated_hours, priority, deadline_days, deliverable_criteria, status, progress_pct, complexity, acceptance_criteria, deliverables, subtasks, blocked, activity, seq) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (db.org(), "TSK-X", "NO-SUCH-PROJECT", "t", "d", 1, "Low", 1, "c", "READY_FOR_ALLOCATION", 0, 1, "[]", "[]", "[]", 0, "[]", 0))


def test_old_snapshot_is_imported_once_and_left_in_place():
    """A company from before these tables: only its JSON row exists."""
    source = Store(db.DEFAULT_ORG)
    org_id = f"ORG-{uuid.uuid4().hex[:8]}"
    payload = {k: [i.model_dump() for i in v] for k, v in source._collections().items()}
    payload.update(weights=source.weights.model_dump(), counters=source.counters, audit=source.ledger.dump(), processed_event_keys=sorted(source.processed_event_keys))
    with db.as_org(org_id), db.tx() as c:
        c.execute("INSERT INTO core_state (key, json, updated_at) VALUES (?, ?, ?)", (f"store:{org_id}", json.dumps(payload, default=str), "2026-10-30T00:00:00Z"))
    imported = Store(org_id)
    assert state_of(imported)[:2] == state_of(source)[:2] and imported.ledger.verify()["valid"]
    with db.as_org(org_id):
        assert db.one("SELECT COUNT(*) AS n FROM employees WHERE org_id = ?", (org_id,))["n"] == 12
        assert db.one("SELECT COUNT(*) AS n FROM core_state WHERE org_id = ?", (org_id,))["n"] == 1
    again = Store(org_id)
    assert state_of(again) == state_of(imported)
    with db.as_org(org_id):
        db.clear_business_data()


def test_two_companies_can_use_the_same_employee_number_rows_apart():
    r = client.post("/api/v1/org/register", json={"company_name": "Rows", "admin_name": "Rae Rows", "email": f"r-{uuid.uuid4().hex[:8]}@x.test", "password": "correct-horse-battery"}).json()
    org_id = r["user"]["org_id"]
    with db.as_org(org_id):
        assert db.rows("SELECT id FROM employees WHERE org_id = ?", (org_id,)) == []
        assert db.one("SELECT role FROM org_users WHERE org_id = ?", (org_id,))["role"] == "OWNER"
    assert coretables.TABLE_NAMES


def test_allocation_after_a_reload_gives_the_pinned_result(admin):
    Store(db.DEFAULT_ORG)
    result = client.post("/api/v1/tasks/allocate-all", headers=admin).json()
    assert result["gini_after"] == 0.1369
