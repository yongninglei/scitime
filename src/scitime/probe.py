"""Read what the user is looking at right now: front app, window, URL, terminal job, idle time."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from urllib.parse import urlparse

import Quartz
from AppKit import NSWorkspace
from Foundation import NSDate, NSRunLoop

# Browsers that answer AppleScript "URL of active tab of front window"
CHROMIUM = {
    "com.google.Chrome",
    "com.google.Chrome.beta",
    "com.brave.Browser",
    "com.microsoft.edgemac",
    "com.vivaldi.Vivaldi",
    "company.thebrowser.Browser",  # Arc
    "org.chromium.Chromium",
}
SAFARI = {"com.apple.Safari", "com.apple.SafariTechnologyPreview"}

# Terminals whose front tab tty we can read with AppleScript
TTY_SCRIPTS = {
    "com.apple.Terminal": "get tty of selected tab of front window",
    "com.googlecode.iterm2": "get tty of current session of current window",
}
# Other terminals: only the window title tells us what runs
TERMINALS = set(TTY_SCRIPTS) | {
    "com.mitchellh.ghostty",
    "com.github.wez.wezterm",
    "dev.warp.Warp-Stable",
    "net.kovidgoyal.kitty",
    "io.alacritty",
}

REMOTE_CMDS = {"ssh", "mosh", "mosh-client", "autossh", "et"}
AI_CLIS = {"claude", "codex", "aider", "gemini", "cursor-agent", "opencode", "goose"}


@dataclass
class Sample:
    """One look at the screen."""

    app: str = ""
    bundle: str = ""
    title: str = ""
    url: str = ""
    domain: str = ""
    detail: str = ""  # e.g. "ssh:hpc-login" or "cli:claude"
    idle: float = 0.0

    def key(self) -> tuple:
        return (self.bundle, self.title, self.url, self.detail)


def _osascript(script: str, timeout: float = 2.0) -> str:
    """Run AppleScript; return "" on any error or timeout (never block the tracker)."""
    try:
        out = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def idle_seconds() -> float:
    return Quartz.CGEventSourceSecondsSinceLastEventType(
        Quartz.kCGEventSourceStateCombinedSessionState, Quartz.kCGAnyInputEventType
    )


def _front_app() -> tuple[str, str, int]:
    # NSWorkspace only refreshes frontmostApplication while a run loop spins
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return "", "", -1
    return str(app.localizedName() or ""), str(app.bundleIdentifier() or ""), int(app.processIdentifier())


def _window_title(pid: int) -> str:
    """Title of the top window of pid. Empty unless Screen Recording is granted."""
    opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
    for w in Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []:
        if w.get("kCGWindowOwnerPID") == pid and w.get("kCGWindowLayer", 1) == 0:
            name = w.get("kCGWindowName")
            if name:
                return str(name)
    return ""


def _browser_tab(bundle: str) -> tuple[str, str]:
    if bundle in CHROMIUM:
        script = (
            f'tell application id "{bundle}" to tell active tab of front window '
            "to return (URL as text) & linefeed & (title as text)"
        )
    elif bundle in SAFARI:
        script = (
            f'tell application id "{bundle}" to tell current tab of front window '
            "to return (URL as text) & linefeed & (name as text)"
        )
    else:
        return "", ""
    out = _osascript(script)
    url, _, title = out.partition("\n")
    return url, title


def _tty_jobs(tty: str) -> list[list[str]]:
    """argv of every process on this tty."""
    tty = tty.removeprefix("/dev/")
    try:
        out = subprocess.run(
            ["ps", "-t", tty, "-o", "args="], capture_output=True, text=True, timeout=2
        ).stdout
    except subprocess.TimeoutExpired:
        return []
    return [line.split() for line in out.splitlines() if line.strip()]


def _ssh_host(argv: list[str]) -> str:
    """Best guess at the host in an ssh/mosh command line."""
    takes_value = set("bcDEeFIiJLlmOoPpQRSWw")
    args = argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("-"):
            if len(a) == 2 and a[1] in takes_value:
                i += 1
            i += 1
            continue
        return a.split("@")[-1]
    return "?"


def classify_jobs(jobs: list[list[str]]) -> str:
    """Turn the processes on a terminal tab into a detail string."""
    names = [(argv[0].rsplit("/", 1)[-1].lstrip("-"), argv) for argv in jobs if argv]
    for name, argv in names:
        if name in REMOTE_CMDS:
            return f"ssh:{_ssh_host(argv)}"
    for name, argv in names:
        if name in AI_CLIS:
            return f"cli:{name}"
        # node-based CLIs show up as "node /path/to/claude"
        if name == "node" and len(argv) > 1:
            script = argv[1].rsplit("/", 1)[-1]
            if script in AI_CLIS:
                return f"cli:{script}"
    return ""


_TITLE_SSH = re.compile(r"\b(?:ssh|mosh)\s+(?:-\S+\s+)*(?:\S+@)?([\w.-]+)")
_TITLE_CLI = re.compile(r"\b(" + "|".join(sorted(AI_CLIS)) + r")\b")


def detail_from_title(title: str) -> str:
    if m := _TITLE_SSH.search(title):
        return f"ssh:{m.group(1)}"
    if m := _TITLE_CLI.search(title):
        return f"cli:{m.group(1)}"
    return ""


def domain_of(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.removeprefix("www.")


def sample() -> Sample:
    s = Sample(idle=idle_seconds())
    s.app, s.bundle, pid = _front_app()
    if pid > 0:
        s.title = _window_title(pid)
    if s.bundle in CHROMIUM or s.bundle in SAFARI:
        s.url, tab_title = _browser_tab(s.bundle)
        s.title = tab_title or s.title
        s.domain = domain_of(s.url)
    elif s.bundle in TERMINALS:
        if s.bundle in TTY_SCRIPTS:
            tty = _osascript(f'tell application id "{s.bundle}" to {TTY_SCRIPTS[s.bundle]}')
            if tty:
                s.detail = classify_jobs(_tty_jobs(tty))
        if not s.detail:
            s.detail = detail_from_title(s.title)
    return s
