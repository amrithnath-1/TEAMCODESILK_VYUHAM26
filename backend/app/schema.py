"""Schema shared by SQLite and Postgres. Types stay in the subset both accept; money is BIGINT minor units."""

_ORG_COLUMN_TABLES = ["core_state", "chunks", "project_specs", "clarifications", "plans", "profiles", "resumes", "skill_assessments",
                      "skill_challenges", "professional_links", "progress_updates", "progress_snapshots", "conversations", "messages",
                      "pending_actions", "change_requests", "notifications", "ai_usage"]

# Every table an INSERT should stamp with the current organization. See db._scoped.
ORG_TABLES = set(_ORG_COLUMN_TABLES) | {"documents"}

_ADD_ORG = "\n".join(f"ALTER TABLE {t} ADD COLUMN org_id TEXT NOT NULL DEFAULT 'ORG-1';" for t in _ORG_COLUMN_TABLES)

COMPANIES = _ADD_ORG + """
CREATE INDEX idx_notifications_org ON notifications(org_id);
CREATE INDEX idx_conversations_org ON conversations(org_id, username);
ALTER TABLE conversations ADD COLUMN status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE conversations ADD COLUMN summary TEXT;
ALTER TABLE conversations ADD COLUMN summary_through BIGINT NOT NULL DEFAULT 0;

CREATE TABLE organizations (
    id TEXT PRIMARY KEY, seq INTEGER NOT NULL UNIQUE, name TEXT NOT NULL, onboarding_state TEXT NOT NULL,
    profile_json TEXT NOT NULL DEFAULT '{}', currency TEXT, created_by TEXT NOT NULL, created_at TEXT NOT NULL, onboarded_at TEXT);
INSERT INTO organizations (id, seq, name, onboarding_state, created_by, created_at, onboarded_at)
    VALUES ('ORG-1', 0, 'Demo Enterprise', 'complete', 'SYSTEM', '2026-10-30T00:00:00Z', '2026-10-30T00:00:00Z');
CREATE TABLE accounts (username TEXT PRIMARY KEY, org_id TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX idx_accounts_org ON accounts(org_id);
CREATE TABLE onboarding_messages (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX idx_onboarding_org ON onboarding_messages(org_id);
CREATE TABLE invitations (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE, email TEXT, role TEXT NOT NULL, created_by TEXT NOT NULL,
    created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used_by TEXT, used_at TEXT, revoked_at TEXT);
CREATE INDEX idx_invitations_org ON invitations(org_id);
CREATE TABLE idempotency_keys (
    org_id TEXT NOT NULL, key TEXT NOT NULL, path TEXT NOT NULL, status INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY (org_id, key, path));
"""

SKILLS_AND_LIFECYCLE = """
CREATE TABLE skill_requests (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, employee_id TEXT NOT NULL, skill TEXT NOT NULL, kind TEXT NOT NULL, requested_score DOUBLE PRECISION,
    explanation TEXT NOT NULL, evidence TEXT, status TEXT NOT NULL, reviewer TEXT, review_notes TEXT, created_at TEXT NOT NULL, reviewed_at TEXT);
CREATE INDEX idx_skill_requests_org ON skill_requests(org_id, status);
CREATE TABLE skill_manual_scores (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, employee_id TEXT NOT NULL, skill TEXT NOT NULL, score DOUBLE PRECISION NOT NULL, confidence TEXT NOT NULL,
    reason TEXT NOT NULL, evidence TEXT, evaluator TEXT NOT NULL, evaluated_at TEXT NOT NULL, source_request TEXT);
CREATE INDEX idx_skill_manual_employee ON skill_manual_scores(org_id, employee_id, skill);
CREATE TABLE project_transitions (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, project_id TEXT NOT NULL, from_stage TEXT, to_stage TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX idx_transitions_project ON project_transitions(org_id, project_id);
"""

ROOMS = """
CREATE TABLE project_rooms (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, project_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX idx_rooms_org ON project_rooms(org_id);
CREATE TABLE room_members (
    room_id TEXT NOT NULL, org_id TEXT NOT NULL, username TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL, joined_at TEXT NOT NULL, removed_at TEXT,
    PRIMARY KEY (room_id, username));
CREATE TABLE room_messages (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, room_id TEXT NOT NULL, username TEXT NOT NULL, display_name TEXT NOT NULL, content TEXT NOT NULL, kind TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX idx_room_messages ON room_messages(org_id, room_id, id);
CREATE TABLE room_attachments (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, room_id TEXT NOT NULL, message_id TEXT, filename TEXT NOT NULL, ext TEXT NOT NULL, size BIGINT NOT NULL, sha256 TEXT NOT NULL,
    stored_path TEXT NOT NULL, status TEXT NOT NULL, uploaded_by TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX idx_room_attachments ON room_attachments(org_id, room_id);
CREATE TABLE meeting_minutes (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, room_id TEXT NOT NULL, project_id TEXT NOT NULL, title TEXT NOT NULL, raw_text TEXT NOT NULL, extracted_json TEXT NOT NULL,
    source TEXT NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL, approved_by TEXT, approved_at TEXT);
CREATE INDEX idx_minutes_project ON meeting_minutes(org_id, project_id);
CREATE TABLE project_decisions (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, project_id TEXT NOT NULL, minutes_id TEXT, text TEXT NOT NULL, approved_by TEXT NOT NULL, approved_at TEXT NOT NULL);
CREATE INDEX idx_decisions_project ON project_decisions(org_id, project_id);
CREATE TABLE action_items (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, project_id TEXT NOT NULL, minutes_id TEXT, text TEXT NOT NULL, owner TEXT, due TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX idx_action_items_project ON action_items(org_id, project_id);
"""

BUDGETS = """
CREATE TABLE project_budgets (
    project_id TEXT PRIMARY KEY, org_id TEXT NOT NULL, currency TEXT NOT NULL, total_minor BIGINT NOT NULL, labor_minor BIGINT, non_labor_minor BIGINT NOT NULL DEFAULT 0,
    reserve_minor BIGINT NOT NULL DEFAULT 0, includes_tax INTEGER NOT NULL DEFAULT 0, hard_limit INTEGER NOT NULL DEFAULT 0, updated_by TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE cost_rates (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, employee_id TEXT, role_name TEXT, project_id TEXT, currency TEXT NOT NULL, hourly_minor BIGINT NOT NULL,
    approved_by TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX idx_cost_rates_org ON cost_rates(org_id, employee_id);
CREATE TABLE cost_entries (
    id TEXT PRIMARY KEY, org_id TEXT NOT NULL, project_id TEXT NOT NULL, task_id TEXT, kind TEXT NOT NULL, amount_minor BIGINT NOT NULL, currency TEXT NOT NULL,
    note TEXT, hours DOUBLE PRECISION, created_by TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX idx_cost_entries_project ON cost_entries(org_id, project_id);
"""

COMMON = [COMPANIES, SKILLS_AND_LIFECYCLE, ROOMS, BUDGETS]

# Org-scoped tables that RLS protects on Postgres. accounts and invitations are read before login, so see PG_RLS.
RLS_TABLES = _ORG_COLUMN_TABLES + [
    "documents", "chunks_fts", "onboarding_messages", "idempotency_keys", "skill_requests", "skill_manual_scores", "project_transitions",
    "project_rooms", "room_members", "room_messages", "room_attachments", "meeting_minutes", "project_decisions", "action_items",
    "project_budgets", "cost_rates", "cost_entries",
]


def pg_rls() -> str:
    """Postgres only. The app role is bound to the organization set on its connection; owners and BYPASSRLS roles are not."""
    parts = ["ALTER TABLE chunks_fts ADD COLUMN org_id TEXT NOT NULL DEFAULT current_setting('app.org_id', true);"]
    for table in RLS_TABLES:
        parts.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        parts.append(f"CREATE POLICY org_isolation ON {table} USING (org_id = current_setting('app.org_id', true)) "
                     f"WITH CHECK (org_id = current_setting('app.org_id', true));")
    parts.append("""
    ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
    CREATE POLICY org_self ON organizations USING (id = current_setting('app.org_id', true)) WITH CHECK (id = current_setting('app.org_id', true));
    CREATE POLICY org_register ON organizations FOR INSERT WITH CHECK (current_setting('app.org_id', true) = '' OR id = current_setting('app.org_id', true));
    CREATE POLICY org_next_seq ON organizations FOR SELECT USING (current_setting('app.org_id', true) = '');
    ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
    CREATE POLICY accounts_lookup ON accounts FOR SELECT USING (true);
    CREATE POLICY accounts_write ON accounts FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true));
    ALTER TABLE invitations ENABLE ROW LEVEL SECURITY;
    CREATE POLICY invitation_lookup ON invitations FOR SELECT USING (true);
    CREATE POLICY invitation_insert ON invitations FOR INSERT WITH CHECK (org_id = current_setting('app.org_id', true));
    CREATE POLICY invitation_update ON invitations FOR UPDATE USING (org_id = current_setting('app.org_id', true)) WITH CHECK (org_id = current_setting('app.org_id', true));
    """)
    # The app role reads and writes through these policies. It owns nothing and cannot bypass them; Supabase's API roles get nothing here.
    parts.append("""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vyuham_app') THEN
            EXECUTE format('GRANT USAGE ON SCHEMA %I TO vyuham_app', current_schema());
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO vyuham_app', current_schema());
            EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO vyuham_app', current_schema());
            EXECUTE format('REVOKE INSERT, UPDATE, DELETE ON schema_migrations FROM vyuham_app');
        END IF;
    END $$;
    """)
    return "\n".join(parts)
