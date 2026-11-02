"""SQLite storage: one row per continuous stretch on the same window/tab."""

from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path

DATA_DIR = Path.home() / "Library" / "Application Support" / "scitime"
DB_PATH = DATA_DIR / "scitime.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS segments (
    id     INTEGER PRIMARY KEY,
    start  REAL NOT NULL,   -- unix time
    end    REAL NOT NULL,
    app    TEXT, bundle TEXT, title TEXT, url TEXT, domain TEXT, detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_segments_start ON segments(start);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)  # browsing history: owner only
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


def insert(con: sqlite3.Connection, start: float, end: float, s) -> int:
    cur = con.execute(
        "INSERT INTO segments (start, end, app, bundle, title, url, domain, detail) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (start, end, s.app, s.bundle, s.title, s.url, s.domain, s.detail),
    )
    con.commit()
    return cur.lastrowid


def extend(con: sqlite3.Connection, row_id: int, end: float) -> None:
    con.execute("UPDATE segments SET end = MAX(start, ?) WHERE id = ?", (end, row_id))
    con.commit()


def day_bounds(day: dt.date) -> tuple[float, float]:
    start = dt.datetime.combine(day, dt.time.min).timestamp()
    end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time.min).timestamp()
    return start, end


def segments_between(con: sqlite3.Connection, t0: float, t1: float) -> list[dict]:
    """Segments overlapping [t0, t1), clipped to it."""
    rows = con.execute(
        "SELECT * FROM segments WHERE end > ? AND start < ? ORDER BY start", (t0, t1)
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["start"], d["end"] = max(d["start"], t0), min(d["end"], t1)
        out.append(d)
    return out
