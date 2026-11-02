"""Menu bar item: today's time in the bar, per-category breakdown and goal checks in the menu."""

from __future__ import annotations

import datetime as dt
import subprocess
from dataclasses import dataclass, field

from . import alerts, report, rules, store
from .report import fmt

REFRESH_SECONDS = 60
STALE_SECONDS = 120  # no sample for this long while active = tracker probably stopped


@dataclass
class Row:
    text: str
    color: str | None = None  # dot colour; None = plain line
    children: list[str] = field(default_factory=list)  # submenu lines


@dataclass
class View:
    title: str
    rows: list[Row | None]  # None = separator


def build(s: report.DaySummary, cfg: rules.Config, checks: list[alerts.Check],
          last_sample: float | None, now: float, n_top: int = 5) -> View:
    """What the bar and its menu show. Pure, so it can be tested without AppKit."""
    warn = any(c.over_max for c in checks)
    title = f"{'⚠️ ' if warn else '⏱ '}{fmt(s.total)}"
    mac, ph = sum(s.by_device["mac"].values()), sum(s.by_device["phone"].values())
    head = f"Today {fmt(s.total)}" + (f"  ·  💻 {fmt(mac)}  ·  📱 {fmt(ph)}" if ph else "")
    rows: list[Row | None] = [Row(head), None]
    total = s.total or 1
    for c, sec in s.by_category.most_common():
        top = [f"{k}   {fmt(v)}" for k, v in s.top[c].most_common(n_top)]
        rows.append(Row(f"{cfg.label(c)}   {fmt(sec)}  ({sec / total * 100:.0f}%)", cfg.color(c), top))
    if not s.by_category:
        rows.append(Row("No data yet today"))
    if checks:
        rows += [None] + [Row(c.line()) for c in checks]
    if last_sample is None or now - last_sample > STALE_SECONDS:
        when = "never" if last_sample is None else f"{fmt(now - last_sample)} ago"
        rows += [None, Row(f"Last sample {when} — is the tracker running?")]
    return View(title, rows)


def current_view() -> View:
    cfg = rules.load()
    con = store.connect()
    now = dt.datetime.now().timestamp()
    s = report.summarize_day(con, cfg, dt.date.today())
    last = con.execute("SELECT MAX(end) AS t FROM segments").fetchone()["t"]
    con.close()
    return build(s, cfg, alerts.evaluate(s, cfg), last, now)


def run() -> None:
    """Show the menu bar item until Quit. Blocks in the Cocoa run loop."""
    import objc
    from AppKit import (
        NSApplication,
        NSApplicationActivationPolicyAccessory,
        NSAttributedString,
        NSColor,
        NSFont,
        NSFontAttributeName,
        NSForegroundColorAttributeName,
        NSMenu,
        NSMenuItem,
        NSStatusBar,
        NSVariableStatusItemLength,
    )
    from Foundation import NSObject, NSTimer
    from PyObjCTools import AppHelper

    def hex_color(h: str):
        h = h.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        return NSColor.colorWithSRGBRed_green_blue_alpha_(r, g, b, 1.0)

    def dotted(text: str, color: str):
        out = NSAttributedString.alloc().initWithString_attributes_(
            "● ", {NSForegroundColorAttributeName: hex_color(color)}
        ).mutableCopy()
        out.appendAttributedString_(NSAttributedString.alloc().initWithString_(text))
        return out

    class Bar(NSObject):
        def setup(self):
            self.item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
            self.item.button().setFont_(NSFont.monospacedDigitSystemFontOfSize_weight_(13, 0))
            self.refresh_(None)
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                REFRESH_SECONDS, self, "refresh:", None, True
            )

        @objc.python_method
        def _action(self, menu, title, selector):
            it = menu.addItemWithTitle_action_keyEquivalent_(title, selector, "")
            it.setTarget_(self)

        @objc.typedSelector(b"v@:@")
        def refresh_(self, _sender):
            try:
                view = current_view()
            except Exception as e:  # keep the bar alive (e.g. DB locked mid-write)
                self.item.button().setTitle_(f"⏱ ?  {type(e).__name__}")
                return
            self.item.button().setTitle_(view.title)
            menu = NSMenu.alloc().init()
            menu.setAutoenablesItems_(False)
            for row in view.rows:
                if row is None:
                    menu.addItem_(NSMenuItem.separatorItem())
                    continue
                it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(row.text, None, "")
                if row.color:
                    it.setAttributedTitle_(dotted(row.text, row.color))
                if row.children:
                    sub = NSMenu.alloc().init()
                    sub.setAutoenablesItems_(False)
                    for line in row.children:
                        sub.addItemWithTitle_action_keyEquivalent_(line, None, "")
                    it.setSubmenu_(sub)
                menu.addItem_(it)
            menu.addItem_(NSMenuItem.separatorItem())
            self._action(menu, "Open dashboard", "openDashboard:")
            self._action(menu, "Refresh now", "refresh:")
            self._action(menu, "Quit scitime bar", "quit:")
            self.item.setMenu_(menu)

        @objc.typedSelector(b"v@:@")
        def openDashboard_(self, _sender):
            from . import dashboard

            out = store.DATA_DIR / "dashboard.html"
            con = store.connect()
            dashboard.write(con, rules.load(), dt.date.today(), 14, out)
            con.close()
            subprocess.run(["open", str(out)], check=False)

        @objc.typedSelector(b"v@:@")
        def quit_(self, _sender):
            NSApplication.sharedApplication().terminate_(None)

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # no Dock icon
    bar = Bar.alloc().init()
    bar.setup()
    AppHelper.runEventLoop()
