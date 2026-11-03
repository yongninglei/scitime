import datetime as dt

from scitime import report, rules, store
from scitime.probe import Sample, classify_jobs, detail_from_title, domain_of
from scitime.tracker import Tracker

CFG = rules.parse(rules.default_rules_text())


def cat(**seg):
    return CFG.classify(seg)


def test_classify_examples():
    assert cat(detail="ssh:hpc.example.org") == "server"
    assert cat(bundle="com.microsoft.VSCode", title="x.py — proj [SSH: cluster]") == "server"
    assert cat(bundle="com.citrix.receiver.icaviewer.mac", app="Citrix Viewer") == "server"
    assert cat(bundle="com.citrix.receiver.nomas", app="Citrix Workspace") == "server"
    assert cat(bundle="com.seriflabs.affinitydesigner2", app="Affinity Designer 2") == "figures"
    assert cat(bundle="com.google.Chrome", url="http://localhost:8501/?page=wm", domain="localhost") == "data_analysis"
    assert cat(bundle="com.mathworks.matlab", app="MATLAB") == "data_analysis"
    assert cat(bundle="org.rstudio.RStudio", app="RStudio") == "data_analysis"
    assert cat(bundle="com.google.Chrome", domain="biorender.com") == "figures"
    assert cat(detail="cli:claude", bundle="com.apple.Terminal") == "vibe_coding"
    assert cat(bundle="com.anthropic.claudefordesktop") == "vibe_coding"
    assert cat(bundle="com.google.Chrome", domain="docs.google.com") == "paper_writing"
    for d in ("www.sciencedirect.com", "paperpile.com", "elifesciences.org", "www.nature.com", "jov.arvojournals.org"):
        assert cat(bundle="com.google.Chrome", domain=d) == "paper_reading", d
    assert cat(bundle="org.zotero.zotero", app="Zotero") == "paper_reading"
    assert cat(bundle="com.google.Chrome", domain="claude.ai", url="https://claude.ai/chat/1") == "paper_writing"
    assert cat(bundle="com.google.Chrome", domain="claude.ai", url="https://claude.ai/code/x") == "vibe_coding"
    assert cat(bundle="com.apple.Safari", domain="youtube.com") == "social"
    assert cat(bundle="com.apple.Safari", domain="elpais.com") == "browsing"
    assert cat(bundle="com.apple.Terminal") == "terminal_local"
    assert cat(bundle="com.apple.Preview") == "other"


def test_terminal_jobs():
    assert classify_jobs([["-zsh"], ["ssh", "-p", "22", "alice@hpc.example.org"]]) == "ssh:hpc.example.org"
    assert classify_jobs([["-zsh"], ["node", "/opt/homebrew/bin/claude"]]) == "cli:claude"
    assert classify_jobs([["-zsh"], ["claude", "--resume"]]) == "cli:claude"
    assert classify_jobs([["-zsh"], ["vim", "a.py"]]) == ""
    assert detail_from_title("alice@mac: ssh alice@cluster-login") == "ssh:cluster-login"
    assert domain_of("https://www.youtube.com/watch?v=1") == "youtube.com"


def test_tracker_merges_and_handles_idle(tmp_path):
    con = store.connect(tmp_path / "t.db")
    tr = Tracker(CFG, con)
    t0 = dt.datetime(2026, 11, 1, 10, 0).timestamp()
    a = Sample(app="Chrome", bundle="com.google.Chrome", domain="docs.google.com", url="u1")
    b = Sample(app="Terminal", bundle="com.apple.Terminal", detail="ssh:hpc")
    for i in range(12):  # 60 s of docs
        tr.tick(a, t0 + 5 * i)
    for i in range(12, 24):  # 60 s of ssh
        tr.tick(b, t0 + 5 * i)
    # away: idle beyond threshold, counted only up to when input stopped
    tr.tick(Sample(app="Terminal", bundle="com.apple.Terminal", detail="ssh:hpc", idle=400), t0 + 500)
    rows = con.execute("SELECT * FROM segments ORDER BY start").fetchall()
    assert len(rows) == 2
    s = report.summarize_day(con, CFG, dt.date(2026, 11, 1))
    assert round(s.by_category["paper_writing"]) == 60
    assert round(s.by_category["server"]) == 55 + 0  # last ssh tick at +115; idle start +100 < that
    assert s.top["server"]["ssh:hpc"] > 0


def test_export(tmp_path):
    con = store.connect(tmp_path / "t.db")
    t0 = dt.datetime(2026, 11, 1, 9, 0).timestamp()
    store.insert(con, t0, t0 + 3600, Sample(app="Code", bundle="com.microsoft.VSCode"))
    s = report.summarize_day(con, CFG, dt.date(2026, 11, 1))
    path = report.export_day(s, CFG, tmp_path / "sync")
    assert path.name == "2026-11-01.json"
    assert '"vibe_coding"' in path.read_text()


def test_alerts(tmp_path):
    from scitime import alerts

    con = store.connect(tmp_path / "t.db")
    t0 = dt.datetime(2026, 11, 1, 9, 0).timestamp()
    store.insert(con, t0, t0 + 2 * 3600, Sample(bundle="com.google.Chrome", domain="docs.google.com"))
    store.insert(con, t0 + 7200, t0 + 7200 + 2 * 3600, Sample(bundle="com.google.Chrome", domain="youtube.com"))
    s = report.summarize_day(con, CFG, dt.date(2026, 11, 1))
    checks = {c.alert.name: c for c in alerts.evaluate(s, CFG)}
    assert checks["Writing"].under_min and not checks["Writing"].over_max
    assert checks["Browsing + social"].over_max
    assert "below the 4 h goal" in alerts.digest_text(s, CFG, list(checks.values()))


def test_phone_events(tmp_path):
    from scitime import phone

    log = tmp_path / "phone_events.txt"
    log.write_text(
        "2026-10-31T21:00:00+01:00,open,Douyin\n"
        "2026-10-31T21:30:00+01:00,open,WeChat\n"   # implicitly closes Douyin
        "2026-10-31T21:40:00+01:00,close\n"
        "garbage line\n"
        "2026-10-31T22:00:00+01:00,open,Instagram\n"  # never closed -> capped
    )
    segs = phone.sessions(phone.read_events(log), max_minutes=40)
    assert [(s["app"], round(s["end"] - s["start"])) for s in segs] == [
        ("Douyin", 1800), ("WeChat", 600), ("Instagram", 2400)
    ]
    assert CFG.classify(segs[0]) == "social"
    assert CFG.classify(segs[1]) == "communication"

    cfg = rules.parse(rules.default_rules_text())
    cfg.phone_dir = str(tmp_path)
    cfg.phone_max_minutes = 40
    con = store.connect(tmp_path / "t.db")
    t0 = dt.datetime.fromisoformat("2026-10-31T20:00:00+01:00").timestamp()
    store.insert(con, t0, t0 + 3600, Sample(bundle="com.google.Chrome", domain="youtube.com"))
    day = dt.datetime.fromtimestamp(t0).date()
    s = report.summarize_day(con, cfg, day)
    assert round(s.by_device["mac"]["social"]) == 3600
    assert round(s.by_device["phone"]["social"]) == 4200
    assert round(s.by_category["social"]) == 7800  # Mac + iPhone added up
    assert s.top["social"]["📱 Douyin"] == 1800


def test_menubar_view(tmp_path):
    from scitime import alerts, menubar

    con = store.connect(tmp_path / "t.db")
    t0 = dt.datetime(2026, 11, 1, 9, 0).timestamp()
    store.insert(con, t0, t0 + 3600, Sample(app="Code", bundle="com.microsoft.VSCode"))
    store.insert(con, t0 + 3600, t0 + 3 * 3600, Sample(bundle="com.google.Chrome", domain="youtube.com"))
    s = report.summarize_day(con, CFG, dt.date(2026, 11, 1))
    v = menubar.build(s, CFG, alerts.evaluate(s, CFG), last_sample=t0 + 3 * 3600, now=t0 + 3 * 3600 + 10)
    assert v.title == "⚠️ 3h 00m"  # browsing + social over 1.5 h
    cats = [r for r in v.rows if r and r.color]
    assert cats[0].text.startswith("Social / video   2h 00m") and cats[0].children == ["youtube.com   2h 00m"]
    assert not any(r and "tracker running" in r.text for r in v.rows)
    stale = menubar.build(s, CFG, [], last_sample=None, now=t0)
    assert stale.title == "⏱ 3h 00m" and "never" in stale.rows[-1].text
