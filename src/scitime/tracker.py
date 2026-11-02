"""The sampling loop: look at the screen every few seconds and extend or start a segment."""

from __future__ import annotations

import datetime as dt
import time

from rich.console import Console

from . import probe, store
from .rules import Config

AWAY_BUNDLES = {"com.apple.loginwindow", "com.apple.ScreenSaver.Engine"}


class Tracker:
    def __init__(self, cfg: Config, con, console: Console | None = None):
        self.cfg = cfg
        self.con = con
        self.console = console
        self.row_id: int | None = None
        self.key: tuple | None = None
        self.last = 0.0
        self.notified: set = set()
        self.last_check = 0.0
        self.last_publish = 0.0

    def _close(self, end: float) -> None:
        if self.row_id is not None:
            store.extend(self.con, self.row_id, end)
        self.row_id, self.key = None, None

    def tick(self, s: probe.Sample, now: float) -> None:
        away = s.idle >= self.cfg.idle_threshold or s.bundle in AWAY_BUNDLES or not s.bundle
        slept = self.last and now - self.last > 3 * self.cfg.interval

        if self.row_id is not None and (away or slept):
            # Credit up to when input stopped (or the last tick before a sleep)
            self._close(self.last if slept else max(now - s.idle, self.last))
        if away:
            self.last = now
            return

        if self.row_id is not None and s.key() == self.key:
            store.extend(self.con, self.row_id, now)
        else:
            if self.row_id is not None:
                self._close(now)
            self.row_id = store.insert(self.con, now, now, s)
            self.key = s.key()
            if self.console:
                cat = self.cfg.classify(s.__dict__)
                where = s.domain or s.detail or s.title[:60]
                self.console.print(
                    f"[dim]{time.strftime('%H:%M:%S')}[/dim] "
                    f"[bold]{self.cfg.label(cat)}[/bold]  {s.app}  [dim]{where}[/dim]"
                )
        self.last = now

    def check_limits(self, now: float) -> None:
        """Notify once per day when a max_hours limit is crossed."""
        from . import alerts, report

        day = dt.date.fromtimestamp(now)
        summary = report.summarize_day(self.con, self.cfg, day)
        for c in alerts.evaluate(summary, self.cfg):
            key = (day, c.alert.name)
            if c.over_max and key not in self.notified:
                self.notified.add(key)
                alerts.notify("scitime", c.line())

    def publish(self, now: float) -> None:
        """Write the combined Mac + iPhone dashboard where the phone can open it."""
        from pathlib import Path

        from . import dashboard

        out = Path(self.cfg.phone_dir).expanduser() / "scitime.html"
        dashboard.write(self.con, self.cfg, dt.date.fromtimestamp(now), 14, out)

    def run(self) -> None:
        while True:
            t = time.time()
            try:
                self.tick(probe.sample(), t)
                if self.cfg.alerts and t - self.last_check >= 60:
                    self.last_check = t
                    self.check_limits(t)
                if self.cfg.phone_dir and t - self.last_publish >= 600:
                    self.last_publish = t
                    self.publish(t)
            except Exception as e:  # keep the daemon alive through odd states
                if self.console:
                    self.console.print(f"[red]ERROR[/red] {e!r}")
            time.sleep(max(0.5, self.cfg.interval - (time.time() - t)))
