"""Aggregate segments into per-day, per-category totals."""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import phone, store
from .rules import Config


@dataclass
class DaySummary:
    day: dt.date
    by_category: Counter = field(default_factory=Counter)  # seconds
    # category -> Counter of "where" (domain, ssh host, app) -> seconds
    top: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    by_hour: dict[int, Counter] = field(default_factory=lambda: defaultdict(Counter))
    # "mac" / "phone" -> Counter of category -> seconds
    by_device: dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))

    @property
    def total(self) -> float:
        return sum(self.by_category.values())

    def to_json(self, cfg: Config, device: str = "mac", n_top: int = 10) -> dict:
        return {
            "date": self.day.isoformat(),
            "device": device,
            "total_seconds": round(self.total),
            "categories": {
                c: {
                    "label": cfg.label(c),
                    "seconds": round(sec),
                    "top": [[k, round(v)] for k, v in self.top[c].most_common(n_top)],
                }
                for c, sec in self.by_category.most_common()
            },
        }


def where(seg: dict) -> str:
    """Short name of what was used: ssh host, AI CLI, website, or app."""
    if seg.get("bundle") == phone.PHONE_BUNDLE:
        return f"📱 {seg.get('app')}"
    if seg.get("detail"):
        return seg["detail"]
    if seg.get("domain"):
        return seg["domain"]
    return seg.get("app") or "?"


def summarize_day(con, cfg: Config, day: dt.date) -> DaySummary:
    t0, t1 = store.day_bounds(day)
    out = DaySummary(day)
    segs = store.segments_between(con, t0, t1)
    if cfg.phone_dir:
        events = Path(cfg.phone_dir).expanduser() / "phone_events.txt"
        segs += phone.segments_between(events, t0, t1, cfg.phone_max_minutes)
    for seg in segs:
        sec = seg["end"] - seg["start"]
        if sec <= 0:
            continue
        cat = cfg.classify(seg)
        out.by_category[cat] += sec
        out.top[cat][where(seg)] += sec
        out.by_device["phone" if seg.get("bundle") == phone.PHONE_BUNDLE else "mac"][cat] += sec
        # split across hour boundaries for the hourly strip
        t = seg["start"]
        while t < seg["end"]:
            hour_end = (int(t) // 3600 + 1) * 3600
            chunk_end = min(hour_end, seg["end"])
            out.by_hour[dt.datetime.fromtimestamp(t).hour][cat] += chunk_end - t
            t = chunk_end
    return out


def fmt(sec: float) -> str:
    m = int(round(sec / 60))
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"


def export_day(summary: DaySummary, cfg: Config, sync_dir: Path, device: str = "mac") -> Path:
    """Write <sync_dir>/<device>/YYYY-MM-DD.json for other devices to read."""
    out = sync_dir / device / f"{summary.day.isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary.to_json(cfg, device), indent=2, ensure_ascii=False))
    return out
