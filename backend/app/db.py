"""Persistence: SQLite by default, Supabase Postgres when SUPABASE_DB_URL is set. Versioned migrations and small helpers."""
import json
import os
import shutil
import sqlite3
import re
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlsplit

from .audit import utcnow
from .schema import COMMON, ORG_TABLES

DATA_DIR = Path(os.environ.get("AF07_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DB_PATH = DATA_DIR / "vyuham.db"
UPLOAD_DIR = DATA_DIR / "uploads"
BACKUP_DIR = DATA_DIR / "backups"
DEFAULT_ORG = "ORG-1"
NO_ORG = ""     # a request with no valid token: anything that needs company data fails rather than guessing one
_org: ContextVar[str] = ContextVar("vyuham_org", default=DEFAULT_ORG)
ENVIRONMENTS = ("development", "staging", "production")
DB_URL = os.environ.get("SUPABASE_DB_URL", "").strip()
MIGRATION_URL = os.environ.get("SUPABASE_MIGRATION_DB_URL", "").strip()     # owner login, used only to change the schema
SCHEMA = os.environ.get("VYUHAM_SCHEMA", "vyuham").strip()


def environment() -> str:
    if DB_URL and not os.environ.get("VYUHAM_ENV", "").strip():     # a remote database must never be assumed to be development
        raise RuntimeError("VYUHAM_ENV must be set when SUPABASE_DB_URL is set")
    env = os.environ.get("VYUHAM_ENV", "development").strip().lower()
    if env not in ENVIRONMENTS:
        raise RuntimeError(f"VYUHAM_ENV must be one of {', '.join(ENVIRONMENTS)}")
    return env


def project_ref() -> str:
    """The Supabase project in the connection URL's user name (postgres.<ref>). Not a secret."""
    return (urlsplit(DB_URL).username or "").partition(".")[2]


def require_development(action: str) -> None:
    """Blocks anything that deletes data or seeds demo accounts outside development."""
    if environment() != "development":
        raise PermissionError(f"{action} is only allowed in development (VYUHAM_ENV is {environment()})")
    if DB_URL and project_ref() != os.environ.get("VYUHAM_DEV_PROJECT_REF", "").strip():
        raise PermissionError(f"{action} is refused: this Supabase project is not the one named in VYUHAM_DEV_PROJECT_REF")


def org() -> str:
    return _org.get()


def set_org(value: str):
    return _org.set(value)


def reset_org(handle) -> None:
    _org.reset(handle)


@contextmanager
def as_org(value: str):
    handle = _org.set(value)
    try:
        yield
    finally:
        _org.reset(handle)


_INSERT = re.compile(r"^\s*INSERT INTO (\w+) \(([^)]*)\) VALUES \(", re.IGNORECASE)


def _scoped(sql: str, params: Iterable[Any]) -> tuple:
    """Stamps inserts into company tables with the current organization, so no caller can forget it."""
    params = tuple(params)
    match = _INSERT.match(sql)
    if match and match.group(1) in ORG_TABLES and "org_id" not in match.group(2):
        sql = sql[:match.start(2)] + "org_id, " + sql[match.start(2):match.end()] + "?, " + sql[match.end():]
        params = (org(), *params)
    return sql, params


class _Scoped:
    """Wraps a connection so company inserts are stamped whichever database is in use."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def execute(self, sql: str, params: Iterable[Any] = ()):
        return self._conn.execute(*_scoped(sql, params))

    def executemany(self, sql: str, seq) -> None:
        self._conn.executemany(sql, seq)


def database_label() -> str:
    return "Supabase Postgres" if DB_URL else "SQLite"


MIGRATIONS: List[str] = [
    # 001: core snapshot + document intelligence
    """
    CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE core_state (key TEXT PRIMARY KEY, json TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE documents (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, project_id TEXT NOT NULL, filename TEXT NOT NULL,
        version INTEGER NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL, ext TEXT NOT NULL,
        status TEXT NOT NULL, error TEXT, stored_path TEXT NOT NULL, is_current INTEGER NOT NULL DEFAULT 1,
        chunk_count INTEGER NOT NULL DEFAULT 0, suspicious_count INTEGER NOT NULL DEFAULT 0,
        uploaded_by TEXT NOT NULL, uploaded_at TEXT NOT NULL);
    CREATE INDEX idx_documents_project ON documents(org_id, project_id);
    CREATE TABLE chunks (
        id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        project_id TEXT NOT NULL, seq INTEGER NOT NULL, location TEXT NOT NULL, text TEXT NOT NULL,
        suspicious INTEGER NOT NULL DEFAULT 0);
    CREATE INDEX idx_chunks_document ON chunks(document_id);
    CREATE VIRTUAL TABLE chunks_fts USING fts5(text, chunk_id UNINDEXED, project_id UNINDEXED);
    """,
    # 002: specification, clarifications, plans
    """
    CREATE TABLE project_specs (
        project_id TEXT PRIMARY KEY, analysis_json TEXT NOT NULL, source TEXT NOT NULL, status TEXT NOT NULL,
        approved_by TEXT, approved_at TEXT, updated_at TEXT NOT NULL);
    CREATE TABLE clarifications (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL, question TEXT NOT NULL, why TEXT, options_json TEXT NOT NULL,
        answer TEXT, status TEXT NOT NULL, answered_by TEXT, answered_at TEXT, created_at TEXT NOT NULL,
        UNIQUE(project_id, question));
    CREATE TABLE plans (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL, version INTEGER NOT NULL, plan_json TEXT NOT NULL,
        source TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL,
        approved_by TEXT, approved_at TEXT, UNIQUE(project_id, version));
    """,
    # 003: workforce intelligence
    """
    CREATE TABLE profiles (employee_id TEXT PRIMARY KEY, json TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE resumes (
        id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, filename TEXT NOT NULL, stored_path TEXT NOT NULL,
        extracted_json TEXT NOT NULL, assessment_json TEXT NOT NULL, source TEXT NOT NULL, uploaded_at TEXT NOT NULL);
    CREATE TABLE skill_assessments (
        id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, skill TEXT NOT NULL, score REAL, confidence TEXT NOT NULL,
        evidence_json TEXT NOT NULL, missing_json TEXT NOT NULL, evaluated_at TEXT NOT NULL, is_current INTEGER NOT NULL DEFAULT 1);
    CREATE INDEX idx_skill_assess ON skill_assessments(employee_id, is_current);
    CREATE TABLE skill_challenges (
        id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, skill TEXT NOT NULL, reason TEXT NOT NULL, status TEXT NOT NULL,
        resolution TEXT, resolved_by TEXT, created_at TEXT NOT NULL);
    CREATE TABLE professional_links (
        id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, provider TEXT NOT NULL, url TEXT, handle TEXT, status TEXT NOT NULL,
        status_detail TEXT, data_json TEXT NOT NULL DEFAULT '{}', last_checked TEXT, UNIQUE(employee_id, provider));
    """,
    # 004: progress, assistant, notifications, usage
    """
    CREATE TABLE progress_updates (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL, reported_pct REAL NOT NULL, note TEXT, reported_by TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE progress_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL, verified_pct REAL NOT NULL, in_progress_pct REAL NOT NULL,
        blocked_pct REAL NOT NULL, pending_pct REAL NOT NULL, created_at TEXT NOT NULL);
    CREATE INDEX idx_snapshots_project ON progress_snapshots(project_id);
    CREATE TABLE conversations (
        id TEXT PRIMARY KEY, username TEXT NOT NULL, title TEXT NOT NULL, project_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
    CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        role TEXT NOT NULL, content TEXT NOT NULL, meta_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL);
    CREATE TABLE pending_actions (
        id TEXT PRIMARY KEY, conversation_id TEXT, username TEXT NOT NULL, action TEXT NOT NULL, args_json TEXT NOT NULL,
        summary TEXT NOT NULL, status TEXT NOT NULL, result_json TEXT, created_at TEXT NOT NULL, decided_at TEXT);
    CREATE TABLE change_requests (
        id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, kind TEXT NOT NULL, task_id TEXT, details TEXT NOT NULL, status TEXT NOT NULL,
        resolution TEXT, resolved_by TEXT, created_at TEXT NOT NULL);
    CREATE TABLE notifications (
        id TEXT PRIMARY KEY, audience_role TEXT, audience_user TEXT, kind TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
        link_view TEXT, link_id TEXT, is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
    CREATE TABLE ai_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT, feature TEXT NOT NULL, model TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER,
        ok INTEGER NOT NULL, error TEXT, created_at TEXT NOT NULL);
    """,
]

COMPANY_ONLY_TABLES = ["onboarding_messages", "skill_requests", "skill_manual_scores", "project_transitions", "room_members", "room_attachments", "room_messages",
                       "project_rooms", "project_decisions", "action_items", "meeting_minutes", "project_budgets", "cost_rates", "cost_entries", "idempotency_keys"]
BUSINESS_TABLES = ["chunks_fts", "chunks", "documents", "project_specs", "clarifications", "plans", "profiles", "resumes",
                   "skill_assessments", "skill_challenges", "professional_links", "progress_updates", "progress_snapshots",
                   "messages", "conversations", "pending_actions", "change_requests", "notifications", "ai_usage"]

MIGRATIONS = MIGRATIONS + COMMON
_local = threading.local()
_init_lock = threading.Lock()
_initialized = False


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_conn() -> sqlite3.Connection:
    init()
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _local.conn = _connect()
    return conn


def init() -> None:
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        environment()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        if DB_URL:
            from . import pg
            pg.open_pool(DB_URL, SCHEMA)
            pg.migrate(backup, MIGRATION_URL)
            _initialized = True
            return
        conn = _connect()
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
            pending = [(v, s) for v, s in enumerate(MIGRATIONS, start=1) if v not in applied]
            if applied and pending:     # a new database has nothing to protect
                backup("pre-migration")
            for version, script in pending:
                # The version row commits with the migration, so a crash cannot leave them out of step.
                conn.executescript(f"BEGIN;\n{script}\nINSERT INTO schema_migrations VALUES ({version}, '{utcnow()}');\nCOMMIT;")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        _initialized = True


def backup(reason: str) -> Path:
    """Copies the database and uploads to a new folder. Safe while the server runs; never overwrites."""
    stamp = utcnow().replace(":", "").replace("-", "")
    dest = BACKUP_DIR / f"{stamp}-{uuid.uuid4().hex[:6]}-{reason}"
    dest.mkdir(parents=True)
    if DB_URL:
        from . import pg
        pg.dump_tables(dest)
    else:
        source, target = sqlite3.connect(DB_PATH), sqlite3.connect(dest / "vyuham.db")
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
    if UPLOAD_DIR.exists():
        shutil.copytree(UPLOAD_DIR, dest / "uploads")
    return dest


def has_business_data() -> bool:
    return any(one(f"SELECT 1 AS found FROM {table} WHERE org_id = ? LIMIT 1", (org(),)) for table in BUSINESS_TABLES if table != "chunks_fts")


@contextmanager
def tx():
    if DB_URL:
        init()
        from . import pg
        with pg.transaction() as session:
            yield _Scoped(session)
        return
    conn = get_conn()
    try:
        yield _Scoped(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


@contextmanager
def _reader():
    if DB_URL:
        init()
        from . import pg
        with pg.session() as session:
            yield session
        return
    yield get_conn()


def rows(sql: str, params: Iterable[Any] = ()) -> List[Dict]:
    with _reader() as c:
        return [dict(r) for r in c.execute(sql, tuple(params)).fetchall()]


def one(sql: str, params: Iterable[Any] = ()) -> Optional[Dict]:
    with _reader() as c:
        r = c.execute(sql, tuple(params)).fetchone()
        return dict(r) if r else None


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def ordered_id(prefix: str) -> str:
    """Sorts by creation time, for records shown in sequence."""
    return f"{prefix}-{time.time_ns():020d}-{uuid.uuid4().hex[:6]}"


def get_meta(key: str) -> Optional[str]:
    r = one("SELECT value FROM meta WHERE key = ?", (key,))
    return r["value"] if r else None


def set_meta(key: str, value: str) -> None:
    with tx() as c:
        c.execute("INSERT INTO meta VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


def clear_business_data() -> None:
    """Removes this organization's records and files. Other organizations are untouched."""
    current = org()
    stored = [r["stored_path"] for t in ("documents", "resumes", "room_attachments") for r in rows(f"SELECT stored_path FROM {t} WHERE org_id = ?", (current,))]
    with tx() as c:
        c.execute("DELETE FROM chunks_fts WHERE chunk_id IN (SELECT id FROM chunks WHERE org_id = ?)", (current,))
        for table in COMPANY_ONLY_TABLES + BUSINESS_TABLES:
            if table != "chunks_fts":
                c.execute(f"DELETE FROM {table} WHERE org_id = ?", (current,))
    for path in stored:
        Path(path).unlink(missing_ok=True)


def add_account(username: str, organization: Optional[str] = None) -> None:
    with tx() as c:
        c.execute("INSERT INTO accounts (username, org_id, created_at) VALUES (?, ?, ?) ON CONFLICT(username) DO NOTHING", (username, organization or org(), utcnow()))


def account_org(username: str) -> Optional[str]:
    row = one("SELECT org_id FROM accounts WHERE username = ?", (username.lower().strip(),))
    return row["org_id"] if row else None


def notify(kind: str, title: str, body: str, audience_role: Optional[str] = None, audience_user: Optional[str] = None,
           link_view: Optional[str] = None, link_id: Optional[str] = None) -> None:
    with tx() as c:
        c.execute("INSERT INTO notifications (id, audience_role, audience_user, kind, title, body, link_view, link_id, created_at) "
                  "VALUES (?,?,?,?,?,?,?,?,?)",
                  (new_id("NTF"), audience_role, audience_user, kind, title, body, link_view, link_id, utcnow()))


def dumps(value: Any) -> str:
    return json.dumps(value, default=str)
