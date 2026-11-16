"""Assemble the HTML report from results.json (numbers) and narrative.json (words).

Claude writes the narrative: titles, the answer, chapter text, persona names,
actions and next questions. Every number shown comes from results.json, so the
words can never drift from the data. See skills/_shared/narrative.md.
"""

from __future__ import annotations

import os
import re
from datetime import date
from html import escape

from . import charts as ch

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
TONES = {"problem", "strength", "watch", "neutral"}
PRIORITY = {"now": "Act now", "next": "Plan next", "protect": "Protect"}



def e(x) -> str:
    return escape("" if x is None else str(x), quote=True)


def rich(text) -> str:
    """Escape, then [[problem]] -> clay emphasis and {{good}} -> brand emphasis."""
    s = e(text)
    s = re.sub(r"\[\[(.+?)\]\]", r'<em class="hl-problem">\1</em>', s)
    s = re.sub(r"\{\{(.+?)\}\}", r'<em class="hl-good">\1</em>', s)
    return s


def plain(text) -> str:
    return re.sub(r"\[\[|\]\]|\{\{|\}\}", "", str(text or ""))


def _read(name: str) -> str:
    with open(os.path.join(ASSETS, name), encoding="utf-8") as fh:
        return fh.read()


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:30] or "chapter"


class Ctx:
    def __init__(self, results: dict, narrative: dict, brand: dict):
        self.r = results
        self.n = narrative
        self.brand = brand
        self.warnings: list[str] = []
        self.mode = results["meta"]["mode"]
        self.kpi = results.get("kpi") or None
        self.labels: dict[str, str] = {}
        for q in results["questions"]:
            self.labels[q["id"]] = q.get("short") or q["label"]
        for d in (results.get("drivers") or {}).get("drivers", []) or []:
            self.labels.setdefault(d["column"], d["label"])
        self.labels.update(narrative.get("labels") or {})
        self.qby = {q["id"]: q for q in results["questions"]}
        self.comp = {c["dimension"]: c for c in results.get("comparisons", [])}
        self.text = {o["column"]: o for o in results.get("open_text", [])}

    def warn(self, msg):
        self.warnings.append(msg)

    def kpi_fmt(self, v):
        if v is None:
            return "–"
        return ch.fmt_signed(v) if self.kpi and self.kpi.get("kind") == "nps" else ch.fmt_pct(v)


# ── header pieces ────────────────────────────────────────────────────────────

def default_stats(c: Ctx) -> list[dict]:
    r, k = c.r, c.kpi
    out = []
    if k and k.get("n"):
        name = "Net Promoter Score" if k["kind"] == "nps" else ch._clip(c.labels.get(k["column"], k["short"]), 28)
        out.append({"label": name, "value": c.kpi_fmt(k["value"]),
                    "note": f"likely {c.kpi_fmt(k['ci'][0])} to {c.kpi_fmt(k['ci'][1])}", "tone": "lead"})
    t = r.get("trend")
    if t and t.get("points") and len(t["points"]) >= 2:
        prev = t["points"][-2]
        out.append({"label": f"Since {prev['wave']}", "value": ch.fmt_signed(t["last_change"]),
                    "note": f"from {c.kpi_fmt(prev['value'])}",
                    "tone": "alert" if t["last_change"] < 0 and t["verdict"] in ("real", "probable") else "plain"})
    out.append({"label": "Responses", "value": f"{r['meta']['n_analysed']:,}",
                "note": f"of {r['meta']['n_rows']:,} in the file", "tone": "plain"})
    h = r["health"]
    out.append({"label": "Finished", "value": f"{h['completion_pct']:.0f}%",
                "note": f"{h['completed']:,} of {h['started']:,}", "tone": "plain"})
    return out[:4]


def stats_html(stats: list[dict], cls: str = "stats") -> str:
    if not stats:
        return ""
    cells = []
    for s in stats[:4]:
        tone = s.get("tone", "plain")
        tone_cls = {"lead": " lead", "alert": " alert", "good": " good"}.get(tone, "")
        cells.append(f'<div class="stat{tone_cls}"><span class="k">{e(s.get("label"))}</span>'
                     f'<span class="v">{e(s.get("value"))}</span><span class="d">{e(s.get("note", ""))}</span></div>')
    return f'<div class="{cls} num" aria-label="Key figures">{"".join(cells)}</div>'


def brand_html(c: Ctx, small: bool = False) -> str:
    b = c.brand
    if b["mode"] == "none":
        return ""
    mark = '<span class="mark" role="img" aria-label="logo"></span>' if b.get("logo") else ""
    tag = f'<small>{e(b.get("tagline"))}</small>' if b.get("tagline") and not small else ""
    return f'<div class="brand">{mark}<span class="name">{e(b["name"])}{tag}</span></div>'


def pdf_menu(c: Ctx) -> str:
    custom = c.brand["mode"] == "custom"
    branded_name = c.brand["name"] if custom else "Insight Badger"
    return f'''<div class="pdf">
<button class="pdf-btn" type="button" aria-haspopup="menu" aria-expanded="false">
<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2v8m0 0L4.8 6.8M8 10l3.2-3.2M3 12.5h10" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
<span>Download <span class="lbl-long">PDF</span></span>
<svg class="chev" viewBox="0 0 12 12" aria-hidden="true"><path d="M3 4.5 6 7.5l3-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>
</button>
<div class="pdf-menu" role="menu" hidden>
<div class="mh">Download as PDF</div>
<button class="pdf-opt" type="button" role="menuitem" data-brand="branded"><span class="thumb"><span class="lg"></span><i class="t"></i><i></i><i class="s"></i></span><span><b>{e(branded_name)} branded</b><small>Logo on the cover, name and credit in the footer</small></span></button>
<button class="pdf-opt" type="button" role="menuitem" data-brand="unbranded"><span class="thumb"><span class="lg none"></span><i class="t"></i><i></i><i class="s"></i></span><span><b>Unbranded</b><small>No logo or product name. Ready to send as your own.</small></span></button>
<div class="fine">Every tab is included, one chapter per page, with page numbers. In the print window, choose "Save as PDF".</div>
</div></div>'''


# ── figures ──────────────────────────────────────────────────────────────────

def figure(c: Ctx, f: dict) -> str:
    t = f.get("type")
    title, sub, body, src = f.get("title"), f.get("subtitle"), "", ""
    r = c.r
    if t == "nps":
        if not c.kpi or c.kpi.get("kind") != "nps":
            c.warn("Figure 'nps' needs an NPS KPI; skipped.")
            return ""
        title = title or "Who recommends us"
        body = ch.nps_bar(c.kpi["detail"])
    elif t == "drivers":
        d = r.get("drivers") or {}
        if not d.get("available"):
            c.warn(f"Figure 'drivers' skipped: {d.get('reason', 'no driver analysis')}")
            return ""
        kname = "NPS" if c.kpi and c.kpi.get("kind") == "nps" else "the KPI"
        title = title or f"What matters most for {kname}, and how well we do on it"
        sub = sub or "Importance: share of the explained difference in the KPI. Rated well: % in the top two boxes."
        body = ch.driver_matrix(d, c.labels)
        src = f'<span class="num">Base: {d["n"]:,} people</span><span class="num">These items explain {d["r2"]:.0f}% of the variation</span>' + \
              "".join(f"<span>{e(n)}</span>" for n in d.get("notes", []))
    elif t == "groups":
        comp = c.comp.get(f.get("dimension"))
        if not comp or not c.kpi:
            c.warn(f"Figure 'groups' skipped: no comparison for '{f.get('dimension')}' (run analyze with --compare).")
            return ""
        kname = "NPS" if c.kpi["kind"] == "nps" else ch._clip(c.labels.get(c.kpi["column"], c.kpi["short"]), 40)
        title = title or f"{kname} by {ch._clip(c.labels.get(comp['dimension'], comp['short']), 50).rstrip('?')}"
        sub = sub or "Dot is the score; the bar shows the likely range. The dashed line is the overall score."
        body = ch.group_dots(comp, c.kpi, f.get("highlight"))
        x = comp.get("extremes")
        if x:
            src = (f"<span>Gap between {e(x['high'])} and {e(x['low'])}: {c.kpi_fmt(x['gap']) if c.kpi['kind'] != 'nps' else ch.fmt_signed(x['gap'])}"
                   f"{'' if c.kpi['kind'] == 'nps' else ' points'}</span>{verdict_chip(x['verdict'])}"
                   "<span>Adjusted for the number of comparisons</span>")
    elif t == "pair":
        comp = c.comp.get(f.get("dimension"))
        if not comp or not comp.get("pair"):
            c.warn(f"Figure 'pair' skipped: no item comparison for '{f.get('dimension')}' (use --pair).")
            return ""
        p = comp["pair"]
        title = title or f"% rating each item well: {p['a']} compared with {p['b']}"
        sub = sub or "Sorted by the size of the gap. Hollow grey means the gap could be chance."
        body = ch.dumbbell(p, c.labels)
    elif t == "segments":
        body = personas(c)
        return body
    elif t == "themes":
        o = c.text.get(f.get("column")) or next((x for x in c.text.values() if x.get("themes")), None)
        if not o or not o.get("themes"):
            c.warn("Figure 'themes' skipped: open-text answers have not been coded (run 'ib.py themes').")
            return ""
        title = title or "What people mention, and how they feel about it"
        sub = sub or (f"{o['n_coded']:,} comments coded" + (f" (a sample of {o['n_real']:,})" if o.get("sampled") else ""))
        body = ch.themes(o)
    elif t == "quotes":
        return quotes(c, f)
    elif t == "ratings":
        cols = f.get("columns")
        if not cols and f.get("group"):
            cols = next((g["columns"] for g in r.get("groups", []) if g["id"] == f["group"]), [])
        if not cols:
            cols = [q["id"] for q in r["questions"] if q["type"] in ("likert", "csat", "ces", "rating")]
        rows = [{"column": col, "label": c.labels.get(col, col), "summary": c.qby[col]["summary"],
                 "small_base": c.qby[col].get("small_base")} for col in cols if col in c.qby and "top_box" in c.qby[col]["summary"]]
        if not rows:
            c.warn("Figure 'ratings' skipped: no rating questions found.")
            return ""
        title = title or "How people rate each part of their experience"
        sub = sub or "Sorted by % in the top two boxes."
        body = ch.diverging(rows, f.get("highlight"))
    elif t == "trend":
        tr = r.get("trend")
        if not tr:
            c.warn("Figure 'trend' skipped: run analyze with --wave.")
            return ""
        title = title or "Score by wave"
        sub = sub or "The shaded band shows the likely range."
        body = ch.trend(tr, bool(c.kpi and c.kpi.get("kind") == "nps"))
        if tr.get("verdict"):
            src = f"<span>Latest change: {ch.fmt_signed(tr['last_change'])}</span>{verdict_chip(tr['verdict'])}"
    elif t == "question":
        q = c.qby.get(f.get("column"))
        if not q:
            c.warn(f"Figure 'question' skipped: unknown column '{f.get('column')}'.")
            return ""
        return question_card(c, q)
    elif t == "text":
        return f'<p class="lede">{rich(f.get("text"))}</p>'
    else:
        c.warn(f"Unknown figure type '{t}'.")
        return ""
    head = (f'<div class="ftitle">{e(title)}</div>' if title else "") + (f'<div class="fsub">{e(sub)}</div>' if sub else "")
    src_html = f'<div class="src">{src}</div>' if src else ""
    return f'<div class="figure">{head}{body}{src_html}</div>'


def verdict_chip(v: str) -> str:
    return {"real": '<span class="conf">Real, not noise</span>',
            "probable": '<span class="conf watch">Probably real</span>',
            "chance": '<span class="conf grey">Could be chance</span>',
            "small-base": '<span class="conf watch">Small group</span>'}.get(v, "")


def personas(c: Ctx) -> str:
    s = c.r.get("segments") or {}
    if not s.get("available"):
        c.warn(f"Figure 'segments' skipped: {s.get('reason', 'no segments')}")
        return ""
    names = c.n.get("segments") or {}
    cards = []
    color_i = 0
    for seg in s["segments"]:
        meta = names.get(str(seg["id"])) or {}
        focus = bool(meta.get("flag"))
        cls = "persona focus" if focus else ("persona" if color_i == 0 else f"persona c{color_i % 4}")
        if not focus:
            color_i += 1
        name = meta.get("name") or f"Group {seg['id'] + 1}"
        dl = []
        if seg.get("kpi") is not None:
            dl.append(f"<dt>{'NPS' if c.kpi and c.kpi['kind'] == 'nps' else 'KPI'}</dt><dd><b>{c.kpi_fmt(seg['kpi'])}</b></dd>")
        hi = ", ".join(ch._clip(c.labels.get(h["column"], h["label"]), 32) for h in seg["high"][:2])
        lo = ", ".join(ch._clip(c.labels.get(h["column"], h["label"]), 32) for h in seg["low"][:2])
        if hi:
            dl.append(f"<dt>Rate highly</dt><dd>{e(hi)}</dd>")
        if lo:
            dl.append(f"<dt>Rate low</dt><dd>{e(lo)}</dd>")
        if seg.get("skews"):
            sk = seg["skews"][0]
            dl.append(f"<dt>More often</dt><dd>{e(sk['value'])} ({sk['share']:.0f}% vs {sk['overall']:.0f}%)</dd>")
        quote = meta.get("quote")
        if not quote and meta.get("quote_id"):
            col, _, rid = str(meta["quote_id"]).partition(":")
            quote = (c.text.get(col, {}).get("quotes") or {}).get(rid, {}).get("text")
        flag_html = '<span class="pflag">Needs action</span>' if focus else ""
        quote_html = f"<q>{e(quote)}</q>" if quote else ""
        desc = meta.get("description")
        desc_html = f'<p class="muted" style="font-size:13px">{rich(desc)}</p>' if desc else ""
        cards.append(
            f'<article class="{cls}">{flag_html}'
            f'<div class="top"><h3>{e(name)}</h3><span class="share num">{seg["size_pct"]:.0f}%</span></div>'
            f'<div class="sizebar"><span style="width:{seg["size_pct"]:.0f}%"></span></div>'
            f'<dl class="num">{"".join(dl)}</dl>'
            f'{quote_html}{desc_html}'
            '</article>')
    note = "" if s["strength"] != "weak" else '<p class="muted" style="font-size:13px">These groups overlap a lot; read them as tendencies.</p>'
    return f'<div class="personas">{"".join(cards)}</div>{note}'


def quotes(c: Ctx, f: dict) -> str:
    o = c.text.get(f.get("column")) or next((x for x in c.text.values() if x.get("quotes")), None)
    if not o or not o.get("quotes"):
        c.warn("Figure 'quotes' skipped: no coded open-text answers.")
        return ""
    ids = f.get("ids")
    themes = o.get("themes") or []
    if not ids:
        ids = []
        for t in themes[:4]:
            if t["example_ids"]:
                ids.append(t["example_ids"][0])
    theme_of = {}
    tone_of = {}
    for t in themes:
        for rid in t["example_ids"]:
            theme_of.setdefault(rid, t["name"])
            tone_of.setdefault(rid, "neg" if t["negative_pct"] >= 60 else "pos" if t["positive_pct"] >= 60 else "")
    cards = []
    for rid in ids:
        q = o["quotes"].get(str(rid))
        if not q:
            c.warn(f"Quote id '{rid}' not found among coded examples; skipped.")
            continue
        who = [v for k, v in q.items() if k not in ("id", "text")][:3]
        cards.append(f'<figure class="quote {tone_of.get(str(rid), "")}"><span class="th">{e(theme_of.get(str(rid), ""))}</span>'
                     f'<p>{e(q["text"])}</p><span class="who">{e(" · ".join(who))}</span></figure>')
    return f'<div class="quotes">{"".join(cards)}</div>' if cards else ""


# ── question cards ───────────────────────────────────────────────────────────

def question_card(c: Ctx, q: dict, battery: list[dict] | None = None) -> str:
    s = q["summary"]
    t = q["type"]
    meta = [f"<span class=\"num\">{s.get('n', 0):,} answered</span>"]
    if q.get("small_base"):
        meta.append('<span class="conf watch">Small group</span>')
    if battery:
        title = battery[0].get("group_label") or q["label"]
        body = ch.diverging([{"column": b["id"], "label": c.labels.get(b["id"], b.get("short") or b["label"]),
                              "summary": b["summary"], "small_base": b.get("small_base")} for b in battery])
        meta = [f"<span>{len(battery)} items on the same scale</span>"]
    elif t == "nps":
        title = q["label"]
        body = (f'<div class="bignum num">{ch.fmt_signed(s["nps"])}</div>'
                f'<div class="muted num" style="font-size:13px">likely {ch.fmt_signed(s["ci"][0])} to {ch.fmt_signed(s["ci"][1])}</div>'
                + ch.nps_bar(s))
    elif "top_box" in s:
        title = q["label"]
        body = ch.diverging([{"column": q["id"], "label": c.labels.get(q["id"], q.get("short")), "summary": s}])
        meta.append(f"<span class=\"num\">Average {s['mean']} on a {len(s['distribution'])}-point scale</span>")
    elif t == "multi-select":
        title = q["label"]
        body = ch.hbars(s.get("options", []), "slate")
        meta.append(f"<span class=\"num\">On average {s.get('mean_selected', 0)} chosen · base: {e(s.get('base_note', ''))}</span>")
    elif t == "numeric":
        title = q["label"]
        body = ch.histogram(s)
        if s.get("n"):
            meta.append(f"<span class=\"num\">Median {s['median']:g} · middle half {s['p25']:g} to {s['p75']:g}</span>")
    elif t == "open-text":
        title = q["label"]
        o = c.text.get(q["id"]) or {}
        body = ch.themes(o) if o.get("themes") else f'<p class="muted" style="margin-top:8px">{s.get("n", 0):,} comments. Themes appear here once they are coded.</p>'
    else:
        title = q["label"]
        body = ch.hbars(s.get("options", []))
    return (f'<div class="figure qcard"><div class="ftitle">{e(title)}</div>'
            f'<div class="qmeta">{"".join(meta)}</div>{body}</div>')


def questions_tab(c: Ctx) -> str:
    groups = {g["id"]: g for g in c.r.get("groups", []) if g["kind"] == "battery"}
    done = set()
    cards = []
    for q in c.r["questions"]:
        gid = q.get("group")
        if gid and gid in groups:
            if gid in done:
                continue
            done.add(gid)
            members = [dict(c.qby[col], group_label=groups[gid]["label"]) for col in groups[gid]["columns"] if col in c.qby]
            cards.append(question_card(c, q, members))
        else:
            cards.append(question_card(c, q))
    return "".join(cards)


# ── data & method ────────────────────────────────────────────────────────────

def data_tab(c: Ctx) -> str:
    r, h, m = c.r, c.r["health"], c.r["meta"]
    chips = [f"<span>{h['started']:,} started</span>",
             f'<span class="good">{h["completed"]:,} finished ({h["completion_pct"]:.0f}%)</span>']
    ex = m.get("excluded", {})
    if ex.get("speeders"):
        chips.append(f'<span class="flag">{ex["speeders"]} removed as speeders</span>')
    if ex.get("straightliners"):
        chips.append(f'<span class="flag">{ex["straightliners"]} removed for identical answers</span>')
    if h.get("routed"):
        chips.append(f"<span>{h['routed']} question{'s' if h['routed'] != 1 else ''} shown to some people only</span>")
    if h.get("red"):
        chips.append(f'<span class="flag">{h["red"]} question{"s" if h["red"] != 1 else ""} with many blanks</span>')
    rows = []
    for col in h["columns"]:
        badge = {"green": "Good", "yellow": "Check", "red": "Weak"}[col["status"]]
        rows.append(f"<tr><td>{e(ch._clip(c.labels.get(col['column'], col['label']), 70))}</td><td class=\"num\">{col['answered_pct']:.0f}%</td>"
                    f"<td><span class=\"badge {col['status']}\">{badge}</span></td><td>{e(col['note'])}</td></tr>")
    scope = []
    if m.get("filters"):
        scope.append("Filtered to: " + "; ".join(m["filters"]))
    if m.get("weights"):
        scope.append(f"Weighted by '{m['weights']}'")
    rel = [b for b in r.get("batteries", []) if b.get("alpha") is not None]
    rel_txt = "".join(
        f"<li>&lsquo;{e(ch._clip(b['label'], 70).rstrip('?:. '))}&rsquo;: {'the questions hang together well' if b['alpha'] >= 0.7 else 'the questions only partly hang together' if b['alpha'] >= 0.6 else 'the questions measure different things'} (reliability {b['alpha']:.2f}).</li>"
        for b in rel)
    return f'''
<div class="head"><span class="kicker ochre">Reference · Data &amp; method</span><h2>Data quality and how this was worked out</h2></div>
<div class="quality num">{"".join(chips)}</div>
{f'<p class="muted">{e(" · ".join(scope))}</p>' if scope else ""}
<div class="figure"><div class="ftitle">How completely each question was answered</div>
<div class="fsub">Questions skipped by survey routing, and blanks from people who left early, are not counted as problems.</div>
<div class="table-wrap"><table><thead><tr><th>Question</th><th>Answered</th><th>Status</th><th>Note</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>
<div class="figure"><div class="ftitle">Methods</div><ul class="methods" style="margin-top:10px">{"".join(f"<li>{e(x)}</li>" for x in r.get("methods", []))}{rel_txt}
<li>Speeders: {e(h.get("speeder_rule", "").lower())}.</li><li>Personal details such as email addresses are left out of this report and removed from quotes.</li></ul></div>
<details class="figure"><summary class="ftitle" style="cursor:pointer">Codebook: every column and how it was read</summary>
<div class="table-wrap" style="margin-top:10px"><table><thead><tr><th>Column</th><th>Read as</th><th>Question</th></tr></thead><tbody>
{"".join(f"<tr><td>{e(q['id'])}</td><td>{e(q['type'])}</td><td>{e(ch._clip(q['label'], 120))}</td></tr>" for q in r["questions"])}
</tbody></table></div></details>'''


def caveats_html(items: list[dict]) -> str:
    if not items:
        return ""
    lis = "".join(f'<li><span class="conf{" watch" if x.get("level") == "watch" else ""}">'
                  f'{"Watch" if x.get("level") == "watch" else "Solid"}</span><span>{rich(x.get("text"))}</span></li>'
                  for x in items)
    return f'<ul class="caveats">{lis}</ul>'


# ── page ─────────────────────────────────────────────────────────────────────

def _actions(n: dict) -> str:
    acts = n.get("actions") or []
    nq = n.get("next_questions") or []
    if not acts and not nq:
        return ""
    a = "".join(f'<div class="action {x.get("priority", "next")}"><span class="tag">{PRIORITY.get(x.get("priority", "next"), "Plan next")}</span>{rich(x.get("text"))}</div>'
                for x in acts)
    q = "".join(f'<div><span>{e(x.get("text"))}</span><code>/{e(x.get("skill", "dig-for"))}</code></div>' for x in nq)
    left = f'<div><h3>What to do about it</h3><div class="actions">{a}</div></div>' if acts else ""
    right = f'<div><h3>Keep digging</h3><div class="nextq">{q}</div></div>' if nq else ""
    return f'<div class="split">{left}{right}</div>'


def _pager(prev, nxt) -> str:
    if not prev and not nxt:
        return ""
    p = f'<a href="#{prev[0]}"><span>Previous</span><b>← {e(prev[1])}</b></a>' if prev else ""
    n_ = f'<a class="nx" href="#{nxt[0]}"><span>Next</span><b>{e(nxt[1])} →</b></a>' if nxt else ""
    return f'<div class="pager">{p}{n_}</div>'


def render_report(results: dict, narrative: dict, brand: dict) -> tuple[str, list[str]]:
    c = Ctx(results, narrative, brand)
    n = narrative
    is_for = c.mode == "for"
    chapters = n.get("chapters") or []
    if not n.get("title"):
        c.warn("Narrative has no 'title'.")
    for chp in chapters:
        if chp.get("tone", "neutral") not in TONES:
            c.warn(f"Chapter '{chp.get('title')}' has unknown tone '{chp.get('tone')}'.")

    # Tabs
    first_id = "answer" if is_for else "overview"
    tabs = [(first_id, "Answer" if is_for else "Overview", None)]
    for i, chp in enumerate(chapters, 1):
        chp["_id"] = "ch-" + _slug(chp.get("id") or chp.get("tab") or str(i))
        tabs.append((chp["_id"], chp.get("tab") or f"Chapter {i}", i))
    if is_for:
        tabs.append(("confidence", "How sure we are", "ref"))
    else:
        tabs.append(("questions", "All questions", "ref"))
    tabs.append(("data", "Data & method", "ref"))

    tab_html = []
    for tid, name, num in tabs:
        cls = "tab" + (" ref" if num == "ref" and (tid in ("questions", "confidence")) else "")
        extra = ""
        if isinstance(num, int):
            chp = chapters[num - 1]
            extra = f'<span class="no">{num}</span>'
            name_html = e(name)
            if chp.get("tone") == "problem":
                name_html += '<span class="flag" title="Contains something to fix"></span>'
            if chp.get("count") is not None:
                name_html += f'<span class="ct num">{e(chp["count"])}</span>'
            tab_html.append(f'<a class="{cls}" role="tab" href="#{tid}" data-tab="{tid}">{extra}{name_html}</a>')
        else:
            label = e(name)
            if tid == "questions":
                label += f'<span class="ct num">{len(results["questions"])}</span>'
            if tid == "confidence":
                w = sum(1 for x in (n.get("caveats") or results.get("caveats") or []) if x.get("level") == "watch")
                if w:
                    label += f'<span class="ct watch num">{w}</span>'
            tab_html.append(f'<a class="{cls}" role="tab" href="#{tid}" data-tab="{tid}">{label}</a>')
        if tid == first_id:
            tab_html.append('<span class="divider" aria-hidden="true"></span>')

    order = [(t[0], t[1] if not isinstance(t[2], int) else f"{t[2]} · {t[1]}") for t in tabs if t[2] != "ref"]

    def pager_for(tid):
        ids = [o[0] for o in order]
        if tid not in ids:
            return ""
        i = ids.index(tid)
        return _pager(order[i - 1] if i > 0 else None, order[i + 1] if i + 1 < len(order) else None)

    panels = []
    # First tab
    first = [f'<p class="answer">{rich(n.get("answer", ""))}</p>'] if n.get("answer") else []
    if is_for:
        rs = n.get("reasons") or []
        if rs:
            first.append('<div class="reasons">' + "".join(
                f'<div class="reason"><span class="k">{e(x.get("label"))}</span><span class="v num">{e(x.get("value"))}</span>'
                f'<p>{rich(x.get("text"))}</p></div>' for x in rs) + '</div>')
        if n.get("not_cause"):
            first.append(f'<div class="same"><b>Not the cause:</b> {rich(n["not_cause"])}</div>')
    else:
        if c.kpi and c.kpi.get("kind") == "nps" and c.kpi.get("detail"):
            first.append(f'<div class="figure"><div class="ftitle">Who recommends us</div>{ch.nps_bar(c.kpi["detail"])}</div>')
        if chapters:
            cards = []
            for i, chp in enumerate(chapters, 1):
                tone = chp.get("tone", "neutral")
                tag_html = f'<span class="tag">{e(chp.get("tag"))}</span>' if chp.get("tag") else "<span></span>"
                cid = chp["_id"]
                cards.append(f'<a class="story tone-{tone}" href="#{cid}"><div class="top">'
                             f'{tag_html}'
                             f'<span class="ch">Chapter {i}</span></div><h3>{e(plain(chp.get("title")))}</h3>'
                             f'<p>{rich(chp.get("summary", ""))}</p><span class="go">Open {e(chp.get("tab") or "chapter")} →</span></a>')
            first.append(f'<div class="head"><span class="kicker">The story in {len(chapters)} chapter{"s" if len(chapters) != 1 else ""}</span></div>'
                         f'<div class="storymap">{"".join(cards)}</div>')
    first.append(_actions(n))
    first.append(pager_for(first_id))
    panels.append((first_id, "".join(first)))

    for i, chp in enumerate(chapters, 1):
        kick = "kicker slate" if is_for else "kicker"
        body = [f'<div class="head"><span class="{kick}">{"" if is_for else "Chapter "}{i} · {e(chp.get("tab") or "")}</span>'
                f'<h2>{rich(chp.get("title"))}</h2></div>']
        if chp.get("lede"):
            body.append(f'<p class="lede">{rich(chp["lede"])}</p>')
        for f in chp.get("figures") or []:
            body.append(figure(c, f))
        if chp.get("so_what"):
            body.append(f'<div class="sowhat"><b>So what</b>{rich(chp["so_what"])}</div>')
        body.append(pager_for(chp["_id"]))
        panels.append((chp["_id"], "".join(body)))

    cav = n.get("caveats") or results.get("caveats") or []
    if is_for:
        panels.append(("confidence", f'<div class="head"><span class="kicker ochre">How sure we are</span>'
                                     f'<h2>{rich(n.get("confidence_title") or "What this rests on")}</h2></div>'
                                     + (caveats_html(cav) or '<p class="muted">No specific concerns.</p>')))
    else:
        qtab = ('<div class="head"><span class="kicker slate">Reference · All questions</span>'
                '<h2>Every question, one card each</h2></div>' + questions_tab(c))
        panels.append(("questions", qtab))
    panels.append(("data", (caveats_html(cav) if (cav and not is_for) else "") + data_tab(c)))

    # Header
    stats = n.get("stats") or default_stats(c)
    meta = results["meta"]
    survey = n.get("survey_name") or os.path.splitext(os.path.basename(meta["file"]))[0]
    crumbs = [survey] + ([n["wave"]] if n.get("wave") else []) + ["Focused question" if is_for else "Full exploration"]
    gd = date.fromisoformat(meta["generated"]) if meta.get("generated") else None
    generated = f"{gd.day} {gd.strftime('%b %Y')}" if gd else ""
    question = n.get("question") or meta.get("question")
    asked = ""
    if is_for and question:
        asked = (f'<div class="asked"><span class="k">You asked</span>'
                 f'<span class="q">&ldquo;{e(question)}&rdquo;</span></div>')
    scope = ""
    if n.get("scope"):
        scope = '<div class="scope">' + "".join(f"<span>{e(x)}</span>" for x in n["scope"]) + "</div>"
    sub_html = f'<p class="sub">{rich(n.get("subtitle"))}</p>' if n.get("subtitle") else ""
    hero_cls = "hero" + (" for" if is_for else "") + ("" if stats else " nostats")
    mode_label = "Focused question · /dig-for" if is_for else "Full exploration · /dig-deep"
    title_html = rich(n.get("title", "Survey findings"))
    hero = (f'<header class="{hero_cls} wrap"><div class="inner"><div class="hero-text">'
            f'<span class="mode">{mode_label}</span>{asked}<h1>{title_html}</h1>{sub_html}{scope}</div>'
            f'{stats_html(stats)}</div></header>')
    brand_block = brand_html(c) or f'<div class="brand">{e(survey)}</div>'
    crumb_parts = []
    for j, x in enumerate(crumbs):
        crumb_parts.append(f"<b>{e(x)}</b>" if j == len(crumbs) - 1 else f"<span>{e(x)}</span>")
    crumbs_html = '<span class="sep">/</span>'.join(crumb_parts)
    appbar = (f'<div class="appbar wrap screen-only"><div class="inner">{brand_block}'
              f'<div class="crumbs">{crumbs_html}</div>'
              f'<div class="bar-right"><span class="stamp num">Generated {e(generated)}</span>{pdf_menu(c)}</div>'
              '</div></div>')
    conf_html = '<span class="conf-label">Confidential</span>' if brand.get("confidential") else ""
    q_html = f'<p class="meta">You asked: &ldquo;{e(question)}&rdquo;</p>' if is_for and question else ""
    n_resp = f"{meta['n_analysed']:,} responses"
    cover_meta = " · ".join(x for x in [survey, n.get("wave"), n.get("fieldwork"), n_resp, generated] if x)
    bigmark = '<div class="bigmark"></div>' if brand["mode"] != "none" and brand.get("logo") else ""
    kind = "Focused question" if is_for else "Full exploration"
    cover_cls = "cover for" if is_for else "cover"
    cover = (f'<section class="{cover_cls}">{brand_html(c, small=True)}{conf_html}'
             f'<div class="band"><span class="kind">{kind}</span>{q_html}<h1>{title_html}</h1>'
             f'<p class="meta num">{e(cover_meta)}</p></div>{bigmark}</section>'
             f'<div class="print-only">{stats_html(stats, "stats print-stats")}</div>')
    if brand["mode"] == "insight-badger":
        credit = "Generated with Insight Badger"
    elif brand["mode"] == "custom":
        credit = f"Prepared by {brand['name']}"
    else:
        credit = ""
    credit_html = f'<span class="credit">{e(credit)} · </span>' if credit else ""
    filt = (" · " + e("; ".join(meta["filters"]))) if meta.get("filters") else ""
    foot = (f'<footer class="foot wrap"><div class="inner">{brand_html(c, small=True)}'
            f'<span>{credit_html}{e(generated)} · {e(os.path.basename(meta["file"]))}{filt}</span></div></footer>')

    panel_html = "".join(
        f'<section class="panel wrap" id="p-{tid}" role="tabpanel"{"" if j == 0 else " hidden"}><div class="inner">{body}</div></section>'
        for j, (tid, body) in enumerate(panels))
    css = _read("report.css").replace("__PAPER__", "letter" if brand.get("paper", "A4").lower() == "letter" else "A4")
    color_vars = "".join(f"{k}:{v};" for k, v in (brand.get("colors") or {}).items())
    logo_var = f"--logo:url('{brand['logo']}');" if brand.get("logo") else ""
    root = f":root{{{logo_var}{color_vars}}}"
    title_txt = plain(n.get("title") or "Survey findings")
    file_title = f"{survey} - {'focused question' if is_for else 'full exploration'} - {generated}"
    body_cls = ("for-report" if is_for else "deep-report") + (" unbranded" if brand["mode"] == "none" else "") + \
               ("" if brand.get("logo") else " nologo")
    html = (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f'<title>{e(title_txt)}</title><meta name="generator" content="Insight Badger">'
            f'<style>{css}\n{root}</style></head>'
            f'<body class="{body_cls}" data-default-brand="{e(brand["mode"])}" data-file-title="{e(file_title)}">'
            f'{appbar}{cover}{hero}'
            f'<nav class="tabbar wrap" aria-label="Report sections"><div class="inner tabs" role="tablist">{"".join(tab_html)}</div></nav>'
            f'<main>{panel_html}</main>{foot}<script>{_read("report.js")}</script></body></html>')
    return html, c.warnings
