"""Made-up data for a researcher's last two weeks, used for the website demo and `scitime demo`."""

from __future__ import annotations

import datetime as dt
import random
from pathlib import Path

from . import dashboard, rules, store
from .probe import Sample

# (weight, sample) — what a typical day of a computational neuroscientist looks like
ACTIVITIES = [
    (9, Sample(app="Terminal", bundle="com.apple.Terminal", detail="cli:claude")),
    (5, Sample(app="Cursor", bundle="com.todesktop.230313mzl4w4u92")),
    (3, Sample(app="Chrome", bundle="com.google.Chrome", domain="github.com", url="https://github.com/")),
    (8, Sample(app="Chrome", bundle="com.google.Chrome", domain="overleaf.com", url="https://www.overleaf.com/")),
    (4, Sample(app="Chrome", bundle="com.google.Chrome", domain="docs.google.com", url="https://docs.google.com/")),
    (3, Sample(app="Chrome", bundle="com.google.Chrome", domain="claude.ai", url="https://claude.ai/chat/")),
    (3, Sample(app="Zotero", bundle="org.zotero.zotero")),
    (2, Sample(app="Chrome", bundle="com.google.Chrome", domain="pubmed.ncbi.nlm.nih.gov", url="https://pubmed.ncbi.nlm.nih.gov/")),
    (5, Sample(app="MATLAB", bundle="com.mathworks.matlab")),
    (4, Sample(app="RStudio", bundle="org.rstudio.RStudio")),
    (3, Sample(app="Chrome", bundle="com.google.Chrome", domain="localhost", url="http://localhost:8501/")),
    (6, Sample(app="Terminal", bundle="com.apple.Terminal", detail="ssh:hpc.example.org")),
    (3, Sample(app="Affinity Designer 2", bundle="com.seriflabs.affinitydesigner2")),
    (1, Sample(app="Chrome", bundle="com.google.Chrome", domain="biorender.com", url="https://biorender.com/")),
    (4, Sample(app="Slack", bundle="com.tinyspeck.slackmacgap")),
    (3, Sample(app="Mail", bundle="com.apple.mail")),
    (3, Sample(app="Chrome", bundle="com.google.Chrome", domain="elpais.com", url="https://elpais.com/")),
    (2, Sample(app="Chrome", bundle="com.google.Chrome", domain="youtube.com", url="https://youtube.com/")),
    (1, Sample(app="Chrome", bundle="com.google.Chrome", domain="x.com", url="https://x.com/")),
    (1, Sample(app="Preview", bundle="com.apple.Preview")),
]


def fill(con, end_day: dt.date, days: int = 14, seed: int = 23) -> None:
    rng = random.Random(seed)
    weights = [w for w, _ in ACTIVITIES]
    for i in range(days):
        day = end_day - dt.timedelta(days=days - 1 - i)
        if day.weekday() >= 5 and rng.random() < 0.6:
            continue  # most weekends off
        t = dt.datetime.combine(day, dt.time(8, 30)).timestamp() + rng.uniform(0, 3600)
        stop = dt.datetime.combine(day, dt.time(18, 30)).timestamp() + rng.uniform(-3600, 5400)
        if day == end_day:
            stop = min(stop, dt.datetime.combine(day, dt.time(16, 40)).timestamp())
        while t < stop:
            if 13 * 3600 <= (t - dt.datetime.combine(day, dt.time.min).timestamp()) < 14 * 3600:
                t += 3600  # lunch
                continue
            s = rng.choices(ACTIVITIES, weights)[0][1]
            dur = rng.uniform(4, 40) * 60
            store.insert(con, t, min(t + dur, stop), s)
            t += dur + rng.uniform(0, 6) * 60


def write(out: Path, db: Path, today: dt.date | None = None) -> Path:
    """Write a demo dashboard from made-up data in a throwaway database (never the real one)."""
    today = today or dt.date.today()
    cfg = rules.parse(rules.default_rules_text())
    cfg.phone_dir = ""
    con = store.connect(db)
    fill(con, today)
    dashboard.write(con, cfg, today, 14, out)
    con.close()
    return out


MENU_CSS = """
body { margin:0; width:620px; height:520px; font:13px -apple-system, BlinkMacSystemFont, sans-serif;
       background: linear-gradient(140deg, #5b5bf0 0%, #a35cf0 55%, #f08bb4 100%); overflow:hidden; }
.mb { height:26px; display:flex; justify-content:flex-end; align-items:center; gap:16px; padding:0 14px;
      background:rgba(255,255,255,.28); backdrop-filter:blur(20px); color:#111; font-weight:500; }
.mb .on { background:rgba(255,255,255,.55); border-radius:5px; padding:2px 8px; font-variant-numeric:tabular-nums; }
.menu { position:absolute; top:30px; left:126px; width:330px; padding:5px; border-radius:11px;
        background:rgba(246,246,248,.93); backdrop-filter:blur(30px); color:#1d1d1f;
        box-shadow:0 0 0 .5px rgba(0,0,0,.18), 0 12px 40px rgba(0,0,0,.28); }
.r { display:flex; align-items:center; gap:7px; padding:3px 10px; border-radius:6px; line-height:18px;
     white-space:nowrap; }
.r .x { margin-left:auto; color:#888; }
.r.hl { background:#5b5bf0; color:#fff; } .r.hl .x { color:#fff; }
.d { width:9px; height:9px; border-radius:50%; flex:none; }
.s { height:1px; background:rgba(0,0,0,.1); margin:5px 10px; }
.sub { position:absolute; top:94px; left:460px; width:150px; padding:5px; border-radius:11px;
       background:rgba(246,246,248,.93); box-shadow:0 0 0 .5px rgba(0,0,0,.18), 0 12px 40px rgba(0,0,0,.28); }
"""


def write_menubar_mock(out: Path, db: Path, today: dt.date) -> Path:
    """HTML picture of the menu bar item and its open menu, from the demo data (for the README)."""
    from html import escape

    from . import alerts, menubar, report

    cfg = rules.parse(rules.default_rules_text())
    cfg.phone_dir = ""
    con = store.connect(db)
    fill(con, today)
    s = report.summarize_day(con, cfg, today)
    now = dt.datetime.combine(today, dt.time(16, 40)).timestamp()
    view = menubar.build(s, cfg, alerts.evaluate(s, cfg), now - 5, now)
    con.close()
    rows, sub, first_cat = [], "", True
    for r in view.rows + [None, menubar.Row("Open dashboard"), menubar.Row("Refresh now"), menubar.Row("Quit SciTime")]:
        if r is None:
            rows.append('<div class="s"></div>')
            continue
        dot = f'<span class="d" style="background:{r.color}"></span>' if r.color else ""
        hl = r.color and first_cat
        chevron = '<span class="x">›</span>' if r.children else ""
        rows.append(f'<div class="r{" hl" if hl else ""}">{dot}{escape(r.text)}{chevron}</div>')
        if hl:
            first_cat = False
            sub = "".join(f'<div class="r">{escape(c)}</div>' for c in r.children)
    clock = dt.datetime.fromtimestamp(now).strftime("%a %-d %b  %H:%M")
    out.write_text(
        f'<!doctype html><meta charset="utf-8"><style>{MENU_CSS}</style>'
        f'<div class="mb"><span>🔋 87%</span><span>📶</span><span class="on">{escape(view.title)}</span>'
        f'<span>{clock}</span></div><div class="menu">{"".join(rows)}</div><div class="sub">{sub}</div>'
    )
    return out
