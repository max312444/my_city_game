import asyncio
import os
import uuid
from pathlib import Path

import pytest

# Must happen before any `app.*` import: app/db.py reads this once at import time
# and points the whole app at this throwaway file instead of the real dev save
# (my_city.db, which has actual long-running playtest data we never want a test
# run to touch or wipe).
TEST_DB_PATH = Path(__file__).resolve().parent / "test_regnum.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"

from app.db import engine, init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_test_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    asyncio.run(init_db())
    yield
    asyncio.run(engine.dispose())


@pytest.fixture
def session_id():
    """A fresh, unique session id per test so tests never see each other's rows,
    even though they all share one physical test database file."""
    return f"test_{uuid.uuid4().hex[:12]}"
