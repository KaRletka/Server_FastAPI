import asyncio
import tempfile
from pathlib import Path

import aiosqlite
import pytest

_TEST_DB = Path(tempfile.mktemp(suffix=".sqlite"))
_TEST_LOG = Path(tempfile.mktemp(suffix=".log"))


def pytest_configure(config):
    import os
    os.environ["DB_PATH"] = str(_TEST_DB)
    os.environ["LOG_PATH"] = str(_TEST_LOG)


@pytest.fixture(scope="session", autouse=True)
def create_test_db():
    async def _setup():
        async with aiosqlite.connect(_TEST_DB) as db:
            await db.execute("PRAGMA foreign_keys = ON")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    login           TEXT    UNIQUE NOT NULL,
                    password_hash   TEXT    NOT NULL,
                    token_hash      TEXT    UNIQUE NOT NULL,
                    token_encrypted TEXT    NOT NULL DEFAULT ''
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS words (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    word          TEXT    NOT NULL,
                    transcription TEXT,
                    translate     TEXT    NOT NULL,
                    addition      TEXT,
                    UNIQUE(user_id, word)
                )
            """)
            await db.commit()

    asyncio.run(_setup())
    yield
    _TEST_DB.unlink(missing_ok=True)
    _TEST_LOG.unlink(missing_ok=True)
