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

CORE_RECORDS = """
CREATE TABLE org_settings (
    org_id TEXT PRIMARY KEY, weights_json TEXT NOT NULL, counters_json TEXT NOT NULL, processed_event_keys_json TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE team_roles (
    org_id TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, department TEXT NOT NULL, role_eval_weights TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, id));
CREATE TABLE employees (
    org_id TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL, department TEXT NOT NULL, designation TEXT NOT NULL, manager TEXT NOT NULL, team_role_id TEXT NOT NULL,
    years_exp DOUBLE PRECISION NOT NULL, weekly_capacity_hrs DOUBLE PRECISION NOT NULL, committed_hrs DOUBLE PRECISION NOT NULL, meeting_hrs DOUBLE PRECISION NOT NULL, leave_hrs DOUBLE PRECISION NOT NULL,
    status TEXT NOT NULL, delivery_completion_rate DOUBLE PRECISION NOT NULL, work_quality_acceptance_rate DOUBLE PRECISION NOT NULL, deadline_reliability_rate DOUBLE PRECISION NOT NULL,
    collaboration_review_score DOUBLE PRECISION NOT NULL, learning_improvement_score DOUBLE PRECISION NOT NULL, preferred_tasks TEXT NOT NULL, learning_goals TEXT NOT NULL,
    sufficient_evidence INTEGER NOT NULL, dispute_status TEXT NOT NULL, dispute_note TEXT, availability TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, id));
CREATE INDEX idx_employees_status ON employees(org_id, status);
CREATE TABLE employee_skills (
    org_id TEXT NOT NULL, employee_id TEXT NOT NULL, skill_name TEXT NOT NULL, level TEXT NOT NULL, is_verified INTEGER NOT NULL, evidence_source TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, employee_id, skill_name),
    FOREIGN KEY (org_id, employee_id) REFERENCES employees(org_id, id) ON DELETE CASCADE);
CREATE INDEX idx_employee_skills_skill ON employee_skills(org_id, skill_name);
CREATE TABLE projects (
    org_id TEXT NOT NULL, id TEXT NOT NULL, name TEXT NOT NULL, business_objective TEXT NOT NULL, priority TEXT NOT NULL, deadline_days INTEGER NOT NULL, status TEXT NOT NULL, created_by TEXT NOT NULL,
    start_date TEXT, manager_usernames TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, id));
CREATE TABLE tasks (
    org_id TEXT NOT NULL, id TEXT NOT NULL, project_id TEXT NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, estimated_hours DOUBLE PRECISION NOT NULL, priority TEXT NOT NULL, deadline_days INTEGER NOT NULL,
    deliverable_criteria TEXT NOT NULL, status TEXT NOT NULL, assigned_to TEXT, progress_pct INTEGER NOT NULL, phase TEXT, milestone TEXT, complexity INTEGER NOT NULL, acceptance_criteria TEXT NOT NULL, deliverables TEXT NOT NULL,
    subtasks TEXT NOT NULL, suggested_assignee TEXT, blocked INTEGER NOT NULL, blocked_reason TEXT, plan_id TEXT, activity TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, id),
    FOREIGN KEY (org_id, project_id) REFERENCES projects(org_id, id),
    FOREIGN KEY (org_id, assigned_to) REFERENCES employees(org_id, id));
CREATE INDEX idx_tasks_project ON tasks(org_id, project_id);
CREATE INDEX idx_tasks_assignee ON tasks(org_id, assigned_to);
CREATE TABLE task_required_skills (
    org_id TEXT NOT NULL, task_id TEXT NOT NULL, skill_name TEXT NOT NULL, level TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, task_id, skill_name),
    FOREIGN KEY (org_id, task_id) REFERENCES tasks(org_id, id) ON DELETE CASCADE);
CREATE TABLE task_dependencies (
    org_id TEXT NOT NULL, task_id TEXT NOT NULL, depends_on TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, task_id, depends_on),
    FOREIGN KEY (org_id, task_id) REFERENCES tasks(org_id, id) ON DELETE CASCADE);
CREATE TABLE task_assignments (
    org_id TEXT NOT NULL, id TEXT NOT NULL, task_id TEXT NOT NULL, employee_id TEXT NOT NULL, suitability_score DOUBLE PRECISION NOT NULL, factor_breakdown TEXT NOT NULL, explanation_rationale TEXT NOT NULL,
    tradeoffs_flagged TEXT NOT NULL, status TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, id));
CREATE INDEX idx_assignments_task ON task_assignments(org_id, task_id);
CREATE INDEX idx_assignments_employee ON task_assignments(org_id, employee_id);
CREATE TABLE deliverables (
    org_id TEXT NOT NULL, id TEXT NOT NULL, task_id TEXT NOT NULL, employee_id TEXT NOT NULL, accepted INTEGER NOT NULL, rework_count INTEGER NOT NULL, complexity_weight DOUBLE PRECISION NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, id));
CREATE TABLE integration_events (
    org_id TEXT NOT NULL, id TEXT NOT NULL, employee_id TEXT NOT NULL, source_system TEXT NOT NULL, external_id TEXT NOT NULL, pr_review_score DOUBLE PRECISION, defect_rate DOUBLE PRECISION, summary TEXT NOT NULL, received_at TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, id));
CREATE TABLE agent_decisions (
    org_id TEXT NOT NULL, id TEXT NOT NULL, agent_name TEXT NOT NULL, trigger_event TEXT NOT NULL, shortlist TEXT NOT NULL, recommended_action TEXT NOT NULL, risk_level TEXT NOT NULL, requires_approval INTEGER NOT NULL, created_at TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, id));
CREATE TABLE approvals (
    org_id TEXT NOT NULL, approval_id TEXT NOT NULL, decision_id TEXT NOT NULL, kind TEXT NOT NULL, task_id TEXT NOT NULL, task_title TEXT NOT NULL, priority TEXT NOT NULL, previous_owner TEXT, previous_owner_id TEXT,
    recommended_new_owner_id TEXT, recommended_new_owner_name TEXT, suitability_score DOUBLE PRECISION NOT NULL, post_utilization_pct DOUBLE PRECISION NOT NULL, explanation TEXT NOT NULL, shortlist TEXT NOT NULL, status TEXT NOT NULL,
    manager_comments TEXT, created_at TEXT NOT NULL, decided_at TEXT, decided_by TEXT, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, approval_id));
CREATE INDEX idx_approvals_status ON approvals(org_id, status);
CREATE TABLE org_users (
    org_id TEXT NOT NULL, username TEXT NOT NULL, display_name TEXT NOT NULL, role TEXT NOT NULL, employee_id TEXT, password_hash TEXT NOT NULL, salt TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, username));
CREATE TABLE audit_log (
    org_id TEXT NOT NULL, id TEXT NOT NULL, timestamp TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL, entity_id TEXT NOT NULL, details TEXT NOT NULL, prev_hash TEXT NOT NULL, sha256_proof TEXT NOT NULL, seq INTEGER NOT NULL,
    PRIMARY KEY (org_id, id));
CREATE INDEX idx_audit_entity ON audit_log(org_id, entity_id);
"""

COMMON = [COMPANIES, SKILLS_AND_LIFECYCLE, ROOMS, BUDGETS, CORE_RECORDS]
# Postgres numbers its migrations separately, and row-level security came between these two groups.
EARLY_COMMON = COMMON[:-1]

# Org-scoped tables that RLS protects on Postgres. accounts and invitations are read before login, so see PG_RLS.
_FIRST_RLS_TABLES = _ORG_COLUMN_TABLES + [
    "documents", "chunks_fts", "onboarding_messages", "idempotency_keys", "skill_requests", "skill_manual_scores", "project_transitions",
    "project_rooms", "room_members", "room_messages", "room_attachments", "meeting_minutes", "project_decisions", "action_items",
    "project_budgets", "cost_rates", "cost_entries",
]
CORE_TABLES = ["org_settings", "team_roles", "employees", "employee_skills", "projects", "tasks", "task_required_skills", "task_dependencies", "task_assignments", "deliverables",
               "integration_events", "agent_decisions", "approvals", "org_users", "audit_log"]
RLS_TABLES = _FIRST_RLS_TABLES + CORE_TABLES
_GRANTS = """
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vyuham_app') THEN
            EXECUTE format('GRANT USAGE ON SCHEMA %I TO vyuham_app', current_schema());
            EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO vyuham_app', current_schema());
            EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO vyuham_app', current_schema());
            EXECUTE format('REVOKE INSERT, UPDATE, DELETE ON schema_migrations FROM vyuham_app');
            %s
        END IF;
    END $$;
    """


def _policies(tables) -> list:
    parts = []
    for table in tables:
        parts.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        parts.append(f"CREATE POLICY org_isolation ON {table} USING (org_id = current_setting('app.org_id', true)) "
                     f"WITH CHECK (org_id = current_setting('app.org_id', true));")
    return parts


def pg_core_rls() -> str:
    """The app can add audit entries and clear them on a development reset, but never rewrite one."""
    return "\n".join(_policies(CORE_TABLES) + [_GRANTS.replace("%s", "EXECUTE 'REVOKE UPDATE ON audit_log FROM vyuham_app';")])


def pg_rls() -> str:
    """Postgres only. The app role is bound to the organization set on its connection; owners and BYPASSRLS roles are not."""
    parts = ["ALTER TABLE chunks_fts ADD COLUMN org_id TEXT NOT NULL DEFAULT current_setting('app.org_id', true);"]
    parts += _policies(_FIRST_RLS_TABLES)
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
    parts.append(_GRANTS.replace("%s", ""))
    return "\n".join(parts)
