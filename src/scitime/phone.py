"""iPhone time from an event log written by iOS Shortcuts automations.

Each line of the log is "<ISO 8601 date>,<event>,<app>", for example
    2026-11-01T21:03:05+01:00,open,Douyin
    2026-11-01T21:20:41+01:00,close
An "open" starts a session; it ends at the next event of any kind (only one app can
be in front on an iPhone), and never lasts longer than max_session_minutes, in case
a "close" was missed (e.g. the phone was locked).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

DEFAULT_DIR = "~/Library/Mobile Documents/iCloud~is~workflow~my~workflows/Documents/scitime"
PHONE_BUNDLE = "iphone"


def _parse_time(text: str) -> float | None:
    text = text.strip().replace("Z", "+00:00")
    try:
        t = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    return t.timestamp()  # naive = local time, as written by the phone


def read_events(path: Path) -> list[tuple[float, str, str]]:
    """(time, event, app) sorted by time; unreadable lines are skipped."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(errors="replace").splitlines():
        parts = [p.strip() for p in line.split(",", 2)]
        if len(parts) < 2:
            continue
        t = _parse_time(parts[0])
        if t is None:
            continue
        event = parts[1].lower()
        app = parts[2] if len(parts) > 2 else ""
        if event in ("open", "close"):
            out.append((t, event, app))
    out.sort(key=lambda e: e[0])
    return out


def sessions(events: list[tuple[float, str, str]], max_minutes: float = 120) -> list[dict]:
    """Turn events into segments shaped like rows of the Mac segments table."""
    cap = max_minutes * 60
    out = []
    for i, (t, event, app) in enumerate(events):
        if event != "open" or not app:
            continue
        end = events[i + 1][0] if i + 1 < len(events) else min(t + cap, dt.datetime.now().timestamp())
        end = min(end, t + cap)
        if end > t:
            out.append(
                {"start": t, "end": end, "app": app, "bundle": PHONE_BUNDLE,
                 "title": "", "url": "", "domain": "", "detail": ""}
            )
    return out


def segments_between(path: Path, t0: float, t1: float, max_minutes: float = 120) -> list[dict]:
    out = []
    for s in sessions(read_events(path), max_minutes):
        if s["end"] > t0 and s["start"] < t1:
            out.append(s | {"start": max(s["start"], t0), "end": min(s["end"], t1)})
    return out
