import threading

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.seed import ADMIN_ACCOUNT, STAFF_PASSWORD
from app.state import STORE

client = TestClient(app)

EXPECTED = {
    "TSK-101": ("EMP-06", 82.58, 70.0), "TSK-102": ("EMP-01", 78.97, 85.0), "TSK-103": ("EMP-05", 79.45, 85.0),
    "TSK-104": ("EMP-02", 78.54, 90.0), "TSK-105": ("EMP-04", 63.10, 67.5), "TSK-106": ("EMP-07", 78.24, 82.5),
    "TSK-107": ("EMP-09", 81.32, 80.0), "TSK-108": ("EMP-10", 79.93, 90.0),
}


def login(username, password):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(autouse=True)
def fresh():
    STORE.reset()
    yield


@pytest.fixture
def admin():
    return login(ADMIN_ACCOUNT["username"], ADMIN_ACCOUNT["password"])


@pytest.fixture
def staff():
    return login("sneha", STAFF_PASSWORD)


def test_reference_allocation_matches_targets(admin):
    r = client.post("/api/v1/tasks/allocate-all", headers=admin).json()
    assert (r["gini_before"], r["gini_after"]) == (0.1584, 0.1369)
    got = {a["task_id"]: (a["recommended"]["employee_id"], a["recommended"]["suitability_score"],
                          a["recommended"]["utilization_after_pct"]) for a in r["allocations"]}
    assert got == EXPECTED


def test_overloaded_and_new_hire_never_assigned(admin):
    r = client.post("/api/v1/tasks/allocate-all", headers=admin).json()
    owners = {a["recommended"]["employee_id"] for a in r["allocations"]}
    assert "EMP-11" not in owners and "EMP-12" not in owners
    kabir = client.get("/api/v1/employees/EMP-12/evaluation", headers=admin).json()["scores"]
    assert kabir["level"].startswith("Insufficient Evidence") and kabir["performance_score"] is None


def test_critical_tasks_require_hitl(admin):
    r = client.post("/api/v1/tasks/allocate-all", headers=admin).json()
    statuses = {a["task_id"]: a["status"] for a in r["allocations"]}
    assert statuses["TSK-102"] == "PENDING_HITL_APPROVAL"   # Critical
    assert statuses["TSK-108"] == "PENDING_HITL_APPROVAL"   # 90% post-load
    assert statuses["TSK-101"] == "ASSIGNED"


def test_disruption_creates_reallocation_and_approval_executes(admin):
    client.post("/api/v1/tasks/allocate-all", headers=admin)
    d = client.post("/api/v1/disruptions/simulate", headers=admin, json={"employee_id": "EMP-01", "new_status": "On Leave"}).json()
    assert len(d["proposals_created"]) == 1
    p = d["proposals_created"][0]
    assert p["task_id"] == "TSK-102" and p["recommended_new_owner_id"] != "EMP-01"
    a = client.post(f"/api/v1/approvals/{p['approval_id']}/approve", headers=admin, json={}).json()
    assert a["status"] == "EXECUTED_AND_VERIFIED" and a["verification"]["verified"]
    # approving twice is rejected (no double execution)
    assert client.post(f"/api/v1/approvals/{p['approval_id']}/approve", headers=admin, json={}).status_code == 409


def test_duplicate_disruption_does_not_duplicate_proposals(admin):
    client.post("/api/v1/tasks/allocate-all", headers=admin)
    body = {"employee_id": "EMP-01", "new_status": "On Leave"}
    client.post("/api/v1/disruptions/simulate", headers=admin, json=body)
    second = client.post("/api/v1/disruptions/simulate", headers=admin, json=body).json()
    assert second["proposals_created"] == []


def test_staff_cannot_use_admin_endpoints_or_see_others(staff):
    assert client.post("/api/v1/tasks/allocate-all", headers=staff).status_code == 403
    assert client.get("/api/v1/dashboard/summary", headers=staff).status_code == 403
    assert client.get("/api/v1/employees/EMP-01/evaluation", headers=staff).status_code == 403
    assert client.get("/api/v1/employees/EMP-06/evaluation", headers=staff).status_code == 200


def test_unauthenticated_and_bad_password():
    assert client.get("/api/v1/dashboard/summary").status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401


def test_weights_must_sum_to_one(admin):
    bad = {"skill_match": 0.5, "availability": 0.5, "workload_balance": 0.2, "priority_alignment": 0.0,
           "past_performance": 0.0, "development_opportunity": 0.0}
    assert client.post("/api/v1/admin/weights", headers=admin, json=bad).status_code == 422


def test_duplicate_integration_event_ignored(admin):
    ev = {"employee_id": "EMP-03", "source_system": "GitHub", "external_id": "gh-pr-9001", "pr_review_score": 90, "summary": "Reviewed PR"}
    assert client.post("/api/v1/integrations/events", headers=admin, json=ev).json()["status"] == "INGESTED"
    assert client.post("/api/v1/integrations/events", headers=admin, json=ev).json()["status"] == "DUPLICATE_IGNORED"


def test_audit_chain_detects_tampering(admin):
    client.post("/api/v1/tasks/allocate-all", headers=admin)
    assert STORE.ledger.verify()["valid"]
    STORE.ledger.all()[1].details["score"] = 100   # tamper with history
    assert not STORE.ledger.verify()["valid"]


def test_concurrent_allocation_never_double_assigns(admin):
    errors = []

    def run():
        r = client.post("/api/v1/tasks/allocate-all", headers=admin)
        if r.status_code != 200:
            errors.append(r.text)

    threads = [threading.Thread(target=run) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors
    active = [a for a in STORE.assignments if a.status in ("ACTIVE", "PENDING_HITL_APPROVAL")]
    assert len(active) == len({a.task_id for a in active}) == 8


def test_project_brief_decomposes_into_valid_dag(admin):
    r = client.post("/api/v1/projects", headers=admin, json={
        "name": "Field Service App", "objective": "Build a mobile app and dashboard with AI predictive maintenance for technicians",
        "priority": "High", "deadline_days": 30}).json()
    ids = {t["id"] for t in r["tasks"]}
    assert len(ids) >= 5
    assert all(set(t["dependencies"]) <= ids for t in r["tasks"])
    assert r["critical_path"]["path"]


def test_staff_progress_only_on_own_task(admin, staff):
    client.post("/api/v1/tasks/allocate-all", headers=admin)
    assert client.post("/api/v1/tasks/TSK-101/progress", headers=staff, json={"progress_pct": 40}).status_code == 200
    assert client.post("/api/v1/tasks/TSK-103/progress", headers=staff, json={"progress_pct": 40}).status_code == 403


def test_chat_disruption_routes_to_hitl(admin):
    client.post("/api/v1/tasks/allocate-all", headers=admin)
    r = client.post("/api/v1/chat/coordinator", headers=admin, json={"query": "Vikram is on sick leave for 2 days"}).json()
    assert "HITL" in r["response"] and r["data"]["proposals_created"]
