"""SQLite storage for the dummy Access Point.

Deliberately not Postgres: this service is a stand-in for a real business API,
and requiring a database server to run it would make it more infrastructure
than the thing it exists to support. SQLite means one file (or none at all)
and a single-container deployment.

One connection is held for the process lifetime and writes are serialised
behind a lock. That is plenty for a dummy, and it is what makes
EINVOICE_DATABASE_PATH=":memory:" work at all — each new SQLite connection to
":memory:" gets its *own* empty database, so a pool would silently hand out
connections that can't see each other's data.
"""

import asyncio
import json
from datetime import datetime, timezone

import aiosqlite

from config import settings

_conn: aiosqlite.Connection | None = None
_write_lock = asyncio.Lock()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_db_time(value: datetime | None) -> str | None:
    """Store timestamps as ISO-8601 UTC text — SQLite has no native date type."""
    return value.astimezone(timezone.utc).isoformat() if value else None


def from_db_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    # Rows written before a tz was attached would come back naive; assume UTC
    # rather than letting an aware/naive comparison blow up in the projection.
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def to_db_json(value) -> str:
    return json.dumps(value if value is not None else [])


def from_db_json(value: str | None):
    return json.loads(value) if value else []


async def get_conn() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        _conn = await aiosqlite.connect(settings.database_path)
        _conn.row_factory = aiosqlite.Row
        # WAL is a no-op for :memory: but lets file-backed reads proceed
        # during writes.
        await _conn.execute("PRAGMA journal_mode=WAL")
        await _conn.execute("PRAGMA foreign_keys=ON")
        await _conn.commit()
    return _conn


async def init_db():
    """Create the single companies table. Idempotent — runs on every startup."""
    conn = await get_conn()
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id TEXT PRIMARY KEY,

            -- identity
            participant_id TEXT NOT NULL UNIQUE,
            uen TEXT NOT NULL,
            name TEXT NOT NULL,
            country_code TEXT NOT NULL,
            solution_provider_id TEXT,
            access_point_configurations TEXT NOT NULL DEFAULT '[]',

            -- KYC registration: always configured.  PENDING -> REGISTERED
            kyc_status TEXT NOT NULL DEFAULT 'PENDING',
            kyc_status_changed_at TEXT NOT NULL,

            -- Tax submission: opt-in, togglable at any time and independent
            -- of kyc_status.  NULL = never enabled.
            --   PENDING_ACTIVATION   -> ACTIVATED
            --   PENDING_DEACTIVATION -> DEACTIVATED
            tax_status TEXT,
            tax_status_changed_at TEXT,

            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_companies_uen ON companies (uen)"
    )
    await conn.commit()


async def fetch(query: str, *args) -> list[aiosqlite.Row]:
    conn = await get_conn()
    async with conn.execute(query, args) as cursor:
        return await cursor.fetchall()


async def fetchrow(query: str, *args) -> aiosqlite.Row | None:
    conn = await get_conn()
    async with conn.execute(query, args) as cursor:
        return await cursor.fetchone()


async def execute(query: str, *args) -> int:
    """Run a write and return the number of affected rows."""
    conn = await get_conn()
    async with _write_lock:
        cursor = await conn.execute(query, args)
        await conn.commit()
        return cursor.rowcount


async def close_db():
    global _conn
    if _conn:
        await _conn.close()
        _conn = None
