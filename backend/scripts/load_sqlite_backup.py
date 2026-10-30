"""Copies a SQLite backup into the empty Supabase schema, then checks every row count.

Usage, from backend/: python -m scripts.load_sqlite_backup <path to backup vyuham.db>
Refuses to run if the target already holds data. The token signing key is not copied.
"""
import sqlite3
import sys
from pathlib import Path

from app import db, pg

# Parents before children, so foreign keys hold.
TABLES = ["core_state", "documents", "chunks", "chunks_fts", "project_specs", "clarifications", "plans", "profiles", "resumes",
          "skill_assessments", "skill_challenges", "professional_links", "progress_updates", "progress_snapshots", "conversations",
          "messages", "pending_actions", "change_requests", "notifications", "ai_usage"]
GENERATED = {"tsv"}


def main(path: str) -> int:
    source_path = Path(path).resolve()
    if not db.DB_URL:
        print("SUPABASE_DB_URL is not set. Nothing was done.")
        return 1
    source = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
    db.init()
    with pg.transaction() as s:
        occupied = [t for t in TABLES if s.execute(f'SELECT 1 FROM "{t}" LIMIT 1').fetchone()]
        if occupied:
            print(f"Target already holds data in: {', '.join(occupied)}. Nothing was done.")
            return 1
        for table in TABLES:
            columns = [r[0] for r in s.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
                                               (db.SCHEMA, table)).fetchall() if r[0] not in GENERATED]
            have = {r[1] for r in source.execute(f"PRAGMA table_info({table})")} or set(columns)
            columns = [c for c in columns if c in have or table == "chunks_fts" and c != "org_id"]
            names = ", ".join(columns)
            found = source.execute(f"SELECT {names} FROM {table}").fetchall()
            if found:
                s.executemany(f'INSERT INTO "{table}" ({names}) VALUES ({", ".join("?" * len(columns))})', found)
            for column in ("id", "rowid"):      # continue numbering after the copied rows
                if column in columns and s.execute("SELECT pg_get_serial_sequence(?, ?)", (f"{db.SCHEMA}.{table}", column)).fetchone()[0]:
                    s.execute(f"SELECT setval(pg_get_serial_sequence(?, ?), GREATEST((SELECT COALESCE(MAX({column}), 0) FROM \"{table}\"), 1))", (f"{db.SCHEMA}.{table}", column))
    bad = 0
    with pg.session() as s:
        for table in TABLES:
            want = source.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            got = s.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            print(f"{'ok ' if want == got else 'BAD'} {table}: {got} of {want}")
            bad += want != got
    source.close()
    print("All row counts match." if not bad else f"{bad} table(s) do not match.")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
