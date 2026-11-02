"""Render a self-contained HTML dashboard (no network, inline SVG), styled after Tai."""

from __future__ import annotations

import datetime as dt
import math
from html import escape

from .report import DaySummary, fmt
from .rules import Config

# Categories that count as research work; the rest is shown as distraction or other.
FOCUS = {"vibe_coding", "paper_writing", "data_analysis", "figures", "server"}
DISTRACTION = {"browsing", "social"}

CSS = """
:root { --bg:#f3f4f8; --card:#ffffff; --fg:#1d1f2b; --muted:#7a7f93; --line:#e8eaf1;
        --soft:#f6f7fb; --accent:#5b5bf0; --accent-soft:#ececfe; --good:#1f9d6b; --bad:#e0445e;
        --shadow: 0 1px 2px rgba(20,22,40,.04), 0 6px 24px rgba(20,22,40,.06); }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111218; --card:#1b1c25; --fg:#eceef5; --muted:#9296a8; --line:#2a2c38;
          --soft:#22232e; --accent:#8b8bff; --accent-soft:#2a2a4a; --good:#3ccf91; --bad:#ff6b81;
          --shadow: none; }
}
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font: 14px/1.5 -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
       -webkit-font-smoothing: antialiased; }
main { max-width: 1080px; margin: 0 auto; padding: 28px 16px 56px; }
header { display:flex; align-items:center; justify-content:space-between; gap:12px;
         flex-wrap:wrap; margin-bottom: 20px; }
.brand { display:flex; align-items:center; gap:10px; font-weight:700; font-size:17px; }
.logo { width:30px; height:30px; border-radius:9px; display:grid; place-items:center;
        background: linear-gradient(135deg, #6d6df7, #a35cf0); color:#fff; font-size:15px; }
.date { color:var(--muted); }
h2 { font-size:15px; font-weight:650; margin:0 0 14px; }
.card { background:var(--card); border-radius:16px; padding:18px 20px; box-shadow:var(--shadow);
        border:1px solid var(--line); min-width:0; }
.stats { display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:14px; }
.stat .k { color:var(--muted); font-size:12.5px; display:flex; align-items:center; gap:8px; }
.stat .v { font-size:28px; font-weight:700; letter-spacing:-.02em; margin-top:4px;
           font-variant-numeric: tabular-nums; }
.stat .s { color:var(--muted); font-size:12.5px; margin-top:2px; }
.chip { width:26px; height:26px; border-radius:8px; display:grid; place-items:center; font-size:14px;
        background:var(--accent-soft); }
.row { display:grid; grid-template-columns: 340px 1fr; gap:14px; margin-top:14px; }
@media (max-width: 820px) { .row { grid-template-columns: 1fr; } }
.donut { display:flex; flex-direction:column; align-items:center; gap:10px; }
.donut .c { font-size:22px; font-weight:700; fill:var(--fg); }
.donut .l { font-size:11px; fill:var(--muted); }
.legend { width:100%; display:grid; grid-template-columns: 1fr 1fr; gap:6px 12px;
          font-size:12.5px; color:var(--muted); }
.legend div { display:flex; align-items:center; gap:7px; min-width:0; }
.legend span.n { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.dot { width:9px; height:9px; border-radius:50%; flex:none; }
.rank { display:flex; flex-direction:column; gap:12px; }
.item { display:grid; grid-template-columns: 34px 1fr auto; gap:12px; align-items:center; }
.icon { width:34px; height:34px; border-radius:10px; display:grid; place-items:center;
        font-weight:700; font-size:14px; color:#fff; }
.item .name { font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.item .sub { color:var(--muted); font-size:12px; }
.bar { height:6px; border-radius:3px; background:var(--soft); overflow:hidden; margin-top:6px; }
.bar i { display:block; height:100%; border-radius:3px; }
.item .t { font-variant-numeric: tabular-nums; font-weight:600; text-align:right; }
.item .p { color:var(--muted); font-size:12px; text-align:right; }
.wide { margin-top:14px; }
svg text { fill: var(--muted); font-size: 11px; font-family: inherit; }
svg .grid { stroke: var(--line); stroke-width: 1; }
.goals { display:flex; flex-direction:column; gap:8px; }
.goal { display:flex; justify-content:space-between; gap:10px; padding:10px 12px; border-radius:10px;
        background:var(--soft); }
.goal.ok b { color:var(--good); } .goal.bad b { color:var(--bad); }
.empty { color:var(--muted); padding: 8px 0; }
footer { color:var(--muted); font-size:12px; text-align:center; margin-top:26px; }
"""


def _icon(name: str, color: str) -> str:
    letter = escape((name.lstrip("📱 ") or "?")[0].upper())
    return f'<div class="icon" style="background:{color}">{letter}</div>'


def _donut(day: DaySummary, cfg: Config) -> str:
    r, w = 62, 18
    circ = 2 * math.pi * r
    total = day.total or 1
    parts = [f'<svg viewBox="0 0 160 160" width="190" height="190" role="img" aria-label="Time by category">'
             f'<circle cx="80" cy="80" r="{r}" fill="none" stroke="var(--soft)" stroke-width="{w}"/>']
    offset = 0.0
    for c, sec in day.by_category.most_common():
        length = sec / total * circ
        gap = 1.5 if length > 3 else 0
        parts.append(
            f'<circle cx="80" cy="80" r="{r}" fill="none" stroke="{cfg.color(c)}" stroke-width="{w}" '
            f'stroke-dasharray="{max(length - gap, 0):.2f} {circ:.2f}" stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 80 80)"><title>{escape(cfg.label(c))} {fmt(sec)}</title></circle>'
        )
        offset += length
    parts.append(f'<text class="c" x="80" y="82" text-anchor="middle">{fmt(day.total)}</text>'
                 '<text class="l" x="80" y="100" text-anchor="middle">active today</text></svg>')
    return "".join(parts)


def _stacked_bars(columns: list[tuple[str, dict]], cfg: Config, cats: list[str], peak: float,
                  height: int, label_every: int, tip) -> str:
    """Rounded stacked bars; columns are (label, {category: seconds})."""
    w, pad_l, pad_b = 1000, 40, 22
    n = max(len(columns), 1)
    slot = (w - pad_l) / n
    bw = min(slot * 0.62, 34)
    parts = [f'<svg viewBox="0 0 {w} {height + pad_b}" width="100%" role="img">']
    for frac in (0.5, 1.0):
        y = height - frac * height
        parts.append(f'<line class="grid" x1="{pad_l}" x2="{w}" y1="{y:.1f}" y2="{y:.1f}"/>'
                     f'<text x="0" y="{y + 4:.1f}">{fmt(peak * frac)}</text>')
    for i, (label, by_cat) in enumerate(columns):
        x = pad_l + i * slot + (slot - bw) / 2
        total = sum(by_cat.values())
        if total > 0:
            th = total / peak * height
            parts.append(f'<clipPath id="b{height}_{i}"><rect x="{x:.1f}" y="{height - th:.1f}" '
                         f'width="{bw:.1f}" height="{th:.1f}" rx="{min(bw / 2, 6):.1f}"/></clipPath>'
                         f'<g clip-path="url(#b{height}_{i})">')
            y = height
            for c in cats:
                sec = by_cat.get(c, 0)
                if sec <= 0:
                    continue
                bh = sec / peak * height
                y -= bh
                parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh + 0.5:.1f}" '
                             f'fill="{cfg.color(c)}"><title>{escape(tip(label, c, sec))}</title></rect>')
            parts.append("</g>")
        if i % label_every == 0:
            parts.append(f'<text x="{x + bw / 2:.1f}" y="{height + 16}" text-anchor="middle">{escape(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def render(today: DaySummary, days: list[DaySummary], cfg: Config) -> str:
    from . import alerts

    cats = list(cfg.categories) + sorted({c for d in days for c in d.by_category} - set(cfg.categories))
    total = today.total or 1
    focus = sum(v for c, v in today.by_category.items() if c in FOCUS)
    distract = sum(v for c, v in today.by_category.items() if c in DISTRACTION)
    mac, ph = sum(today.by_device["mac"].values()), sum(today.by_device["phone"].values())
    week = days[-7:]
    week_avg = sum(d.total for d in week) / max(len(week), 1)

    stats = [
        ("⏱", "Active today", fmt(today.total), f"💻 {fmt(mac)}" + (f" · 📱 {fmt(ph)}" if ph else "")),
        ("🔬", "Research focus", fmt(focus), f"{focus / total * 100:.0f}% of the day"),
        ("📺", "Browsing + social", fmt(distract), f"{distract / total * 100:.0f}% of the day"),
        ("📅", "7-day average", fmt(week_avg), f"over {len(week)} days"),
    ]
    stat_html = "".join(
        f'<div class="card stat"><div class="k"><span class="chip">{i}</span>{k}</div>'
        f'<div class="v">{v}</div><div class="s">{s}</div></div>' for i, k, v, s in stats
    )

    legend = "".join(
        f'<div><span class="dot" style="background:{cfg.color(c)}"></span><span class="n">{escape(cfg.label(c))}</span></div>'
        for c, _ in today.by_category.most_common()
    )

    peak_cat = max(today.by_category.values(), default=1)
    ranking = "".join(
        f'<div class="item">{_icon(cfg.label(c), cfg.color(c))}<div style="min-width:0">'
        f'<div class="name">{escape(cfg.label(c))}</div>'
        f'<div class="sub">{escape(", ".join(k for k, _ in today.top[c].most_common(3)))}</div>'
        f'<div class="bar"><i style="width:{sec / peak_cat * 100:.1f}%;background:{cfg.color(c)}"></i></div></div>'
        f'<div><div class="t">{fmt(sec)}</div><div class="p">{sec / total * 100:.0f}%</div></div></div>'
        for c, sec in today.by_category.most_common()
    ) or '<div class="empty">No activity recorded yet today.</div>'

    top_items = sorted(
        ((c, k, v) for c, ctr in today.top.items() for k, v in ctr.items()), key=lambda x: -x[2]
    )[:8]
    peak_item = top_items[0][2] if top_items else 1
    most_used = "".join(
        f'<div class="item">{_icon(k, cfg.color(c))}<div style="min-width:0">'
        f'<div class="name">{escape(k)}</div><div class="sub">{escape(cfg.label(c))}</div>'
        f'<div class="bar"><i style="width:{v / peak_item * 100:.1f}%;background:{cfg.color(c)}"></i></div></div>'
        f'<div class="t">{fmt(v)}</div></div>'
        for c, k, v in top_items
    ) or '<div class="empty">Nothing yet.</div>'

    goals = "".join(
        f'<div class="goal {"ok" if ch.ok else "bad"}"><span>{escape(ch.alert.name)}</span><b>{escape(ch.line().split(": ", 1)[-1])}</b></div>'
        for ch in alerts.evaluate(today, cfg)
    ) or '<div class="empty">No goals set — add [[alert]] entries to rules.toml.</div>'

    hourly = _stacked_bars(
        [(f"{h:02d}", today.by_hour.get(h, {})) for h in range(24)], cfg, cats, 3600, 150, 3,
        lambda lab, c, s: f"{lab}:00 · {cfg.label(c)} {fmt(s)}",
    )
    peak_day = max((d.total for d in days), default=0) or 3600
    daily = _stacked_bars(
        [(d.day.strftime("%a %d"), d.by_category) for d in days], cfg, cats, peak_day, 190,
        1 if len(days) <= 14 else 2, lambda lab, c, s: f"{lab} · {cfg.label(c)} {fmt(s)}",
    )

    generated = dt.datetime.now().strftime("%H:%M")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SciTime — {today.day}</title><style>{CSS}</style></head>
<body><main>
<header><div class="brand"><div class="logo">⚗︎</div>SciTime</div>
<div class="date">{today.day.strftime("%A, %d %B %Y")} · updated {generated}</div></header>
<section class="stats">{stat_html}</section>
<section class="row">
  <div class="card donut"><h2 style="align-self:flex-start">Today</h2>{_donut(today, cfg)}<div class="legend">{legend}</div></div>
  <div class="card"><h2>Categories</h2><div class="rank">{ranking}</div></div>
</section>
<section class="row">
  <div class="card"><h2>Goals</h2><div class="goals">{goals}</div></div>
  <div class="card"><h2>Most used</h2><div class="rank">{most_used}</div></div>
</section>
<section class="card wide"><h2>Hour by hour</h2>{hourly}</section>
<section class="card wide"><h2>Last {len(days)} days</h2>{daily}</section>
<footer>SciTime — everything stays on this Mac.</footer>
</main></body></html>
"""


def write(con, cfg: Config, day: dt.date, days: int, out) -> None:
    """Summarise the last `days` days ending at `day` and write the dashboard to `out`."""
    from . import report

    hist = [report.summarize_day(con, cfg, day - dt.timedelta(days=i)) for i in range(days - 1, -1, -1)]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(hist[-1], hist, cfg))
