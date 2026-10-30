"""Row-level security on Postgres: these talk to the database directly, under the app's restricted role, to prove isolation holds even if application code forgets a filter."""
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import db, pg
from app.main import app
from app.schema import RLS_TABLES
from app.state import STORE

pytestmark = pytest.mark.skipif(not db.DB_URL, reason="Needs Postgres")
client = TestClient(app)
PASSWORD = "correct-horse-battery"


def company(name):
    r = client.post("/api/v1/org/register", json={"company_name": name, "admin_name": "Olga Owner", "email": f"o-{uuid.uuid4().hex[:8]}@x.test", "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]["org_id"]


def activity(headers):
    pid = client.post("/api/v1/projects/draft", headers=headers, json={"name": "Secret", "objective": "", "priority": "High", "deadline_days": 30}).json()["id"]
    client.post("/api/v1/assistant/chat", headers=headers, json={"message": "hello there"})
    client.put(f"/api/v1/projects/{pid}/budget", headers=headers, json={"currency": "USD", "total_minor": 1000})
    client.post(f"/api/v1/projects/{pid}/room/minutes", headers=headers, json={"text": "Decision: use the secret plan"})
    return pid


def test_the_app_role_is_restricted():
    with pg.session() as s:
        row = s.execute("SELECT rolbypassrls, rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user").fetchone()
        assert s.execute("SELECT current_user").fetchone()[0] == "vyuham_app"
        assert tuple(row.values_) == (False, False, False, False)
        assert s.execute("SELECT has_schema_privilege(current_schema(), 'CREATE')").fetchone()[0] is False


def test_supabase_api_roles_cannot_reach_the_schema():
    with pg.session() as s:
        for role in ("anon", "authenticated"):
            assert s.execute("SELECT has_schema_privilege(?, ?, 'USAGE')", (role, db.SCHEMA)).fetchone()[0] is False


def test_every_company_table_has_rls_turned_on():
    with psycopg.connect(db.MIGRATION_URL, autocommit=True, prepare_threshold=None) as owner:
        rows = dict(owner.execute("SELECT c.relname, c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = %s AND c.relkind = 'r'", (db.SCHEMA,)).fetchall())
    for table in RLS_TABLES + ["organizations", "accounts", "invitations"]:
        assert rows[table] is True, table


def test_one_company_cannot_read_another_without_any_filter():
    a, org_a = company("Alpha")
    b, org_b = company("Beta")
    activity(a)
    activity(b)
    for org_id, other in ((org_a, org_b), (org_b, org_a)):
        with db.as_org(org_id), pg.session() as s:
            for table in RLS_TABLES:
                assert s.execute(f'SELECT COUNT(*) FROM "{table}" WHERE org_id = ?', (other,)).fetchone()[0] == 0, table
            assert s.execute("SELECT COUNT(*) FROM org_settings WHERE org_id = ?", (org_id,)).fetchone()[0] == 1
            assert s.execute("SELECT COUNT(*) FROM organizations").fetchone()[0] == 1
    with db.as_org(org_a), pg.session() as s:
        seen = s.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        assert seen >= 1


def test_no_company_context_sees_nothing():
    a, _ = company("Alpha")
    activity(a)
    with db.as_org(db.NO_ORG), pg.session() as s:
        for table in RLS_TABLES:
            assert s.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == 0, table


def test_writes_for_another_company_are_rejected():
    _, org_a = company("Alpha")
    b, org_b = company("Beta")
    pid = activity(b)
    with db.as_org(org_a), pg.session() as s:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            s.execute("INSERT INTO notifications (id, org_id, kind, title, body, created_at) VALUES (?,?,?,?,?,?)", ("NTF-x", org_b, "k", "t", "b", "now"))
        s.execute("UPDATE project_budgets SET total_minor = 1 WHERE project_id = ?", (pid,))
    with db.as_org(org_b):
        assert db.one("SELECT total_minor FROM project_budgets WHERE project_id = ?", (pid,))["total_minor"] == 1000


def test_app_role_cannot_change_the_schema_or_policies():
    with pg.session() as s:
        for statement in ("DROP TABLE notifications", "ALTER TABLE notifications DISABLE ROW LEVEL SECURITY", "CREATE TABLE sneaky (id INT)", "DROP POLICY org_isolation ON notifications"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                s.conn.execute(statement)


def test_migration_history_cannot_be_rewritten_by_the_app():
    with pg.session() as s:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            s.execute("DELETE FROM schema_migrations")
