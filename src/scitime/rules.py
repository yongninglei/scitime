"""Load settings and categorisation rules, and sort a recorded segment into a category."""

from __future__ import annotations

import json
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "scitime"
USER_RULES = CONFIG_DIR / "rules.toml"
USER_SITES = CONFIG_DIR / "sites.yaml"  # website -> category; checked before every rule in rules.toml
FIELDS = ("app", "bundle", "title", "url", "domain", "detail")


@dataclass
class Rule:
    category: str
    patterns: dict[str, re.Pattern]
    source: str = "rules.toml"

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


def load(path: Path | None = None, sites: Path | None = None, strict: bool = False) -> Config:
    """Rules from rules.toml, with sites.yaml in front. A broken sites.yaml is skipped with a
    warning (so a typo never stops the tracker) unless `strict`."""
    path = path or USER_RULES
    sites = sites or path.with_name(USER_SITES.name)
    text = path.read_text() if path.exists() else default_rules_text()
    cfg = parse(text)
    if sites.exists():
        try:
            cfg.rules = site_rules(sites.read_text(), cfg.categories) + cfg.rules
        except Exception as e:  # ValueError or a YAML syntax error
            if strict:
                raise ValueError(f"{sites}: {e}") from None
            print(f"scitime: ignoring {sites}: {e}", file=sys.stderr)
    return cfg


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


# --- sites.yaml: the simple way to put a website in a category -----------------------------

SITES_TEMPLATE = """\
# SciTime — your websites, sorted into your categories.
#
# Put a website under one of your category keys (list them with `uv run scitime categories`).
# These are checked before every rule in rules.toml, so they always win.
#
#   jov.arvojournals.org     that site and all its subdomains (a leading www. is ignored)
#   github.com/my-lab        only pages under that path
#
# Add one from the terminal:   uv run scitime add-site paper_reading jov.arvojournals.org
# Test where a page goes:      uv run scitime which --url https://jov.arvojournals.org/article.aspx
#
# Example:
#
# paper_reading:
#   - jov.arvojournals.org
#   - journals.plos.org
# vibe_coding:
#   - github.com/my-lab
"""


def normalize_site(site: str) -> str:
    """https://www.Example.org/lab/ -> example.org/lab"""
    site = site.strip()
    if "://" in site:
        site = site.split("://", 1)[1]
    host, _, path = site.partition("/")
    host = host.lower().removeprefix("www.")
    path = path.strip("/")
    return f"{host}/{path}" if path else host


def site_patterns(site: str) -> dict[str, str]:
    """Regexes for one sites.yaml entry: a domain, or a domain followed by a path."""
    host, _, path = normalize_site(site).partition("/")
    if not PLAIN_DOMAIN.match(host):
        raise ValueError(f"{site!r} is not a website like jov.arvojournals.org or github.com/my-lab "
                         "(for anything fancier use `scitime add-rule`)")
    if not path.strip("/"):
        return {"domain": domain_pattern(host)}
    return {"url": r"^https?://([^/]*\.)?" + re.escape(host) + "/" + re.escape(path)}


def parse_sites(text: str, categories: dict) -> dict[str, list[str]]:
    import yaml

    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("sites.yaml must be a mapping of category key -> list of websites")
    out: dict[str, list[str]] = {}
    seen: dict[str, str] = {}
    for cat, sites in data.items():
        if cat not in categories:
            raise ValueError(f"sites.yaml: no category {cat!r}; existing keys: {', '.join(categories)}")
        if sites is None:
            sites = []
        if not isinstance(sites, list):
            raise ValueError(f"sites.yaml: {cat} must be a list of websites (lines starting with '- ')")
        for s in sites:
            s = str(s).strip()
            site_patterns(s)
            key = normalize_site(s)
            if key in seen and seen[key] != cat:
                raise ValueError(f"sites.yaml: {s!r} is listed under both {seen[key]} and {cat}")
            seen[key] = cat
            out.setdefault(cat, []).append(s)
    return out


def site_rules(text: str, categories: dict) -> list[Rule]:
    return [
        Rule(cat, {f: re.compile(p, re.I) for f, p in site_patterns(s).items()}, source=f"sites.yaml: {s}")
        for cat, sites in parse_sites(text, categories).items() for s in sites
    ]


def add_site_text(text: str, category: str, site: str, categories: dict) -> str:
    """Add `site` under `category` in sites.yaml text, keeping the user's comments and layout."""
    site_patterns(site)
    site = normalize_site(site)
    current = parse_sites(text, categories)
    if category not in categories:
        raise ValueError(f"no category {category!r}; existing keys: {', '.join(categories)}")
    for cat, sites in current.items():
        if site in (normalize_site(s) for s in sites):
            raise ValueError(f"{site} is already in sites.yaml under {cat}")
    lines = text.splitlines()
    head = next((i for i, ln in enumerate(lines) if re.match(rf"^{re.escape(category)}:\s*(#.*)?$", ln)), None)
    if head is None:
        if category in current:
            raise ValueError(f"sites.yaml: {category} is not written as a '- ' list; edit it by hand")
        if lines and lines[-1].strip():
            lines.append("")
        lines += [f"{category}:", f"  - {site}"]
    else:
        last = head
        for i in range(head + 1, len(lines)):
            if lines[i].strip() and not lines[i][0].isspace():
                break
            if lines[i].strip().startswith("- "):
                last = i
        lines.insert(last + 1, f"  - {site}")
    new = "\n".join(lines) + "\n"
    parse_sites(new, categories)
    return new


def user_sites_text() -> str:
    return USER_SITES.read_text() if USER_SITES.exists() else SITES_TEMPLATE


def save_user_sites(text: str) -> Path:
    """Write sites.yaml, keeping the previous version as sites.yaml.bak."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if USER_SITES.exists():
        shutil.copyfile(USER_SITES, USER_SITES.with_suffix(".yaml.bak"))
    USER_SITES.write_text(text)
    return USER_SITES


def init_user_sites() -> tuple[Path, bool]:
    if USER_SITES.exists():
        return USER_SITES, False
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    USER_SITES.write_text(SITES_TEMPLATE)
    return USER_SITES, True
