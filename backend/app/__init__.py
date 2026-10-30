"""Loads the project's .env file for local runs. Real environment variables take precedence."""
import os
from pathlib import Path

if not os.environ.get("AF07_SKIP_DOTENV"):
    for candidate in (Path(__file__).resolve().parents[2] / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if value.strip():
                        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
