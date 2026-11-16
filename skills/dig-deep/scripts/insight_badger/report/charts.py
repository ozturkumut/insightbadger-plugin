"""SVG and HTML chart builders. Pure functions: data in, markup out.

Charts are inline SVG, so reports work offline, print sharply, and look the
same every time. Colours come from CSS classes, so a custom brand recolours
them automatically.
"""

from __future__ import annotations

import math
from html import escape


def e(x) -> str:
    return escape("" if x is None else str(x), quote=True)


def fmt_signed(v, digits: int = 0) -> str:
    if v is None:
        return "–"
    v = round(float(v), digits)
    s = f"{abs(v):.{digits}f}"
    return ("+" if v > 0 else "−" if v < 0 else "") + s


def fmt_pct(v, digits: int = 0) -> str:
    return "–" if v is None else f"{float(v):.{digits}f}%"


def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    span = hi - lo
    if span <= 0:
        return [lo]
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw), default=raw)
    start = math.ceil(lo / step) * step
    ticks = []
    v = start
    while v <= hi + 1e-9:
        ticks.append(round(v, 6))
        v += step
    return ticks


def _clip(label: str, n: int) -> str:
    label = str(label)
    return label if len(label) <= n else label[: n - 1].rstrip() + "…"


# ── NPS composition bar ──────────────────────────────────────────────────────

def nps_bar(detail: dict) -> str:
    d, p, pr = detail["detractors"], detail["passives"], detail["promoters"]
    def seg(cls, v):
        lab = f"{v:.0f}%" if v >= 6 else ""
        return f'<span class="{cls}" style="width:{v}%">{lab}</span>' if v > 0 else ""
    return (f'<div class="npsbar num" role="img" aria-label="Detractors {d:.0f} percent, passives {p:.0f} percent, '
            f'promoters {pr:.0f} percent">{seg("det", d)}{seg("pas", p)}{seg("pro", pr)}</div>'
            '<div class="legend"><span><i style="background:var(--clay)"></i>Detractors (0–6)</span>'
            '<span><i style="background:var(--neutral)"></i>Passives (7–8)</span>'
            '<span><i style="background:var(--teal)"></i>Promoters (9–10)</span></div>')


# ── Key-driver matrix ────────────────────────────────────────────────────────

ZONE = {"fix": ("clay", "FIX FIRST"), "protect": ("teal", "STRENGTHS TO PROTECT"),
        "monitor": ("ochre", "MONITOR"), "nice": ("slate", "NICE TO HAVE")}


def driver_matrix(block: dict, labels: dict[str, str]) -> str:
    rows = block["drivers"]
    W, H = 640, 410
    x0, x1, y0, y1 = 60, 610, 20, 350
    xmax = max(10, math.ceil(max(r["importance"] for r in rows) / 10) * 10)
    pmin = min(r["performance"] for r in rows)
    pmax = max(r["performance"] for r in rows)
    ylo = max(0, math.floor((pmin - 5) / 10) * 10)
    yhi = min(100, math.ceil((pmax + 5) / 10) * 10)
    if yhi - ylo < 30:
        yhi = min(100, ylo + 30)
        ylo = max(0, yhi - 30)

    def X(v):
        return x0 + v / xmax * (x1 - x0)

    def Y(v):
        return y1 - (v - ylo) / (yhi - ylo) * (y1 - y0)

    sx, sy = X(block["split_importance"]), Y(block["split_performance"])
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{e(_driver_alt(rows, labels))}">']
    out.append(f'<rect class="z-slate" x="{x0}" y="{y0}" width="{sx - x0:.1f}" height="{sy - y0:.1f}"/>')
    out.append(f'<rect class="z-teal" x="{sx:.1f}" y="{y0}" width="{x1 - sx:.1f}" height="{sy - y0:.1f}"/>')
    out.append(f'<rect class="z-ochre" x="{x0}" y="{sy:.1f}" width="{sx - x0:.1f}" height="{y1 - sy:.1f}"/>')
    out.append(f'<rect class="z-clay" x="{sx:.1f}" y="{sy:.1f}" width="{x1 - sx:.1f}" height="{y1 - sy:.1f}"/>')
    out.append('<g class="grid-w">')
    for t in _nice_ticks(ylo, yhi, 5):
        out.append(f'<line x1="{x0}" y1="{Y(t):.1f}" x2="{x1}" y2="{Y(t):.1f}"/>')
    for t in _nice_ticks(0, xmax, 4):
        out.append(f'<line x1="{X(t):.1f}" y1="{y0}" x2="{X(t):.1f}" y2="{y1}"/>')
    out.append('</g>')
    out.append(f'<line class="axis" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}"/><line class="axis" x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}"/>')
    out.append('<g class="num">')
    for t in _nice_ticks(ylo, yhi, 5):
        out.append(f'<text class="t-muted" x="{x0 - 8}" y="{Y(t) + 4:.1f}" text-anchor="end">{t:g}%</text>')
    for t in _nice_ticks(0, xmax, 4):
        out.append(f'<text class="t-muted" x="{X(t):.1f}" y="{y1 + 18}" text-anchor="middle">{t:g}%</text>')
    out.append('</g>')
    out.append(f'<text class="t-muted" x="{(x0 + x1) / 2}" y="{H - 14}" text-anchor="middle">Importance for the KPI</text>')
    out.append(f'<text class="t-muted" x="14" y="{(y0 + y1) / 2}" text-anchor="middle" transform="rotate(-90 14 {(y0 + y1) / 2})">Rated well</text>')
    out.append(f'<text class="q-lab c-clay" x="{x1 - 10}" y="{y1 - 10}" text-anchor="end">FIX FIRST</text>')
    out.append(f'<text class="q-lab c-teal" x="{x1 - 10}" y="{y0 + 18}" text-anchor="end">STRENGTHS TO PROTECT</text>')
    out.append(f'<text class="q-lab c-slate" x="{x0 + 10}" y="{y0 + 18}">NICE TO HAVE</text>')
    out.append(f'<text class="q-lab c-ochre" x="{x0 + 10}" y="{y1 - 10}">MONITOR</text>')

    # Labels: place right of the point unless near the right edge; nudge apart vertically
    placed: list[tuple[float, float, str]] = []
    pts = []
    for r in sorted(rows, key=lambda r: Y(r["performance"])):
        cx, cy = X(r["importance"]), Y(r["performance"])
        color = ZONE[r["zone"]][0]
        lab = _clip(labels.get(r["column"], r["label"]), 30)
        side = "end" if cx > x0 + (x1 - x0) * 0.62 else "start"
        ly = cy + 4
        for (px, py, ps) in placed:
            if ps == side and abs(px - cx) < 170 and abs(py - ly) < 14:
                ly = py + 14
        placed.append((cx, ly, side))
        pts.append((cx, cy, ly, side, color, lab, r["zone"] == "fix"))
    for cx, cy, ly, side, color, lab, big in pts:
        r_ = 9 if big else 6.5
        tx = cx - (r_ + 5) if side == "end" else cx + (r_ + 5)
        out.append(f'<circle class="d-{color}" cx="{cx:.1f}" cy="{cy:.1f}" r="{r_}"/>')
        out.append(f'<text class="c-{color}{" t-strong" if big else ""}" x="{tx:.1f}" y="{ly:.1f}" text-anchor="{side}">{e(lab)}</text>')
    out.append('</svg>')
    return "".join(out)


def _driver_alt(rows, labels) -> str:
    parts = [f"{labels.get(r['column'], r['label'])}: importance {r['importance']:.0f} percent, "
             f"rated well by {r['performance']:.0f} percent, {ZONE[r['zone']][1].lower()}" for r in rows]
    return "Key drivers. " + "; ".join(parts)


# ── Group dot plot with likely ranges ────────────────────────────────────────

def group_dots(comp: dict, kpi: dict, highlight: list[str] | None = None) -> str:
    groups = [g for g in comp["groups"] if g.get("value_metric") is not None]
    is_nps = kpi["kind"] == "nps"
    vals = [v for g in groups for v in (g["ci"] or [g["value_metric"]] * 2)] + [kpi["value"]]
    lo = min(vals) - 5
    hi = max(vals) + 5
    if is_nps:
        lo, hi = max(-100, math.floor(lo / 20) * 20), min(100, math.ceil(hi / 20) * 20)
    else:
        lo, hi = max(0, math.floor(lo / 10) * 10), min(100, math.ceil(hi / 10) * 10)
    if highlight is None:
        real = [g for g in groups if g.get("verdict") == "real" and (g.get("gap_vs_rest") or 0) < 0]
        highlight = [min(real, key=lambda g: g["value_metric"])["value"]] if real else []
    W = 640
    row_h = 45
    top = 22
    H = top + row_h * len(groups) + 30
    x0, x1 = 170, 620

    def X(v):
        return x0 + (v - lo) / (hi - lo) * (x1 - x0)

    ticks = _nice_ticks(lo, hi, 4)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{e(_dots_alt(groups, is_nps))}">']
    for i, g in enumerate(groups):
        if g["value"] in highlight:
            out.append(f'<rect class="pill-clay" x="0" y="{top + i * row_h:.1f}" width="{W}" height="{row_h - 2}" rx="8"/>')
    out.append('<g class="grid">' + "".join(f'<line x1="{X(t):.1f}" y1="{top - 4}" x2="{X(t):.1f}" y2="{H - 30}"/>' for t in ticks) + '</g>')
    rx = X(kpi["value"])
    out.append(f'<line class="ref" x1="{rx:.1f}" y1="{top - 10}" x2="{rx:.1f}" y2="{H - 30}"/>')
    anchor = "end" if rx > x1 - 80 else "start"
    out.append(f'<text class="c-ochre t-strong" style="font-size:11px" x="{rx + (-4 if anchor == "end" else 4):.1f}" y="{top - 10}" text-anchor="{anchor}">overall {fmt_signed(kpi["value"]) if is_nps else fmt_pct(kpi["value"])}</text>')
    for i, g in enumerate(groups):
        cy = top + i * row_h + 22
        hl = g["value"] in highlight
        small = g.get("small_base")
        cls = "clay" if hl else ("grey" if small else "teal")
        lab_cls = "c-clay" if hl else ("c-grey" if small else "")
        out.append(f'<text class="{lab_cls}" x="10" y="{cy - 2:.1f}">{e(_clip(g["value"], 24))}</text>')
        out.append(f'<text class="t-muted num" x="10" y="{cy + 13:.1f}">n = {g["n"]}{" · small group" if small else ""}</text>')
        if g.get("ci"):
            out.append(f'<line class="ci-{cls}" x1="{X(g["ci"][0]):.1f}" y1="{cy:.1f}" x2="{X(g["ci"][1]):.1f}" y2="{cy:.1f}"/>')
        dot = "d-hollow" if small else f"d-{cls}"
        out.append(f'<circle class="{dot}" cx="{X(g["value_metric"]):.1f}" cy="{cy:.1f}" r="{8 if hl else 6.5}"/>')
        val = fmt_signed(g["value_metric"]) if is_nps else fmt_pct(g["value_metric"])
        out.append(f'<text class="{"c-clay" if hl else "c-grey" if small else "c-teal t-strong"} num" x="{X(g["value_metric"]):.1f}" y="{cy - 12:.1f}" text-anchor="middle">{val}</text>')
    out.append('<g class="num">' + "".join(
        f'<text class="t-muted" x="{X(t):.1f}" y="{H - 10}" text-anchor="middle">{fmt_signed(t) if is_nps else f"{t:g}%"}</text>'
        for t in ticks) + '</g></svg>')
    return "".join(out)


def _dots_alt(groups, is_nps) -> str:
    return "; ".join(f"{g['value']}: {fmt_signed(g['value_metric']) if is_nps else fmt_pct(g['value_metric'])} "
                     f"from {g['n']} people" for g in groups)


# ── Two-group dumbbell ───────────────────────────────────────────────────────

def dumbbell(pair: dict, labels: dict[str, str], max_items: int = 10) -> str:
    items = pair["items"][:max_items]
    W = 640
    row_h = 40
    top = 16
    H = top + row_h * len(items) + 34
    x0, x1 = 190, 540

    def X(v):
        return x0 + v / 100 * (x1 - x0)

    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{e(_dumb_alt(items, pair, labels))}">']
    out.append('<g class="grid">' + "".join(f'<line x1="{X(t):.1f}" y1="{top}" x2="{X(t):.1f}" y2="{H - 34}"/>'
                                         for t in (0, 25, 50, 75, 100)) + '</g>')
    for i, it in enumerate(items):
        cy = top + i * row_h + 18
        real = it.get("verdict") in ("real", "probable")
        lab = _clip(labels.get(it["column"], it["label"]), 30)
        out.append(f'<text class="{"t-strong" if real else "t-muted"}" style="font-size:12px" x="0" y="{cy + 4:.1f}">{e(lab)}</text>')
        xa, xb = X(it["a"]), X(it["b"])
        if real:
            out.append(f'<line class="lk-clay" x1="{xa:.1f}" y1="{cy:.1f}" x2="{xb:.1f}" y2="{cy:.1f}"/>')
            out.append(f'<circle class="d-clay" cx="{xa:.1f}" cy="{cy:.1f}" r="7.5"/><circle class="d-slate" cx="{xb:.1f}" cy="{cy:.1f}" r="7.5"/>')
        else:
            out.append(f'<line class="lk-grey" x1="{xa:.1f}" y1="{cy:.1f}" x2="{xb:.1f}" y2="{cy:.1f}"/>')
            out.append(f'<circle class="d-hollow" cx="{xa:.1f}" cy="{cy:.1f}" r="6"/><circle class="d-hollow" cx="{xb:.1f}" cy="{cy:.1f}" r="6"/>')
        left, right = (xa, xb) if xa <= xb else (xb, xa)
        la, lb = (f"{it['a']:.0f}%", f"{it['b']:.0f}%") if xa <= xb else (f"{it['b']:.0f}%", f"{it['a']:.0f}%")
        ca, cb = ("c-clay", "c-slate") if xa <= xb else ("c-slate", "c-clay")
        if not real:
            ca = cb = "t-muted"
        out.append(f'<text class="{ca} num" x="{left - 12:.1f}" y="{cy + 4:.1f}" text-anchor="end">{la}</text>')
        out.append(f'<text class="{cb} num" x="{right + 12:.1f}" y="{cy + 4:.1f}">{lb}</text>')
        if real:
            out.append(f'<rect class="pill-clay" x="{W - 62}" y="{cy - 10:.1f}" width="50" height="20" rx="10"/>')
            out.append(f'<text class="c-clay num" x="{W - 37}" y="{cy + 4:.1f}" text-anchor="middle">{fmt_signed(it["gap"])}</text>')
        else:
            out.append(f'<text class="t-muted" x="{W - 37}" y="{cy + 4:.1f}" text-anchor="middle">chance</text>')
    out.append('<g class="num">' + "".join(f'<text class="t-muted" x="{X(t):.1f}" y="{H - 12}" text-anchor="middle">{t}%</text>'
                                        for t in (0, 25, 50, 75, 100)) + '</g></svg>')
    out.append(f'<div class="legend"><span><i style="background:var(--clay)"></i>{e(pair["a"])}</span>'
               f'<span><i style="background:var(--slate)"></i>{e(pair["b"])}</span>'
               '<span><i class="hollow"></i>Gap could be chance</span></div>')
    return "".join(out)


def _dumb_alt(items, pair, labels) -> str:
    return "; ".join(f"{labels.get(i['column'], i['label'])}: {pair['a']} {i['a']:.0f} percent, {pair['b']} {i['b']:.0f} percent"
                     + ("" if i.get("verdict") == "real" else ", could be chance") for i in items)


# ── Diverging rating bars (HTML) ─────────────────────────────────────────────

def diverging(rows: list[dict], highlight: list[str] | None = None) -> str:
    """rows: {column, label, summary(rating_summary), small_base}."""
    highlight = highlight or []
    rows = [r for r in rows if r["summary"].get("n")]
    if not rows:
        return ""
    rows = sorted(rows, key=lambda r: -r["summary"]["top_box"])
    neg_max = max(r["summary"]["bottom_box"] for r in rows)
    pos_max = max(r["summary"]["top_box"] for r in rows)
    neg_max = max(10, math.ceil(neg_max / 5) * 5)
    pos_max = max(10, math.ceil(pos_max / 5) * 5)
    total = neg_max + pos_max
    mid = neg_max / total * 100
    out = ['<div class="likert num">']
    for r in rows:
        s = r["summary"]
        dist = {d["code"]: d["pct"] for d in s["distribution"]}
        b = s["bottom_codes"]
        t = s["top_codes"]
        strong_neg = dist.get(b[0], 0)
        weak_neg = sum(dist.get(c, 0) for c in b[1:])
        strong_pos = dist.get(t[-1], 0)
        weak_pos = sum(dist.get(c, 0) for c in t[:-1])
        cls = "lk-row" + (" hl" if r["column"] in highlight else "") + (" small" if r.get("small_base") else "")
        out.append(
            f'<div class="{cls}"><span class="lab">{e(_clip(r["label"], 48))}</span>'
            f'<div class="lk-track" role="img" aria-label="{e(r["label"])}: {s["top_box"]:.0f} percent agree, {s["bottom_box"]:.0f} percent disagree">'
            f'<div class="lk-neg" style="left:0;right:{100 - mid:.2f}%"><span class="s-d" style="width:{weak_neg / neg_max * 100:.2f}%"></span>'
            f'<span class="s-sd" style="width:{strong_neg / neg_max * 100:.2f}%"></span></div>'
            f'<div class="lk-pos" style="left:{mid:.2f}%;right:0"><span class="s-a" style="width:{weak_pos / pos_max * 100:.2f}%"></span>'
            f'<span class="s-sa" style="width:{strong_pos / pos_max * 100:.2f}%"></span></div>'
            f'<span class="mid" style="left:{mid:.2f}%"></span></div>'
            f'<span class="t2b">{s["top_box"]:.0f}%</span></div>')
    out.append('</div><div class="legend"><span><i style="background:var(--clay)"></i>Most negative</span>'
               '<span><i style="background:var(--clay-mid)"></i>Negative</span><span><i style="background:var(--teal-mid)"></i>Positive</span>'
               '<span><i style="background:var(--teal)"></i>Most positive</span><span>Neutral answers are not drawn</span></div>')
    return "".join(out)


# ── Horizontal bars ──────────────────────────────────────────────────────────

def hbars(options: list[dict], color: str = "") -> str:
    if not options:
        return ""
    top = max(o["pct"] for o in options) or 1
    out = ['<div class="hbars num">']
    for o in options:
        out.append(f'<div class="hbar"><span class="lab">{e(_clip(o["label"], 60))}</span>'
                   f'<div class="track"><span class="{color}" style="width:{o["pct"] / top * 100:.1f}%"></span></div>'
                   f'<span class="pct">{o["pct"]:.0f}%</span></div>')
    out.append('</div>')
    return "".join(out)


def histogram(summary: dict) -> str:
    bins = summary.get("histogram") or []
    if not bins:
        return ""
    W, H, x0, x1, y0, y1 = 640, 200, 40, 630, 10, 170
    mx = max(b["count"] for b in bins) or 1
    bw = (x1 - x0) / len(bins)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Distribution from {summary["min"]} to {summary["max"]}, median {summary["median"]}">']
    for i, b in enumerate(bins):
        h = b["count"] / mx * (y1 - y0)
        out.append(f'<rect class="d-teal" x="{x0 + i * bw + 1:.1f}" y="{y1 - h:.1f}" width="{bw - 2:.1f}" height="{h:.1f}" rx="2"/>')
    out.append(f'<line class="axis" x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}"/>')
    out.append(f'<text class="t-muted num" x="{x0}" y="{H - 8}">{bins[0]["from"]:g}</text>')
    out.append(f'<text class="t-muted num" x="{x1}" y="{H - 8}" text-anchor="end">{bins[-1]["to"]:g}</text>')
    out.append('</svg>')
    return "".join(out)


# ── Themes ───────────────────────────────────────────────────────────────────

def themes(block: dict, max_themes: int = 8) -> str:
    ts = block["themes"][:max_themes]
    if not ts:
        return ""
    out = ['<div class="themes num">']
    scale = max(t["pct"] for t in ts) or 1
    for i, t in enumerate(ts):
        width = t["pct"] / scale * 100
        neg = width * t["negative_pct"] / 100
        mix = width * t["mixed_pct"] / 100
        pos = width * t["positive_pct"] / 100
        name = f"<b>{e(t['name'])}</b>" if i == 0 else e(t["name"])
        out.append(f'<div class="theme"><span>{name}</span><div class="bar" role="img" aria-label="{e(t["name"])}: '
                   f'{t["pct"]:.0f} percent of comments, {t["negative_pct"]:.0f} percent negative">'
                   f'<span class="neg" style="width:{neg:.1f}%"></span><span class="mix" style="width:{mix:.1f}%"></span>'
                   f'<span class="pos" style="width:{pos:.1f}%"></span></div><span class="pct">{t["pct"]:.0f}%</span></div>')
    out.append('</div><div class="legend"><span><i style="background:var(--clay)"></i>Negative</span>'
               '<span><i style="background:var(--neutral)"></i>Mixed</span><span><i style="background:var(--teal)"></i>Positive</span>'
               '<span>Bar length is the share of comments</span></div>')
    return "".join(out)


# ── Trend ────────────────────────────────────────────────────────────────────

def trend(tr: dict, is_nps: bool) -> str:
    pts = [p for p in tr["points"] if p.get("value") is not None]
    if len(pts) < 2:
        return ""
    W, H, x0, x1, y0, y1 = 640, 240, 50, 610, 20, 200
    vals = [v for p in pts for v in (p.get("ci") or [p["value"]] * 2)]
    lo, hi = min(vals) - 5, max(vals) + 5
    lo, hi = (max(-100, math.floor(lo / 10) * 10), min(100, math.ceil(hi / 10) * 10)) if is_nps else \
             (max(0, math.floor(lo / 10) * 10), min(100, math.ceil(hi / 10) * 10))

    def X(i):
        return x0 + i / (len(pts) - 1) * (x1 - x0)

    def Y(v):
        return y1 - (v - lo) / (hi - lo) * (y1 - y0)

    band_top = " ".join(f"{X(i):.1f},{Y(p['ci'][1]):.1f}" for i, p in enumerate(pts) if p.get("ci"))
    band_bot = " ".join(f"{X(i):.1f},{Y(p['ci'][0]):.1f}" for i, p in reversed(list(enumerate(pts))) if p.get("ci"))
    alt = "; ".join(f"{p['wave']}: {p['value']}" for p in pts)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{e(alt)}">']
    for t in _nice_ticks(lo, hi, 4):
        out.append(f'<line class="grid" x1="{x0}" y1="{Y(t):.1f}" x2="{x1}" y2="{Y(t):.1f}"/>'
                   f'<text class="t-muted num" x="{x0 - 8}" y="{Y(t) + 4:.1f}" text-anchor="end">{fmt_signed(t) if is_nps else f"{t:g}%"}</text>')
    if band_top:
        out.append(f'<polygon class="band-teal" points="{band_top} {band_bot}"/>')
    out.append('<polyline class="line-teal" points="' + " ".join(f"{X(i):.1f},{Y(p['value']):.1f}" for i, p in enumerate(pts)) + '"/>')
    for i, p in enumerate(pts):
        last = i == len(pts) - 1
        out.append(f'<circle class="{"d-clay" if last and tr.get("last_change", 0) < 0 and tr.get("verdict") == "real" else "d-teal"}" cx="{X(i):.1f}" cy="{Y(p["value"]):.1f}" r="{7 if last else 5}"/>')
        out.append(f'<text class="t-strong num" x="{X(i):.1f}" y="{Y(p["value"]) - 12:.1f}" text-anchor="middle">{fmt_signed(p["value"]) if is_nps else fmt_pct(p["value"])}</text>')
        out.append(f'<text class="t-muted" x="{X(i):.1f}" y="{H - 14}" text-anchor="middle">{e(_clip(p["wave"], 16))}</text>')
    out.append('</svg>')
    return "".join(out)
