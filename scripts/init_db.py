"""Initialize the database (create tables) for local development.

Usage (from the backend/ directory):
    python ../scripts/init_db.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running from anywhere: add backend/ to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.db import init_db  # noqa: E402

if __name__ == "__main__":
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    print(f"✅ Database ready at: {settings.database_url}")
