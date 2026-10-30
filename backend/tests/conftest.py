import atexit
import os
import tempfile
import uuid

os.environ["AF07_DATA_DIR"] = tempfile.mkdtemp(prefix="vyuham-test-")
os.environ["AF07_SKIP_DOTENV"] = "1"
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

# Set VYUHAM_TEST_DB_URL to run the suite on Postgres, in a temporary schema that is dropped afterwards.
_test_url = os.environ.get("VYUHAM_TEST_DB_URL", "").strip()
if _test_url:
    _owner_url = os.environ["VYUHAM_TEST_OWNER_URL"]
    os.environ.update(SUPABASE_DB_URL=_test_url, SUPABASE_MIGRATION_DB_URL=_owner_url, VYUHAM_ENV="development", VYUHAM_SCHEMA=f"vyuham_test_{uuid.uuid4().hex[:10]}")
    from app import db, pg
    os.environ["VYUHAM_DEV_PROJECT_REF"] = db.project_ref()

    def _drop_test_schema():
        pg.close_pool()
        pg.drop_schema_for_tests(db.SCHEMA, _owner_url)
    atexit.register(_drop_test_schema)
else:
    os.environ.pop("SUPABASE_DB_URL", None)
    os.environ.pop("SUPABASE_MIGRATION_DB_URL", None)
