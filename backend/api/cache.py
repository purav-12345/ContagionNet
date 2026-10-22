"""
Layer 5 — SQLite results cache (async via aiosqlite).

Stores simulation results keyed by a hash of the scenario parameters so the same
scenario is not recomputed. Used by POST /api/simulate and scenario retrieval.
"""
from __future__ import annotations

import hashlib
import json
import logging

import aiosqlite

logger = logging.getLogger("api.cache")

DB_PATH = "simulator_cache.db"


def scenario_id(bank_id: str, shock_magnitude: float, algorithm: str) -> str:
    """Deterministic id (hash) of scenario parameters."""
    raw = f"{algorithm}|{bank_id}|{round(float(shock_magnitude), 6)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


async def init_cache(db_path: str = DB_PATH) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS scenarios (
                id TEXT PRIMARY KEY,
                bank_id TEXT NOT NULL,
                shock_magnitude REAL NOT NULL,
                algorithm TEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()
    logger.info("SQLite cache initialized at %s", db_path)


async def get_cached(scenario_hash: str, db_path: str = DB_PATH) -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT result_json FROM scenarios WHERE id = ?", (scenario_hash,)
        ) as cur:
            row = await cur.fetchone()
    if row:
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None
    return None


async def put_cached(
    scenario_hash: str,
    bank_id: str,
    shock_magnitude: float,
    algorithm: str,
    result: dict,
    db_path: str = DB_PATH,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO scenarios
              (id, bank_id, shock_magnitude, algorithm, result_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (scenario_hash, bank_id, float(shock_magnitude), algorithm, json.dumps(result)),
        )
        await db.commit()
