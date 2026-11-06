"""scitime command line: run the tracker, see reports, open the dashboard, manage autostart."""

from __future__ import annotations

import datetime as dt
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__, report, rules, store

console = Console()
app = typer.Typer(
    add_completion=False,
    pretty_exceptions_show_locals=False,
    help="SciTime — a scientific activity monitor: where your research day goes.",
)

LABEL = "io.github.yongninglei.scitime"
DIGEST_LABEL = "io.github.yongninglei.scitime.digest"
AGENTS = Path.home() / "Library" / "LaunchAgents"
PLIST = AGENTS / f"{LABEL}.plist"
DIGEST_PLIST = AGENTS / f"{DIGEST_LABEL}.plist"
BAR_LABEL = "io.github.yongninglei.scitime.bar"
BAR_PLIST = AGENTS / f"{BAR_LABEL}.plist"
LOG_DIR = Path.home() / "Library" / "Logs" / "scitime"
REPO = Path(__file__).resolve().parents[2]


def _parse_day(day: str) -> dt.date:
    if day == "today":
        return dt.date.today()
    if day == "yesterday":
        return dt.date.today() - dt.timedelta(days=1)
    return dt.date.fromisoformat(day)


@app.command()
def init() -> None:
    """Copy the default rules to ~/.config/scitime/rules.toml so you can edit them."""
    path, created = rules.init_user_rules()
    if created:
        console.print(f"[green]saved[/green] {path}")
    else:
        console.print(f"[yellow]SKIP[/yellow] {path} already exists (not overwritten)")


@app.command()
def run(quiet: bool = typer.Option(False, "--quiet", help="Do not print each switch")) -> None:
    """Run the tracker in the foreground (what the launch agent runs)."""
    from .tracker import Tracker

    cfg = rules.load()
    con = store.connect()
    console.rule(f"[bold]scitime {__version__}[/bold] — sampling every {cfg.interval:g}s")
    console.print(f"[dim]db: {store.DB_PATH}[/dim]")
    try:
        Tracker(cfg, con, None if quiet else console).run()
    except KeyboardInterrupt:
        console.print("stopped")


@app.command()
def now() -> None:
    """Show what scitime sees right now (use this to check permissions)."""
    from . import probe

    cfg = rules.load()
    s = probe.sample()
    t = Table(show_header=False, box=None)
    for k, v in s.__dict__.items():
        t.add_row(f"[dim]{k}[/dim]", f"{v:.0f}s" if k == "idle" else (str(v) or "[dim]—[/dim]"))
    t.add_row("[dim]category[/dim]", f"[bold]{cfg.label(cfg.classify(s.__dict__))}[/bold]")
    console.print(t)
    if not s.title:
        console.print(
            "[yellow]No window title.[/yellow] Grant Screen Recording to "
            f"[bold]{os.path.realpath(sys.executable)}[/bold] in System Settings → "
            "Privacy & Security → Screen & System Audio Recording."
        )


@app.command("report")
def report_cmd(
    day: str = typer.Option("today", "--day", help="today, yesterday or YYYY-MM-DD"),
    days: int = typer.Option(1, "--days", help="Also show a table for the N days ending at --day"),
    top: int = typer.Option(5, "--top", help="Items listed per category"),
) -> None:
    """Print time per category for a day."""
    cfg = rules.load()
    con = store.connect()
    d = _parse_day(day)
    s = report.summarize_day(con, cfg, d)
    console.rule(f"[bold]{d.isoformat()}[/bold] — active {report.fmt(s.total)}")
    t = Table(box=None, pad_edge=False)
    t.add_column("category")
    t.add_column("time", justify="right")
    t.add_column("💻", justify="right", style="dim")
    t.add_column("📱", justify="right", style="dim")
    t.add_column("%", justify="right")
    t.add_column("top", style="dim")
    for c, sec in s.by_category.most_common():
        items = ", ".join(f"{k} {report.fmt(v)}" for k, v in s.top[c].most_common(top))
        mac, ph = s.by_device["mac"].get(c, 0), s.by_device["phone"].get(c, 0)
        t.add_row(
            f"[{cfg.color(c)}]●[/] {cfg.label(c)}",
            report.fmt(sec),
            report.fmt(mac) if mac else "·",
            report.fmt(ph) if ph else "·",
            f"{sec / (s.total or 1) * 100:.0f}",
            items,
        )
    console.print(t)

    if days > 1:
        cats = list(cfg.categories)
        t = Table(box=None)
        t.add_column("day")
        for c in cats:
            t.add_column(cfg.label(c), justify="right")
        t.add_column("total", justify="right")
        for i in range(days - 1, -1, -1):
            di = d - dt.timedelta(days=i)
            si = report.summarize_day(con, cfg, di)
            t.add_row(
                di.strftime("%a %m-%d"),
                *[report.fmt(si.by_category.get(c, 0)) if si.by_category.get(c) else "·" for c in cats],
                report.fmt(si.total),
            )
        console.print(t)


@app.command()
def dashboard(
    day: str = typer.Option("today", "--day"),
    days: int = typer.Option(30, "--days", help="Days you can go back to (and in the history chart)"),
    out: Path = typer.Option(store.DATA_DIR / "dashboard.html", "--out"),
    open_: bool = typer.Option(True, "--open/--no-open"),
) -> None:
    """Write the HTML dashboard and open it in the browser."""
    from . import dashboard as dash

    cfg = rules.load()
    con = store.connect()
    d = _parse_day(day)
    dash.write(con, cfg, d, days, out)
    console.print(f"[green]saved[/green] {out}")
    if cfg.phone_dir:
        phone_out = Path(cfg.phone_dir).expanduser() / "scitime.html"
        dash.write(con, cfg, d, days, phone_out)
        console.print(f"[green]saved[/green] {phone_out} (for the iPhone)")
    if open_:
        subprocess.run(["open", str(out)], check=False)


@app.command()
def demo(
    out: Path = typer.Option(Path("scitime_demo.html"), "--out"),
    open_: bool = typer.Option(True, "--open/--no-open"),
) -> None:
    """Dashboard filled with made-up data, to see what SciTime looks like."""
    import tempfile

    from . import demo as demo_mod

    with tempfile.TemporaryDirectory() as tmp:
        demo_mod.write(out, Path(tmp) / "demo.db")
    console.print(f"[green]saved[/green] {out}")
    if open_:
        subprocess.run(["open", str(out)], check=False)


@app.command()
def bar() -> None:
    """Show today's time in the menu bar (click it for categories and goals)."""
    from . import menubar

    console.print(f"menu bar running — refreshes every {menubar.REFRESH_SECONDS}s, Ctrl-C or Quit to stop")
    menubar.run()


def _save(text: str, what: str) -> None:
    path = rules.save_user_rules(text)
    console.print(f"[green]saved[/green] {what} in {path} (previous version: {path.name}.bak)")
    console.print("[dim]Past days are re-sorted too; the menu bar picks it up within a minute.[/dim]")


@app.command()
def categories() -> None:
    """List your categories: key (for add-rule), label, colour, and how many rules use each."""
    cfg = rules.load()
    t = Table(box=None)
    for col in ("key", "label", "colour", "rules", "focus"):
        t.add_column(col)
    from .dashboard import FOCUS

    for key, c in cfg.categories.items():
        n = sum(r.category == key for r in cfg.rules)
        color = c.get("color", "")
        foc = "yes" if c.get("focus", key in FOCUS) else ""
        t.add_row(key, c.get("label", key), f"[{color}]●[/] {color}", str(n), foc)
    console.print(t)


@app.command("add-category")
def add_category(
    key: str = typer.Argument(..., help="Short name used in rules, e.g. grant_writing"),
    label: str = typer.Option("", "--label", help="Name shown in reports, e.g. 'Grant writing'"),
    color: str = typer.Option("", "--color", help="#rrggbb; a free colour is picked if left out"),
    focus: bool = typer.Option(None, "--focus/--no-focus", help="Count it as research focus on the dashboard"),
) -> None:
    """Add a new category to your rules.toml (then give it rules with add-rule)."""
    try:
        text = rules.add_category_text(rules.user_rules_text(), key, label, color, focus)
    except ValueError as e:
        console.print(f"[red]ERROR[/red] {e}")
        raise typer.Exit(1)
    _save(text, f"category [bold]{key}[/bold]")


@app.command("add-rule")
def add_rule(
    category: str = typer.Argument(..., help="Category key (see `scitime categories`)"),
    domain: str = typer.Option("", "--domain", help="Website, e.g. jov.arvojournals.org (subdomains included) or a regex"),
    app_: str = typer.Option("", "--app", help="App name regex, e.g. 'Skim|PDF Expert'"),
    bundle: str = typer.Option("", "--bundle", help="App bundle id regex, e.g. 'com\\.readdle\\.'"),
    url: str = typer.Option("", "--url", help="Regex on the full page URL"),
    title: str = typer.Option("", "--title", help="Regex on the window title"),
    detail: str = typer.Option("", "--detail", help="Terminal tab: 'ssh:<host>' or 'cli:<program>' regex"),
) -> None:
    """Send an app or website to a category. Your rules come first, so they beat the built-in ones.

    All the options you give must match. Example: scitime add-rule paper_reading --domain jov.arvojournals.org
    """
    fields = {"domain": domain, "app": app_, "bundle": bundle, "url": url, "title": title, "detail": detail}
    try:
        text = rules.add_rule_text(rules.user_rules_text(), category, fields)
    except ValueError as e:
        console.print(f"[red]ERROR[/red] {e}")
        raise typer.Exit(1)
    _save(text, f"rule → [bold]{category}[/bold]")


@app.command()
def which(
    domain: str = typer.Option("", "--domain", help="e.g. www.sciencedirect.com"),
    url: str = typer.Option("", "--url", help="Full URL; its domain is filled in for you"),
    app_: str = typer.Option("", "--app"),
    bundle: str = typer.Option("", "--bundle"),
    title: str = typer.Option("", "--title"),
    detail: str = typer.Option("", "--detail"),
) -> None:
    """Test the rules: which category would this app / website go to? Records nothing."""
    from .probe import domain_of

    seg = {"domain": domain.lower().removeprefix("www.") or (domain_of(url) if url else ""), "url": url, "app": app_,
           "bundle": bundle or ("com.google.Chrome" if (domain or url) else ""), "title": title, "detail": detail}
    cfg = rules.load()
    m = cfg.match(seg)
    if not m:
        console.print("→ [bold]other[/bold] (no rule matches)")
        return
    i, r = m
    pats = ", ".join(f"{f} ~ {p.pattern if len(p.pattern) < 60 else p.pattern[:57] + '...'}" for f, p in r.patterns.items())
    console.print(f"→ [bold]{cfg.label(r.category)}[/bold] ({r.category}), rule #{i + 1}: {pats}")


@app.command()
def export(
    day: str = typer.Option("today", "--day"),
    days: int = typer.Option(1, "--days", help="Export the N days ending at --day"),
    sync_dir: str = typer.Option("", "--sync-dir", help="Overrides sync_dir in rules.toml"),
) -> None:
    """Write daily JSON summaries to the sync folder (for the phone version)."""
    cfg = rules.load()
    target = sync_dir or cfg.sync_dir
    if not target:
        console.print("[red]ERROR[/red] no sync_dir: set it in rules.toml or pass --sync-dir")
        raise typer.Exit(1)
    con = store.connect()
    d = _parse_day(day)
    for i in range(days):
        s = report.summarize_day(con, cfg, d - dt.timedelta(days=i))
        path = report.export_day(s, cfg, Path(target).expanduser())
        console.print(f"[green]saved[/green] {path}")


@app.command()
def digest(
    day: str = typer.Option("today", "--day"),
    send: bool = typer.Option(False, "--send", help="Email it (to [digest] email) and notify"),
    to: str = typer.Option("", "--to", help="Overrides [digest] email in rules.toml"),
) -> None:
    """Daily summary with goal/limit checks. Without --send it is only printed."""
    from . import alerts
    from .dashboard import render

    cfg = rules.load()
    con = store.connect()
    d = _parse_day(day)
    s = report.summarize_day(con, cfg, d)
    checks = alerts.evaluate(s, cfg)
    body = alerts.digest_text(s, cfg, checks)
    console.print(body)
    if not send:
        return

    warnings = [c for c in checks if not c.ok]
    alerts.notify(
        f"scitime — {report.fmt(s.total)} today",
        " · ".join(c.line() for c in warnings) if warnings else "All goals met ✅",
    )
    if cfg.sync_dir:
        report.export_day(s, cfg, Path(cfg.sync_dir).expanduser())
    to = to or cfg.email
    if not to:
        console.print("[yellow]SKIP[/yellow] email: set [digest] email in rules.toml")
        return
    hist = [report.summarize_day(con, cfg, d - dt.timedelta(days=i)) for i in range(13, -1, -1)]
    html = store.DATA_DIR / f"scitime_{d.isoformat()}.html"
    html.write_text(render(hist[-1], hist, cfg))
    subject = f"scitime {d:%a %d %b}: {report.fmt(s.total)}" + (f" — ⚠️ {len(warnings)}" if warnings else " ✅")
    ok, err = alerts.send_mail(to, subject, body, html)
    if ok:
        console.print(f"[green]sent[/green] digest to {to}")
    else:
        console.print(f"[red]ERROR[/red] Mail.app: {err}")
        raise typer.Exit(1)


def _load_agent(plist_path: Path, plist: dict) -> None:
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(plistlib.dumps(plist))
    console.print(f"[green]saved[/green] {plist_path}")
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(plist_path)], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", domain, str(plist_path)], capture_output=True, text=True)
    if r.returncode == 0:
        console.print(f"[green]loaded[/green] {plist['Label']}")
    else:
        console.print(f"[red]ERROR[/red] launchctl bootstrap {plist['Label']}: {r.stderr.strip()}")
        raise typer.Exit(1)


@app.command("install-agent")
def install_agent() -> None:
    """Start tracking at login, and send the digest every evening (launchd user agents)."""
    cfg = rules.load()
    uv = shutil.which("uv") or str(Path.home() / ".local" / "bin" / "uv")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.chmod(0o700)
    base =[uv, "run", "--project", str(REPO), "scitime"]
    env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"}
    _load_agent(PLIST, {
        "Label": LABEL,
        "ProgramArguments": base + ["run", "--quiet"],
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "StandardOutPath": str(LOG_DIR / "scitime.out"),
        "StandardErrorPath": str(LOG_DIR / "scitime.err"),
        "EnvironmentVariables": env,
    })
    hh, mm = (int(x) for x in cfg.digest_time.split(":"))
    _load_agent(DIGEST_PLIST, {
        "Label": DIGEST_LABEL,
        "ProgramArguments": base + ["digest", "--send"],
        "StartCalendarInterval": {"Hour": hh, "Minute": mm},
        "StandardOutPath": str(LOG_DIR / "digest.out"),
        "StandardErrorPath": str(LOG_DIR / "digest.err"),
        "EnvironmentVariables": env,
    })
    _load_agent(BAR_PLIST, {
        "Label": BAR_LABEL,
        "ProgramArguments": base + ["bar"],
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},  # Quit from the menu stays quit until login
        "ProcessType": "Interactive",
        "StandardOutPath": str(LOG_DIR / "bar.out"),
        "StandardErrorPath": str(LOG_DIR / "bar.err"),
        "EnvironmentVariables": env,
    })
    console.print(f"tracking now; menu bar shown; digest every day at {cfg.digest_time}. Logs: {LOG_DIR}")


@app.command("stop-agent")
def stop_agent() -> None:
    """Stop all launch agents until next login (does not delete the plists)."""
    for p in (PLIST, DIGEST_PLIST, BAR_PLIST):
        subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}", str(p)], check=False)
    console.print(f"stopped. To disable autostart for good, delete {PLIST}, {DIGEST_PLIST} and {BAR_PLIST}")


@app.command()
def status() -> None:
    """Is the agent running, and when was the last sample written?"""
    r = subprocess.run(
        ["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"], capture_output=True, text=True
    )
    running = "state = running" in r.stdout
    console.print(f"agent: {'[green]running[/green]' if running else '[yellow]not running[/yellow]'}")
    con = store.connect()
    row = con.execute("SELECT MAX(end) AS t FROM segments").fetchone()
    if row["t"]:
        ago = dt.datetime.now().timestamp() - row["t"]
        console.print(f"last sample: {dt.datetime.fromtimestamp(row['t']):%Y-%m-%d %H:%M:%S} ({ago:.0f}s ago)")
    console.print(f"[dim]db: {store.DB_PATH}\nrules: {rules.USER_RULES if rules.USER_RULES.exists() else 'built-in defaults'}[/dim]")


if __name__ == "__main__":
    app()
