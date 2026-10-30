"""Phase 1 hardening: approval gates, staff data boundaries, tokens, login limits, reset and migration safety."""
import base64
import hashlib
import hmac
import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from app import auth, db, llm, main
from app.main import app
from app.seed import ADMIN_ACCOUNT, STAFF_PASSWORD
from app.state import STORE, Store

client = TestClient(app)


def login(username, password):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(autouse=True)
def fresh():
    STORE.reset()
    llm.set_client_for_tests(None)
    main._rate_windows.clear()
    yield
    main._rate_windows.clear()


@pytest.fixture
def admin():
    return login(ADMIN_ACCOUNT["username"], ADMIN_ACCOUNT["password"])


@pytest.fixture
def staff():
    return login("sneha", STAFF_PASSWORD)


def chat(headers, message):
    r = client.post("/api/v1/assistant/chat", headers=headers, json={"message": message})
    assert r.status_code == 200
    return r.json()


def state_fingerprint():
    return ([(e.id, e.status) for e in STORE.employees], [(t.id, t.assigned_to, t.status) for t in STORE.tasks], len(STORE.assignments))


def test_old_chat_route_is_gone(admin):
    assert client.post("/api/v1/chat/coordinator", headers=admin, json={"query": "hello"}).status_code == 404


@pytest.mark.parametrize("message", ["there is an emergency", "plan the sprint", "how do i leave feedback for the team", "absent minded question"])
def test_offline_assistant_never_changes_state_without_approval(admin, message):
    before = state_fingerprint()
    chat(admin, message)
    assert state_fingerprint() == before


@pytest.mark.parametrize("message", ["is the workload fair", "show top risks", "show the approval queue", "who has free capacity",
                                     "who should do TSK-104", "what skill gaps exist", "what if Vikram takes TSK-104"])
def test_staff_chat_cannot_read_team_data(staff, message):
    text = chat(staff, message)["response"]
    others = [e.name for e in STORE.employees if e.name != "Sneha Patel"]
    assert not [name for name in others if name in text], text
    assert "administrator" in text


def test_staff_chat_can_read_own_scores_only(staff):
    assert "Sneha Patel" in chat(staff, "what is the score of Sneha Patel")["response"]
    assert "only view their own" in chat(staff, "what is the score of Vikram Rao")["response"]


def test_admin_chat_keeps_team_answers(admin):
    assert "Gini" in chat(admin, "is the workload fair")["response"]


def test_correct_password_is_refused_while_locked_out():
    for _ in range(10):
        assert client.post("/api/v1/auth/login", json={"username": "kabir", "password": "nope"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "kabir", "password": STAFF_PASSWORD}).status_code == 429


def test_successful_login_clears_failures():
    for _ in range(9):
        client.post("/api/v1/auth/login", json={"username": "kabir", "password": "nope"})
    login("kabir", STAFF_PASSWORD)
    assert client.post("/api/v1/auth/login", json={"username": "kabir", "password": "nope"}).status_code == 401


def test_failed_logins_from_one_address_stop_filling_the_ledger():
    before = len(STORE.ledger.all())
    codes = [client.post("/api/v1/auth/login", json={"username": f"x{i}", "password": "n"}).status_code for i in range(35)]
    assert codes.count(401) == 30 and codes.count(429) == 5
    assert len(STORE.ledger.all()) == before       # an unknown name belongs to no company's ledger


def test_failed_login_for_a_real_account_is_audited():
    before = len(STORE.ledger.all())
    assert client.post("/api/v1/auth/login", json={"username": "kabir", "password": "nope"}).status_code == 401
    assert STORE.ledger.all()[-1].action == "LOGIN_FAILED" and len(STORE.ledger.all()) == before + 1


def test_deactivated_employee_token_stops_working(admin):
    emp = next(e for e in STORE.employees if not any(t.assigned_to == e.id for t in STORE.tasks))
    username = next(u.username for u in STORE.users if u.employee_id == emp.id)
    headers = login(username, STAFF_PASSWORD)
    assert client.get("/api/v1/me/portal", headers=headers).status_code == 200
    assert client.delete(f"/api/v1/employees/{emp.id}", headers=admin).status_code == 200
    assert client.get("/api/v1/me/portal", headers=headers).status_code == 401


def test_role_comes_from_the_account_not_the_token(staff):
    claims = auth.decode_token(staff["Authorization"].split()[1])
    assert claims["role"] == "STAFF"
    body = {**claims, "role": "ADMIN"}
    payload = auth._b64(json.dumps(body, separators=(",", ":")).encode())
    sig = auth._b64(hmac.new(auth._secret(), payload.encode(), hashlib.sha256).digest())
    assert client.get("/api/v1/audit", headers={"Authorization": f"Bearer {payload}.{sig}"}).status_code == 403


def test_non_ascii_token_is_401_not_500():
    bad = TestClient(app, raise_server_exceptions=False)
    assert bad.get("/api/v1/auth/me", headers={"Authorization": "Bearer a.é".encode("latin-1")}).status_code == 401


def test_key_in_database_cannot_forge_tokens_when_env_key_is_set(monkeypatch):
    db.set_meta("token_secret", "stored-in-database")
    monkeypatch.setattr(auth, "_token_secret", b"from-the-environment")
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "admin", "role": "ADMIN", "emp": None, "exp": int(time.time()) + 60}).encode()).decode().rstrip("=")
    sig = auth._b64(hmac.new(b"stored-in-database", payload.encode(), hashlib.sha256).digest())
    assert client.get("/api/v1/audit", headers={"Authorization": f"Bearer {payload}.{sig}"}).status_code == 401


def test_signing_key_required_outside_development(monkeypatch):
    monkeypatch.setenv("VYUHAM_ENV", "production")
    monkeypatch.delenv("AF07_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError):
        auth.check_config()
    monkeypatch.setenv("AF07_SECRET_KEY", "x" * 32)
    auth.check_config()


def test_unknown_environment_is_refused(monkeypatch):
    monkeypatch.setenv("VYUHAM_ENV", "prod")
    with pytest.raises(RuntimeError):
        db.environment()


def test_reset_needs_confirmation_and_admin(admin, staff):
    assert client.post("/api/v1/reset", headers=admin, json={}).status_code == 422
    assert client.post("/api/v1/reset", headers=staff, json={"confirm": "RESET"}).status_code == 403


def test_reset_saves_a_restorable_backup_first(admin):
    db.notify("test", "keep me", "body", audience_role="ADMIN")
    r = client.post("/api/v1/reset", headers=admin, json={"confirm": "RESET"})
    assert r.status_code == 200
    folder = db.BACKUP_DIR / r.json()["backup"]
    if db.DB_URL:
        assert [n for n in json.loads((folder / "notifications.json").read_text(encoding="utf-8")) if n["title"] == "keep me"]
    else:
        saved = sqlite3.connect(folder / "vyuham.db")
        assert saved.execute("SELECT COUNT(*) FROM notifications WHERE title = 'keep me'").fetchone()[0] == 1
        saved.close()
    assert not db.rows("SELECT id FROM notifications WHERE title = 'keep me'")
    second = client.post("/api/v1/reset", headers=admin, json={"confirm": "RESET"}).json()["backup"]
    assert second != r.json()["backup"]


def test_reset_is_refused_outside_development(admin, monkeypatch):
    db.notify("test", "keep me", "body", audience_role="ADMIN")
    monkeypatch.setenv("VYUHAM_ENV", "production")
    assert client.post("/api/v1/reset", headers=admin, json={"confirm": "RESET"}).status_code == 403
    with pytest.raises(PermissionError):
        STORE.reset()
    assert db.rows("SELECT id FROM notifications WHERE title = 'keep me'")


def test_startup_refuses_to_overwrite_data_when_snapshot_is_missing():
    db.notify("test", "keep me", "body", audience_role="ADMIN")
    with db.tx() as c:
        c.execute("DELETE FROM core_state")
    try:
        with pytest.raises(RuntimeError):
            Store()
        assert db.rows("SELECT id FROM notifications WHERE title = 'keep me'")
    finally:
        STORE.save(force=True)


def _isolated_db(monkeypatch, tmp_path, migrations):
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "vyuham.db")
    monkeypatch.setattr(db, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(db, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(db, "MIGRATIONS", migrations)
    monkeypatch.setattr(db, "_initialized", False)


@pytest.mark.skipif(bool(db.DB_URL), reason="SQLite migration runner")
def test_failed_migration_rolls_back_and_a_backup_was_taken(monkeypatch, tmp_path):
    _isolated_db(monkeypatch, tmp_path, ["CREATE TABLE a (id INTEGER PRIMARY KEY);"])
    db.init()
    assert not (tmp_path / "backups").exists()      # nothing to protect on a new database

    monkeypatch.setattr(db, "MIGRATIONS", ["CREATE TABLE a (id INTEGER PRIMARY KEY);", "CREATE TABLE b (id INTEGER); CREATE TABLE a (id INTEGER);"])
    monkeypatch.setattr(db, "_initialized", False)
    with pytest.raises(sqlite3.OperationalError):
        db.init()
    conn = sqlite3.connect(tmp_path / "vyuham.db")
    assert [r[0] for r in conn.execute("SELECT version FROM schema_migrations")] == [1]
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name = 'b'").fetchone()[0] == 0
    conn.close()
    assert len(list((tmp_path / "backups").iterdir())) == 1


def test_security_headers_and_docs_in_development():
    r = client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]


@pytest.mark.skipif(not db.DB_URL, reason="Postgres migration runner")
def test_failed_postgres_migration_rolls_back_and_a_backup_was_taken(monkeypatch, tmp_path):
    from app import pg
    monkeypatch.setattr(db, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(pg, "MIGRATIONS", pg.MIGRATIONS + ["CREATE TABLE half_done (id INTEGER); CREATE TABLE meta (id INTEGER);"])
    with pytest.raises(Exception):
        pg.migrate(db.backup, db.MIGRATION_URL)
    assert db.one("SELECT COUNT(*) AS n FROM schema_migrations WHERE version = ?", (len(pg.MIGRATIONS),))["n"] == 0
    assert db.one("SELECT COUNT(*) AS n FROM pg_tables WHERE tablename = 'half_done' AND schemaname = ?", (db.SCHEMA,))["n"] == 0
    assert len(list((tmp_path / "backups").iterdir())) == 1


@pytest.mark.skipif(not db.DB_URL, reason="Postgres schema")
def test_postgres_schema_has_every_sqlite_column():
    from app import pg
    mem = sqlite3.connect(":memory:")
    for script in db.MIGRATIONS:
        mem.executescript(script)
    for table in db.BUSINESS_TABLES:
        if table == "chunks_fts":
            continue
        ours = {r[1] for r in mem.execute(f"PRAGMA table_info({table})")}
        theirs = {r["column_name"] for r in db.rows("SELECT column_name FROM information_schema.columns WHERE table_schema = ? AND table_name = ?", (db.SCHEMA, table))}
        assert ours <= theirs, table
    mem.close()


@pytest.mark.skipif(not db.DB_URL, reason="Postgres safety guard")
def test_reset_is_refused_on_any_other_supabase_project(admin, monkeypatch):
    monkeypatch.setenv("VYUHAM_DEV_PROJECT_REF", "some-other-project")
    assert client.post("/api/v1/reset", headers=admin, json={"confirm": "RESET"}).status_code == 403


def test_remote_database_requires_an_explicit_environment(monkeypatch):
    monkeypatch.setattr(db, "DB_URL", "postgresql://postgres.ref:pw@host:5432/postgres")
    monkeypatch.delenv("VYUHAM_ENV", raising=False)
    with pytest.raises(RuntimeError):
        db.environment()


def test_malformed_url_is_rejected_without_echoing_the_password():
    from app import pg
    with pytest.raises(RuntimeError) as err:
        pg.open_pool("postgresql://postgres.ref:secret@1234@host:5432/postgres", "vyuham")
    assert "secret" not in str(err.value) and "1234" not in str(err.value)
