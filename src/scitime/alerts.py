"""Check daily limits, show macOS notifications, and send the evening digest via Mail.app."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .report import DaySummary, fmt
from .rules import Alert, Config


@dataclass
class Check:
    alert: Alert
    seconds: float
    over_max: bool
    under_min: bool

    @property
    def ok(self) -> bool:
        return not (self.over_max or self.under_min)

    def line(self) -> str:
        a = self.alert
        if self.over_max:
            return f"⚠️ {a.name}: {fmt(self.seconds)} — over the {a.max_hours:g} h limit"
        if self.under_min:
            return f"⚠️ {a.name}: {fmt(self.seconds)} — below the {a.min_hours:g} h goal"
        target = f"goal {a.min_hours:g} h" if a.min_hours is not None else f"limit {a.max_hours:g} h"
        return f"✅ {a.name}: {fmt(self.seconds)} ({target})"


def evaluate(s: DaySummary, cfg: Config) -> list[Check]:
    out = []
    for a in cfg.alerts:
        sec = sum(s.by_category.get(c, 0) for c in a.categories)
        out.append(
            Check(
                a,
                sec,
                over_max=a.max_hours is not None and sec > a.max_hours * 3600,
                under_min=a.min_hours is not None and sec < a.min_hours * 3600,
            )
        )
    return out


def _as_applescript(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def notify(title: str, message: str) -> None:
    subprocess.run(
        [
            "osascript",
            "-e",
            f"display notification {_as_applescript(message)} with title {_as_applescript(title)} "
            'sound name "Submarine"',
        ],
        capture_output=True,
        timeout=10,
    )


def digest_text(s: DaySummary, cfg: Config, checks: list[Check], n_top: int = 3) -> str:
    lines = [f"scitime — {s.day:%A %d %B %Y}", f"Active on the Mac: {fmt(s.total)}", ""]
    if checks:
        lines += [c.line() for c in checks] + [""]
    for c, sec in s.by_category.most_common():
        top = ", ".join(f"{k} {fmt(v)}" for k, v in s.top[c].most_common(n_top))
        lines.append(f"{cfg.label(c):<20} {fmt(sec):>8}   {top}")
    return "\n".join(lines)


def send_mail(to: str, subject: str, body: str, attachment: Path | None = None) -> tuple[bool, str]:
    """Send through Mail.app with the user's own account. Returns (ok, error)."""
    attach = ""
    if attachment and attachment.exists():
        attach = (
            "tell content of m to make new attachment with properties "
            f"{{file name:(POSIX file {_as_applescript(str(attachment))})}} at after last paragraph\n"
        )
    script = f"""
tell application "Mail"
    set m to make new outgoing message with properties {{subject:{_as_applescript(subject)}, content:{_as_applescript(body)}, visible:false}}
    tell m to make new to recipient at end of to recipients with properties {{address:{_as_applescript(to)}}}
    {attach}
    delay 1
    send m
end tell
"""
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)
    return r.returncode == 0, r.stderr.strip()
