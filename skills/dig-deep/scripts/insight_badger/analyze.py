"""Run the analysis described by a profile and options; produce results.json."""

from __future__ import annotations

import datetime as _dt
import math
import re

import numpy as np
import pandas as pd

from . import drivers as drv
from . import metrics as m
from . import quality as q
from . import scales
from . import segments as seg
from . import stats as st
from .detect import ORDINAL_TYPES, column_map
from .text import export_texts


# ── helpers ──────────────────────────────────────────────────────────────────

def _short(label: str, n: int = 70) -> str:
    label = re.sub(r"\s+", " ", str(label)).strip()
    return label if len(label) <= n else label[: n - 1].rstrip() + "…"


def apply_filters(df: pd.DataFrame, filters: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Filters like 'Q7=1-10|11-50', 'Region!=EMEA', 'Tenure>=2'."""
    applied = []
    for f in filters or []:
        mt = re.match(r"^\s*(.+?)\s*(!=|>=|<=|=|>|<)\s*(.*)$", f)
        if not mt:
            raise ValueError(f"Cannot read filter '{f}'. Use COLUMN=value, COLUMN!=value or COLUMN>=number.")
        col, op, val = mt.groups()
        if col not in df.columns:
            raise ValueError(f"Filter column '{col}' is not in the file.")
        s = df[col]
        if op in ("=", "!="):
            vals = [v.strip() for v in val.split("|")]
            hit = s.astype(str).str.strip().isin(vals)
            if pd.api.types.is_numeric_dtype(s):
                hit |= s.isin(pd.to_numeric(pd.Series(vals), errors="coerce").dropna())
            mask = hit if op == "=" else ~hit
        else:
            num = pd.to_numeric(s, errors="coerce")
            v = float(val)
            mask = {">=": num >= v, "<=": num <= v, ">": num > v, "<": num < v}[op]
        df = df[mask.fillna(False)]
        applied.append(f"{col} {op} {val}")
    return df, applied


_UNITS = {"day": 1 / 365, "week": 1 / 52, "month": 1 / 12, "year": 1.0}


def _lead(v):
    """Sort key for bands: '1-10', '1,000+', 'Less than 6 months', 'More than 2 years'."""
    text = str(v).strip().lower()
    mt = re.match(r"^(under|less than|fewer than|up to|<|>|over|more than|at least)?\s*\$?(\d[\d,]*(?:\.\d+)?)",
                  text)
    if not mt:
        return None
    value = float(mt.group(2).replace(",", ""))
    unit = re.search(r"(day|week|month|year)", text)
    if unit:
        value *= _UNITS[unit.group(1)]
    prefix = mt.group(1) or ""
    if prefix in ("under", "less than", "fewer than", "up to", "<"):
        value -= 1e-6
    elif prefix in ("over", "more than", "at least", ">") or text.split()[0].endswith("+"):
        value += 1e-6
    return value


def _group_order(values: list) -> list:
    """Natural order for bands like '1-10', '11-50', '250+'; otherwise keep size order."""
    nums = [_lead(v) for v in values]
    if all(n is not None for n in nums) and len(set(nums)) == len(nums):
        return [v for _, v in sorted(zip(nums, values))]
    return values


def kpi_metric(codes: pd.Series, info: dict, weights) -> dict:
    if info["type"] == "nps":
        s = m.nps_summary(codes, weights)
        if s.get("n", 0) == 0:
            return {"n": 0}
        return {"kind": "nps", "value": s["nps"], "ci": s["ci"], "n": s["n"], "n_eff": s["n_eff"], "detail": s}
    s = m.rating_summary(codes, info, weights)
    if s.get("n", 0) == 0:
        return {"n": 0}
    return {"kind": "top_box", "value": s["top_box"], "ci": s["top_box_ci"], "n": s["n"], "n_eff": s["n_eff"], "detail": s}


def kpi_test(a: dict, b: dict) -> float:
    if a.get("kind") == "nps":
        return st.nps_diff_test(a["detail"], b["detail"])
    return st.two_prop_test(a["value"] / 100, a["n_eff"], b["value"] / 100, b["n_eff"])


# ── main ─────────────────────────────────────────────────────────────────────

def run(survey, profile: dict, kpi: str | None = None, driver_cols: list[str] | None = None,
        compare: list[str] | None = None, pair: list[str] | None = None, filters: list[str] | None = None,
        weights_col: str | None = None, wave: str | None = None, do_segments: bool = True,
        keep_flagged: bool = False, mode: str = "deep", max_texts: int = 400) -> tuple[dict, dict]:
    cols = column_map(profile)
    df_all = survey.df
    health = q.health(df_all, profile, cols)

    df, applied = apply_filters(df_all, filters or [])
    flagged = (health["_speeders"] | health["_straightliners"]).reindex(df.index).fillna(False)
    excluded = {"speeders": int(health["_speeders"].reindex(df.index).fillna(False).sum()),
                "straightliners": int(health["_straightliners"].reindex(df.index).fillna(False).sum())}
    if not keep_flagged:
        df = df[~flagged]
    weights = None
    if weights_col:
        if weights_col not in df.columns:
            raise ValueError(f"Weight column '{weights_col}' is not in the file.")
        weights = pd.to_numeric(df[weights_col], errors="coerce").fillna(0)

    methods: list[str] = []
    caveats: list[dict] = []
    labels = {c: i["label"] for c, i in cols.items()}
    item_labels = {c: _short(i.get("item") or i["label"]) for c, i in cols.items()}

    # Encode every rating column once
    codes = {c: m.encode_column(df[c], i) for c, i in cols.items() if i["type"] in ORDINAL_TYPES + ("nps",)}

    # ── per-question summaries ──
    questions = []
    seen_groups = set()
    group_by_id = {g["id"]: g for g in profile["groups"]}
    for c, i in cols.items():
        t = i["type"]
        if t in ("metadata", "empty", "datetime", "unknown") or i.get("pii"):
            continue
        if i.get("group") and group_by_id.get(i["group"], {}).get("kind") == "multi-select":
            gid = i["group"]
            if gid in seen_groups:
                continue
            seen_groups.add(gid)
            g = group_by_id[gid]
            mat = m.multiselect_matrix(df, g)
            questions.append({"id": gid, "label": g["label"], "type": "multi-select",
                              "summary": m.multiselect_summary(mat, None, weights)})
            continue
        entry = {"id": c, "label": i["label"], "short": item_labels[c], "type": t, "group": i.get("group")}
        if t == "nps":
            entry["summary"] = m.nps_summary(codes[c], weights)
        elif t in ORDINAL_TYPES:
            entry["summary"] = m.rating_summary(codes[c], i, weights)
        elif t in ("single-choice", "binary", "demographic") and not i.get("numeric"):
            entry["summary"] = m.categorical_summary(df[c], weights)
        elif t == "multi-select-string":
            mat = m.explode_multiselect_string(df[c], i.get("delimiter", ";"))
            entry["summary"] = m.multiselect_summary(mat, df[c].notna(), weights)
            entry["type"] = "multi-select"
        elif t in ("numeric", "demographic"):
            entry["summary"] = m.numeric_summary(df[c], weights)
            entry["type"] = "numeric"
        elif t == "open-text":
            s = df[c].dropna().astype(str).str.strip()
            entry["summary"] = {"n": int((s != "").sum())}
        else:
            continue
        if entry["summary"].get("n", 0) and entry["summary"]["n"] < st.MIN_BASE:
            entry["small_base"] = True
        questions.append(entry)
    methods.append("Rating questions: share answering in the top two boxes (for example agree + strongly agree), "
                   "with 'don't know' answers left out of the base.")

    # ── KPI ──
    kpi = kpi or (profile["kpi_candidates"][0] if profile["kpi_candidates"] else None)
    kpi_block = None
    if kpi:
        if kpi not in cols:
            raise ValueError(f"KPI column '{kpi}' is not in the file.")
        ki = cols[kpi]
        if kpi not in codes:
            codes[kpi] = m.encode_column(df[kpi], ki)
        km = kpi_metric(codes[kpi], ki, weights)
        kpi_block = {"column": kpi, "label": ki["label"], "short": item_labels[kpi], "type": ki["type"], **km}
        if ki["type"] == "nps":
            methods.append("Net Promoter Score: % scoring 9–10 minus % scoring 0–6. The likely range accounts for "
                           "promoters and detractors coming from the same people.")
        if km.get("n", 0) < 100:
            caveats.append({"level": "watch", "text": f"The headline score rests on {km.get('n', 0)} answers, "
                                                     "so it could move by several points in a repeat survey."})

    # ── drivers ──
    driver_block = {"available": False, "reason": "No KPI selected."}
    if kpi:
        if driver_cols is None:
            # Other outcome questions (overall satisfaction, likelihood to renew) are
            # results, not drivers: using them would explain the KPI with itself.
            outcomes = set(profile["kpi_candidates"])
            driver_cols = [c for c, i in cols.items() if i["type"] in ORDINAL_TYPES and c != kpi
                           and c not in outcomes and not i.get("pii")]
            skipped = [c for c in outcomes if c != kpi and c in cols and cols[c]["type"] in ORDINAL_TYPES]
            if skipped:
                methods.append("Other overall questions (" + ", ".join(skipped) + ") were not used as drivers, "
                               "because they measure the outcome rather than explain it.")
        driver_cols = [c for c in driver_cols if c in codes and c != kpi]
        if driver_cols:
            top_codes = {c: m.top_box_levels(cols[c])[0] for c in driver_cols}
            driver_block = drv.driver_analysis(pd.DataFrame({c: codes[c] for c in driver_cols}), codes[kpi],
                                               top_codes, item_labels)
            if driver_block.get("available"):
                methods.append("Drivers: relative-weights analysis splits the explained variation in the KPI across "
                               "the rating items, which stays fair when items are related to each other.")
        else:
            driver_block = {"available": False, "reason": "No rating items to use as drivers."}

    # battery reliability
    batteries = []
    for g in profile["groups"]:
        if g["kind"] == "battery":
            a = drv.cronbach_alpha(pd.DataFrame({c: codes[c] for c in g["columns"] if c in codes}))
            batteries.append({"id": g["id"], "label": g["label"], "items": len(g["columns"]),
                              "alpha": None if a is None else round(a, 2)})

    # ── comparisons ──
    if compare is None:
        compare = profile["demographics"][:5] if mode == "deep" else []
    comparisons = []
    kpi_tests = []  # (comparison index, group index, p)
    for dim in compare:
        if dim not in df.columns:
            raise ValueError(f"Comparison column '{dim}' is not in the file.")
        grp = df[dim].astype("string").str.strip()
        values = [v for v in grp.dropna().unique() if v != ""]
        values = _group_order(sorted(values, key=lambda v: -(grp == v).sum()))
        if len(values) < 2 or len(values) > 15:
            continue
        comp = {"dimension": dim, "label": labels.get(dim, dim), "short": item_labels.get(dim, dim), "groups": []}
        if kpi:
            ki = cols[kpi]
            for v in values:
                idx = grp[grp == v].index
                gm = kpi_metric(codes[kpi].loc[idx], ki, None if weights is None else weights.loc[idx])
                rest = grp[(grp != v) & grp.notna()].index
                rm = kpi_metric(codes[kpi].loc[rest], ki, None if weights is None else weights.loc[rest])
                p = kpi_test(gm, rm) if gm.get("n") and rm.get("n") else math.nan
                comp["groups"].append({"value": str(v), "n": gm.get("n", 0), "value_metric": gm.get("value"),
                                       "ci": gm.get("ci"), "gap_vs_rest": None if not gm.get("n") or not rm.get("n")
                                       else round(gm["value"] - rm["value"], 1), "p": p,
                                       "small_base": gm.get("n", 0) < st.MIN_BASE, "_metric": gm})
                kpi_tests.append((len(comparisons), len(comp["groups"]) - 1, p))
        comparisons.append(comp)

    # Holm across every KPI group test in this run
    adj = st.holm([p for _, _, p in kpi_tests])
    min_gap = st.MIN_GAP_NPS if kpi and cols[kpi]["type"] == "nps" else st.MIN_GAP_PP
    for (ci, gi, _p), pa in zip(kpi_tests, adj):
        g = comparisons[ci]["groups"][gi]
        g["p_adj"] = None if math.isnan(pa) else round(pa, 4)
        g["verdict"] = st.verdict(pa, g["gap_vs_rest"] or 0, min_gap, g["n"])
        g.pop("p", None)

    for ci_, comp in enumerate(comparisons):
        big = [g for g in comp["groups"] if not g["small_base"] and g.get("value_metric") is not None]
        if kpi and len(big) >= 2:
            hi = max(big, key=lambda g: g["value_metric"])
            lo = min(big, key=lambda g: g["value_metric"])
            p = kpi_test(hi["_metric"], lo["_metric"])
            pa = min(1.0, p * max(1, len(comparisons)))  # Bonferroni over dimensions
            comp["extremes"] = {"high": hi["value"], "low": lo["value"],
                                "gap": round(hi["value_metric"] - lo["value_metric"], 1),
                                "p_adj": round(pa, 4), "verdict": st.verdict(pa, hi["value_metric"] - lo["value_metric"],
                                                                             min_gap, min(hi["n"], lo["n"]))}
        # Item gaps between two chosen groups (dumbbell)
        a_b = None
        if pair and len(pair) == 2 and all(v in [g["value"] for g in comp["groups"]] for v in pair):
            a_b = pair
        elif comp.get("extremes"):
            a_b = [comp["extremes"]["low"], comp["extremes"]["high"]]
        if a_b:
            grp = df[comp["dimension"]].astype("string").str.strip()
            ia, ib = grp[grp == a_b[0]].index, grp[grp == a_b[1]].index
            items, ps = [], []
            item_cols = [c for c, i in cols.items() if i["type"] in ORDINAL_TYPES and c != kpi and not i.get("pii")]
            for c in item_cols:
                sa = m.rating_summary(codes[c].loc[ia], cols[c], None if weights is None else weights.loc[ia])
                sb = m.rating_summary(codes[c].loc[ib], cols[c], None if weights is None else weights.loc[ib])
                if not sa.get("n") or not sb.get("n"):
                    continue
                p = st.two_prop_test(sa["top_box"] / 100, sa["n_eff"], sb["top_box"] / 100, sb["n_eff"])
                items.append({"column": c, "label": item_labels[c], "a": sa["top_box"], "b": sb["top_box"],
                              "n_a": sa["n"], "n_b": sb["n"], "gap": round(sa["top_box"] - sb["top_box"], 1)})
                ps.append(p)
            for it, pa in zip(items, st.holm(ps)):
                it["p_adj"] = None if math.isnan(pa) else round(pa, 4)
                it["verdict"] = st.verdict(pa, it["gap"], st.MIN_GAP_PP, min(it["n_a"], it["n_b"]))
            items.sort(key=lambda it: it["gap"])
            comp["pair"] = {"a": a_b[0], "b": a_b[1], "items": items}
        for g in comp["groups"]:
            g.pop("_metric", None)
    if comparisons:
        methods.append("Group differences: each group is tested against everyone else, and p-values are adjusted "
                       "for the number of tests (Holm). Groups under 30 people are shown but never called a real "
                       "difference.")

    # ── segments ──
    seg_block = {"available": False, "reason": "Not requested."}
    if do_segments:
        rating_cols = [c for c, i in cols.items() if i["type"] in ORDINAL_TYPES and c != kpi and not i.get("pii")]
        seg_block = seg.segment(pd.DataFrame({c: codes[c] for c in rating_cols}, index=df.index), item_labels)
        if seg_block.get("available"):
            lab = seg_block.pop("_labels")
            for s in seg_block["segments"]:
                idx = lab[lab == s["id"]].index
                if kpi:
                    km = kpi_metric(codes[kpi].loc[idx], cols[kpi], None if weights is None else weights.loc[idx])
                    s["kpi"] = km.get("value")
                skews = []
                for d in profile["demographics"][:6]:
                    overall = df[d].astype("string").value_counts(normalize=True)
                    inside = df.loc[idx, d].astype("string").value_counts(normalize=True)
                    for v, share in inside.items():
                        base = overall.get(v, 0)
                        if share >= 0.25 and base and share / base >= 1.3:
                            skews.append({"dimension": item_labels.get(d, d), "value": str(v),
                                          "share": round(float(share) * 100, 1), "overall": round(float(base) * 100, 1)})
                s["skews"] = sorted(skews, key=lambda x: -(x["share"] / x["overall"]))[:3]
            methods.append("Mindsets: people were grouped by how they answered the rating questions (k-means on "
                           "standardised answers), choosing the number of groups that separates them most clearly.")
            if seg_block["strength"] == "weak":
                caveats.append({"level": "watch", "text": "The mindset groups overlap a lot; treat them as tendencies, "
                                                         "not hard categories."})

    # ── trend ──
    trend = None
    if wave and kpi:
        w = df[wave].astype("string").str.strip()
        waves = _group_order([v for v in w.dropna().unique()])
        pts = []
        for v in waves:
            idx = w[w == v].index
            km = kpi_metric(codes[kpi].loc[idx], cols[kpi], None if weights is None else weights.loc[idx])
            pts.append({"wave": str(v), "value": km.get("value"), "ci": km.get("ci"), "n": km.get("n", 0), "_m": km})
        if len(pts) >= 2 and pts[-1]["n"] and pts[-2]["n"]:
            p = kpi_test(pts[-1]["_m"], pts[-2]["_m"])
            gap = pts[-1]["value"] - pts[-2]["value"]
            trend = {"column": wave, "points": [{k: v for k, v in x.items() if k != "_m"} for x in pts],
                     "last_change": round(gap, 1), "p": round(p, 4),
                     "verdict": st.verdict(p, gap, min_gap, min(pts[-1]["n"], pts[-2]["n"]))}
            shifts = []
            for d in profile["demographics"][:5]:
                comp_tab = pd.crosstab(w, df[d].astype("string"), normalize="index") * 100
                if pts[-1]["wave"] in comp_tab.index and pts[-2]["wave"] in comp_tab.index:
                    delta = (comp_tab.loc[pts[-1]["wave"]] - comp_tab.loc[pts[-2]["wave"]]).abs().max()
                    if delta >= 5:
                        shifts.append({"dimension": item_labels.get(d, d), "max_shift_pp": round(float(delta), 1)})
            trend["mix_shifts"] = shifts
            if shifts:
                caveats.append({"level": "watch", "text": "The mix of respondents changed between waves ("
                                + ", ".join(s["dimension"] for s in shifts) + "), which can move the score on its own."})

    # ── open text ──
    text_cols = [c for c, i in cols.items() if i["type"] == "open-text" and not i.get("pii")]
    context = {}
    if kpi:
        if cols[kpi]["type"] == "nps":
            context["nps_group"] = m.nps_group(codes[kpi])
        else:
            top, bottom, _ = m.top_box_levels(cols[kpi])
            context["kpi_group"] = codes[kpi].map(lambda x: np.nan if pd.isna(x) else
                                                  ("High" if x in top else "Low" if x in bottom else "Middle"))
    for d in (compare or [])[:3]:
        context[item_labels.get(d, d)] = df[d]
    texts = export_texts(df, text_cols, labels, context, max_per_question=max_texts)

    # ── caveats from data health ──
    if health["completion_pct"] < 70:
        caveats.append({"level": "watch", "text": f"Only {health['completion_pct']}% of people who started finished."})
    for b in batteries:
        if b["alpha"] is not None and b["alpha"] < 0.6:
            caveats.append({"level": "watch", "text": f"The questions in '{_short(b['label'], 50)}' don't hang together "
                                                     "well, so they are reported one by one."})

    health_out = {k: v for k, v in health.items() if not k.startswith("_")}
    results = {
        "schema": "insight-badger/results@1",
        "meta": {
            "file": survey.path,
            "source_format": survey.source_format,
            "generated": _dt.date.today().isoformat(),
            "mode": mode,
            "n_rows": int(len(df_all)),
            "n_analysed": int(len(df)),
            "filters": applied,
            "weights": weights_col,
            "excluded": excluded if not keep_flagged else {"speeders": 0, "straightliners": 0},
            "n_questions": sum(1 for c in cols.values() if c["type"] not in ("metadata", "empty", "datetime"))
                           - sum(max(0, len(g["columns"]) - 1) for g in profile["groups"] if g["kind"] == "multi-select"),
        },
        "health": health_out,
        "kpi": kpi_block,
        "questions": questions,
        "groups": profile["groups"],
        "batteries": batteries,
        "drivers": driver_block,
        "comparisons": comparisons,
        "segments": seg_block,
        "trend": trend,
        "open_text": [{"column": c, "label": labels[c], "n_answered": texts[c]["n_answered"],
                       "n_real": texts[c]["n_real"], "themes": None} for c in text_cols],
        "methods": methods,
        "caveats": caveats,
    }
    return results, texts


def summary_text(results: dict) -> str:
    """Compact plain-text digest of results for Claude to read."""
    r = results
    out = [f"Analysed {r['meta']['n_analysed']} of {r['meta']['n_rows']} rows"
           + (f" (filters: {'; '.join(r['meta']['filters'])})" if r['meta']['filters'] else "")
           + f"; removed {r['meta']['excluded']['speeders']} speeders and {r['meta']['excluded']['straightliners']} straight-liners."]
    h = r["health"]
    out.append(f"Health: {h['completed']}/{h['started']} finished ({h['completion_pct']}%), "
               f"{h['red']} red and {h['yellow']} yellow questions, {h['routed']} routed by skip logic.")
    k = r["kpi"]
    if k and k.get("n"):
        out.append(f"KPI {k['column']} ({k['type']}): {k['value']} (likely {k['ci'][0]} to {k['ci'][1]}), n={k['n']}.")
    d = r["drivers"]
    if d.get("available"):
        out.append(f"Drivers (explain {d['r2']}% of KPI variation):")
        for x in d["drivers"][:8]:
            out.append(f"  {x['column']}: importance {x['importance']}%, performance {x['performance']}%, zone {x['zone']}"
                       + (" (NEGATIVE direction)" if x["direction"] == "negative" else ""))
    else:
        out.append("Drivers: " + d.get("reason", "not run"))
    for c in r["comparisons"]:
        gs = ", ".join(f"{g['value']}={g['value_metric']} (n={g['n']}, {g.get('verdict')})" for g in c["groups"])
        out.append(f"By {c['dimension']}: {gs}")
        if c.get("extremes"):
            e = c["extremes"]
            out.append(f"  biggest gap {e['high']} vs {e['low']}: {e['gap']} ({e['verdict']})")
        if c.get("pair"):
            real = [i for i in c["pair"]["items"] if i["verdict"] == "real"]
            out.append(f"  items differing between {c['pair']['a']} and {c['pair']['b']}: "
                       + (", ".join(f"{i['column']} {i['a']} vs {i['b']}" for i in real[:6]) or "none beyond chance"))
    s = r["segments"]
    if s.get("available"):
        out.append(f"Segments: {s['k']} ({s['strength']} separation)")
        for x in s["segments"]:
            out.append(f"  seg {x['id']}: {x['size_pct']}%, KPI {x.get('kpi')}, high on "
                       f"{[h['column'] for h in x['high']]}, low on {[l['column'] for l in x['low']]}, skews {x['skews']}")
    else:
        out.append("Segments: " + s.get("reason", "not run"))
    if r["trend"]:
        t = r["trend"]
        out.append(f"Trend: last change {t['last_change']} ({t['verdict']}); mix shifts: {t['mix_shifts']}")
    for o in r["open_text"]:
        out.append(f"Open text {o['column']}: {o['n_real']} real answers" + (" (themes coded)" if o["themes"] else
                                                                              " (needs coding)"))
    for c in r["caveats"]:
        out.append(f"Caveat [{c['level']}]: {c['text']}")
    return "\n".join(out)
