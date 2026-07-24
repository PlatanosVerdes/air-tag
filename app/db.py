"""SQLite storage for decrypted location points.

Points are deduplicated on (timestamp, lat, lon), matching how FindMy.py itself
identifies a unique report, so re-polling overlapping history is idempotent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS points (
    ts       INTEGER NOT NULL,   -- unix seconds (UTC)
    lat      REAL    NOT NULL,
    lon      REAL    NOT NULL,
    accuracy INTEGER,            -- horizontal accuracy in meters
    status   INTEGER,            -- raw status byte (battery etc.)
    PRIMARY KEY (ts, lat, lon)
);
CREATE INDEX IF NOT EXISTS idx_points_ts ON points (ts);
"""


class Store:
    def __init__(self, path: Path) -> None:
        self._path = path

    async def init(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._path) as db:
            await db.executescript(_SCHEMA)
            await db.commit()

    async def insert_many(self, rows: Iterable[tuple[int, float, float, int, int]]) -> int:
        """Insert points, ignoring duplicates. Returns the number of new rows."""
        rows = list(rows)
        if not rows:
            return 0
        async with aiosqlite.connect(self._path) as db:
            cur = await db.executemany(
                "INSERT OR IGNORE INTO points (ts, lat, lon, accuracy, status) "
                "VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            await db.commit()
            return cur.rowcount

    async def points(
        self, since: int | None = None, until: int | None = None
    ) -> list[dict]:
        query = "SELECT ts, lat, lon, accuracy, status FROM points"
        clauses: list[str] = []
        params: list[int] = []
        if since is not None:
            clauses.append("ts >= ?")
            params.append(since)
        if until is not None:
            clauses.append("ts <= ?")
            params.append(until)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY ts ASC"
        async with aiosqlite.connect(self._path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cur:
                return [dict(r) async for r in cur]

    async def stats(self) -> dict:
        async with aiosqlite.connect(self._path) as db:
            async with db.execute(
                "SELECT COUNT(*) c, MIN(ts) mn, MAX(ts) mx FROM points"
            ) as cur:
                row = await cur.fetchone()
        return {"count": row[0], "first_ts": row[1], "last_ts": row[2]}
