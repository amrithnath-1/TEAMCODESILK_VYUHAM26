"""Gives the demo company a clean start: one administrator and one project under AI evaluation, with no employees, tasks or invented progress.

Usage, from backend/, with SUPABASE_MIGRATION_DB_URL set:
  python -m scripts.prepare_demo_company                     lists what would change, and changes nothing
  python -m scripts.prepare_demo_company --apply --remove "Test Retail Software"

Only the demo company and companies named with --remove are touched. Every other company stays exactly as it is.
It backs up every company to a new folder first and stops if that fails. The running backend must be restarted afterwards.
"""
import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from app import db

DEMO_NAME = "VYUHAM Demo Company"
ADMIN_NAME = "Demo Administrator"
PROJECT = ("Retail Ordering Portal", "Launch an online ordering portal for retail customers.", "High", 56)
BRIEF = pathlib.Path(__file__).resolve().parents[2] / "docs/samples/requirements.docx"
BACKUPS = pathlib.Path.home() / "VYUHAM_backups"


def backup(owner) -> pathlib.Path:
    dest = BACKUPS / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-before-demo-reset"
    dest.mkdir(parents=True, exist_ok=False)
    tables = [r["tablename"] for r in owner.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s", (db.SCHEMA,)).fetchall()]
    total = 0
    for table in tables:
        rows = owner.execute(f'SELECT * FROM "{db.SCHEMA}"."{table}"').fetchall()
        (dest / f"{table}.json").write_text(json.dumps(rows, default=str), encoding="utf-8")
        total += len(rows)
    (dest / "MANIFEST.json").write_text(json.dumps({"tables": len(tables), "rows": total, "schema": db.SCHEMA}), encoding="utf-8")
    for table in tables:
        saved = json.loads((dest / f"{table}.json").read_text(encoding="utf-8"))
        live = owner.execute(f'SELECT count(*) AS n FROM "{db.SCHEMA}"."{table}"').fetchone()["n"]
        if len(saved) != live:
            raise SystemExit(f"Backup check failed on {table}. Nothing was changed.")
    print(f"Backup: {dest} ({len(tables)} tables, {total} rows)")
    return dest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--remove", action="append", default=[], help="exact name of another company to delete")
    args = parser.parse_args()
    if not (db.DB_URL and db.MIGRATION_URL):
        print("This needs SUPABASE_DB_URL and SUPABASE_MIGRATION_DB_URL.")
        return 1
    try:
        db.require_development("Preparing the demo company")
    except PermissionError as exc:
        print(exc)
        return 1
    with psycopg.connect(db.MIGRATION_URL, autocommit=True, prepare_threshold=None, row_factory=dict_row, connect_timeout=30) as owner:
        companies = owner.execute(f'SELECT id, name FROM "{db.SCHEMA}".organizations ORDER BY seq').fetchall()
        removing = [c for c in companies if c["name"] in args.remove and c["id"] != db.DEFAULT_ORG]
        unknown = set(args.remove) - {c["name"] for c in removing}
        if unknown:
            print(f"No such company: {', '.join(sorted(unknown))}. Nothing was changed.")
            return 1
        for c in companies:
            action = "RESET" if c["id"] == db.DEFAULT_ORG else "DELETE" if c in removing else "keep"
            print(f"  {action:6} {c['name']}")
        if not args.apply:
            print("Nothing changed. Add --apply to do this.")
            return 0
        backup(owner)
        from app import documents, services
        from app.models import WeightConfig
        from app.state import STORE, Store
        for c in removing:
            with db.as_org(c["id"]):
                db.clear_business_data()
            for table, column in (("accounts", "org_id"), ("invitations", "org_id"), ("organizations", "id")):
                owner.execute(f'DELETE FROM "{db.SCHEMA}"."{table}" WHERE {column} = %s', (c["id"],))
        store = STORE._for(db.DEFAULT_ORG)
        with store.lock:
            admin = next(u for u in store.users if u.username == "admin")     # keeps its existing private password
            admin.display_name, admin.employee_id, admin.role = ADMIN_NAME, None, "OWNER"
            db.clear_business_data()
            owner.execute(f'DELETE FROM "{db.SCHEMA}".accounts WHERE org_id = %s AND username <> %s', (db.DEFAULT_ORG, admin.username))
            owner.execute(f'DELETE FROM "{db.SCHEMA}".invitations WHERE org_id = %s', (db.DEFAULT_ORG,))
            owner.execute(f'UPDATE "{db.SCHEMA}".organizations SET name = %s, onboarding_state = %s WHERE id = %s', (DEMO_NAME, "complete", db.DEFAULT_ORG))
            store.users, store.employees, store.tasks, store.projects, store.roles = [admin], [], [], [], []
            store.deliverables, store.integration_events, store.approvals, store.decisions, store.assignments = [], [], [], [], []
            store.processed_event_keys, store.weights = set(), WeightConfig()
            store.ledger.reset()
            store.ledger.record("SYSTEM_INIT", "DEMO_COMPANY_PREPARED", db.DEFAULT_ORG, {"administrators": 1, "employees": 0})
            store._rows, store._saved_digest = {}, None
            store.save(force=True)
        project = services.create_draft_project(*PROJECT, admin.username)
        doc = documents.store_upload(project["id"], BRIEF.name, BRIEF.read_bytes(), admin.username)
        documents.process(doc["id"])
        store.save(force=True)
        print(f"Prepared {DEMO_NAME}: 1 administrator, project {project['id']}.")
    from app import pg
    pg.close_pool()
    return 0


if __name__ == "__main__":
    sys.exit(main())
