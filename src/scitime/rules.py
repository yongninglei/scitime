"""Load settings and categorisation rules, and sort a recorded segment into a category."""

from __future__ import annotations

import json
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

    def match(self, seg: dict) -> tuple[int, Rule] | None:
        """The first rule that matches, with its position (0-based), or None."""
        for i, rule in enumerate(self.rules):
            if rule.matches(seg):
                return i, rule
        return None

    def classify(self, seg: dict) -> str:
        m = self.match(seg)
        return m[1].category if m else "other"

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
        if r["category"] not in raw.get("categories", {}) and r["category"] != "other":
            raise ValueError(f"rule uses category {r['category']!r}, which has no [categories.{r['category']}] table")
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


# --- editing the user's rules file (used by `scitime add-category` / `add-rule`) ----------

MY_START = "# --- my rules (added by `scitime add-rule`; first match wins, so these beat the rules below) ---"
MY_END = "# --- end of my rules ---"
PALETTE = ["#e4572e", "#17bebb", "#76b041", "#ffc914", "#8e44ad", "#2e86ab", "#f18f01", "#c73e1d",
           "#3bb273", "#7768ae", "#e15554", "#4d9de0"]
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PLAIN_DOMAIN = re.compile(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", re.I)


def _toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # a JSON string is a valid TOML basic string


def _ensure_my_section(text: str) -> str:
    if MY_START in text:
        return text
    lines = text.splitlines(keepends=True)
    i = next((n for n, ln in enumerate(lines) if ln.strip() == "[[rule]]"), len(lines))
    while i > 0 and lines[i - 1].lstrip().startswith("#"):
        i -= 1  # keep the comment that heads the first rule attached to it
    return "".join(lines[:i]) + f"{MY_START}\n\n{MY_END}\n\n" + "".join(lines[i:])


def domain_pattern(value: str) -> str:
    """A plain domain like jov.arvojournals.org matches it and its subdomains; anything else is a regex."""
    if PLAIN_DOMAIN.match(value):
        host = value.lower().removeprefix("www.")  # recorded domains have www. stripped
        return r"(^|\.)" + re.escape(host) + "$"
    return value


def add_category_text(text: str, key: str, label: str = "", color: str = "", focus: bool | None = None) -> str:
    if not KEY_RE.match(key):
        raise ValueError(f"category key {key!r}: use lower case letters, digits and _, e.g. grant_writing")
    raw = tomllib.loads(text)
    cats = raw.get("categories", {})
    if key in cats:
        raise ValueError(f"category {key!r} already exists ({cats[key].get('label', key)})")
    if color and not re.match(r"^#[0-9a-fA-F]{6}$", color):
        raise ValueError(f"colour {color!r}: use #rrggbb")
    used = {str(c.get("color", "")).lower() for c in cats.values()}
    color = color or next((c for c in PALETTE if c not in used), PALETTE[len(cats) % len(PALETTE)])
    block = f"[categories.{key}]\nlabel = {_toml_str(label or key.replace('_', ' ').capitalize())}\ncolor = {_toml_str(color)}\n"
    if focus is not None:
        block += f"focus = {'true' if focus else 'false'}\n"
    text = _ensure_my_section(text)
    text = text.replace(MY_START, block + "\n" + MY_START, 1)
    parse(text)
    return text


def add_rule_text(text: str, category: str, fields: dict[str, str]) -> str:
    fields = {f: v for f, v in fields.items() if v}
    if not fields:
        raise ValueError("give at least one of --" + ", --".join(FIELDS))
    unknown = set(fields) - set(FIELDS)
    if unknown:
        raise ValueError(f"unknown field(s): {', '.join(sorted(unknown))}")
    if category not in tomllib.loads(text).get("categories", {}):
        raise ValueError(f"no category {category!r}; add it first with `scitime add-category {category}`")
    if "domain" in fields:
        fields["domain"] = domain_pattern(fields["domain"])
    for f, v in fields.items():
        try:
            re.compile(v)
        except re.error as e:
            raise ValueError(f"--{f} {v!r} is not a valid regex: {e}") from None
    block = f"[[rule]]\ncategory = {_toml_str(category)}\n" + "".join(f"{f} = {_toml_str(v)}\n" for f, v in fields.items())
    text = _ensure_my_section(text)
    text = text.replace(MY_END, block + "\n" + MY_END, 1)
    parse(text)
    return text


def save_user_rules(text: str) -> Path:
    """Write the user's rules, keeping the previous version as rules.toml.bak."""
    parse(text)
    init_user_rules()
    shutil.copyfile(USER_RULES, USER_RULES.with_suffix(".toml.bak"))
    USER_RULES.write_text(text)
    return USER_RULES


def user_rules_text() -> str:
    return USER_RULES.read_text() if USER_RULES.exists() else default_rules_text()
