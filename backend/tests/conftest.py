import os
import tempfile

os.environ["AF07_DATA_DIR"] = tempfile.mkdtemp(prefix="vyuham-test-")
os.environ["AF07_SKIP_DOTENV"] = "1"
os.environ.pop("ANTHROPIC_API_KEY", None)
os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
