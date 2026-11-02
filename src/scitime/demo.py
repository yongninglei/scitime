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
