"""Load settings and categorisation rules, and sort a recorded segment into a category."""

from __future__ import annotations

import re
import shutil
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "scitime"
USER_RULES = CONFIG_DIR / "rules.toml"
FIELDS = ("app", "bundle", "title", "url", "domain", "detail")


@dataclass
class Rule:
    category: str
    patterns: dict[str, re.Pattern]

    def matches(self, seg: dict) -> bool:
        return all(p.search(seg.get(f) or "") for f, p in self.patterns.items())


@dataclass
class Alert:
    name: str
    categories: list[str]
    min_hours: float | None = None
    max_hours: float | None = None


@dataclass
class Config:
    interval: float = 5.0
    idle_threshold: float = 300.0
    sync_dir: str = ""
    categories: dict[str, dict] = field(default_factory=dict)
    rules: list[Rule] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    digest_time: str = "21:00"
    email: str = ""
    phone_dir: str = ""  # iCloud folder shared with the iPhone Shortcuts; "" = no phone
    phone_max_minutes: float = 120.0

    def classify(self, seg: dict) -> str:
        for rule in self.rules:
            if rule.matches(seg):
                return rule.category
        return "other"

    def label(self, cat: str) -> str:
        return self.categories.get(cat, {}).get("label", cat)

    def color(self, cat: str) -> str:
        return self.categories.get(cat, {}).get("color", "#a3a3a3")


def default_rules_text() -> str:
    return resources.files("scitime").joinpath("default_rules.toml").read_text()


def parse(text: str) -> Config:
    raw = tomllib.loads(text)
    s = raw.get("settings", {})
    rules = []
    for r in raw.get("rule", []):
        pats = {f: re.compile(r[f], re.I) for f in FIELDS if f in r}
        if not pats:
            raise ValueError(f"rule for {r.get('category')!r} has no match fields")
        rules.append(Rule(r["category"], pats))
    return Config(
        interval=float(s.get("interval", 5)),
        idle_threshold=float(s.get("idle_threshold", 300)),
        sync_dir=str(s.get("sync_dir", "")),
        categories=raw.get("categories", {}),
        rules=rules,
        alerts=[
            Alert(a["name"], list(a["categories"]), a.get("min_hours"), a.get("max_hours"))
            for a in raw.get("alert", [])
        ],
        digest_time=str(raw.get("digest", {}).get("time", "21:00")),
        email=str(raw.get("digest", {}).get("email", "")),
        phone_dir=str(raw.get("phone", {}).get("dir", "")),
        phone_max_minutes=float(raw.get("phone", {}).get("max_session_minutes", 120)),
    )


def load(path: Path | None = None) -> Config:
    path = path or USER_RULES
    text = path.read_text() if path.exists() else default_rules_text()
    return parse(text)


def init_user_rules() -> tuple[Path, bool]:
    """Copy default rules to the user config. Never overwrites. Returns (path, created)."""
    if USER_RULES.exists():
        return USER_RULES, False
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with resources.as_file(resources.files("scitime").joinpath("default_rules.toml")) as src:
        shutil.copyfile(src, USER_RULES)
    return USER_RULES, True
