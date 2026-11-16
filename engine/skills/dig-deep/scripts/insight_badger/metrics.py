"""Per-question metrics. Every function accepts optional survey weights."""

from __future__ import annotations

import math
from collections import Counter

import numpy as np
import pandas as pd

from . import scales
from .stats import nps_var, prop_ci, weighted_n


def encode_column(series: pd.Series, info: dict) -> pd.Series:
    """Numeric codes for any rating column (text scales, '5 - Agree', numbers)."""
    if info.get("scale"):
        return scales.encode(series, info["scale"])
    return scales.encode(series)


def _w(weights, index) -> pd.Series:
    if weights is None:
        return pd.Series(1.0, index=index)
    return weights.reindex(index).fillna(0).astype(float)


def top_box_levels(info: dict) -> tuple[list[int], list[int], list[int]]:
    """Codes counted as top box, bottom box and neutral for a rating column."""
    pts = int(info.get("points") or 5)
    t = info.get("type")
    if t == "rating":
        lo = int(info.get("min", 0 if pts == 11 else 1))
        hi = 10
        return [hi - 1, hi], [lo, lo + 1], []
    lo, hi = 1, pts
    top = [hi - 1, hi] if pts >= 4 else [hi]
    bottom = [lo, lo + 1] if pts >= 4 else [lo]
    mid = [(lo + hi) // 2] if pts % 2 == 1 else []
    return top, bottom, mid


def rating_summary(codes: pd.Series, info: dict, weights=None) -> dict:
    """Top-2-box, bottom-2-box, net, mean and the full distribution."""
    valid = codes.dropna()
    w = _w(weights, valid.index)
    total = w.sum()
    pts = int(info.get("points") or 5)
    top, bottom, mid = top_box_levels(info)
    if info.get("type") == "rating":
        levels = list(range(int(info.get("min", 0 if pts == 11 else 1)), 11))
    else:
        levels = list(range(1, pts + 1))
    labels = scales.scale_labels(info["scale"]) if info.get("scale") else [str(x) for x in levels]
    if total == 0:
        return {"n": 0, "n_eff": 0.0}
    dist = []
    for lv, lab in zip(levels, labels):
        share = float(w[valid == lv].sum() / total)
        dist.append({"code": lv, "label": lab, "pct": round(share * 100, 1), "count": int((valid == lv).sum())})
    t2b = float(w[valid.isin(top)].sum() / total)
    b2b = float(w[valid.isin(bottom)].sum() / total)
    n_eff = weighted_n(w.values)
    lo, hi = prop_ci(t2b, n_eff)
    return {
        "n": int(len(valid)),
        "n_eff": round(n_eff, 1),
        "top_box": round(t2b * 100, 1),
        "top_box_ci": [round(lo * 100, 1), round(hi * 100, 1)],
        "bottom_box": round(b2b * 100, 1),
        "neutral": round(float(w[valid.isin(mid)].sum() / total) * 100, 1) if mid else 0.0,
        "net": round((t2b - b2b) * 100, 1),
        "mean": round(float(np.average(valid, weights=w)), 2),
        "distribution": dist,
        "top_codes": top,
        "bottom_codes": bottom,
    }


def nps_summary(codes: pd.Series, weights=None) -> dict:
    v = codes.dropna()
    v = v[(v >= 0) & (v <= 10)]
    w = _w(weights, v.index)
    total = w.sum()
    if total == 0:
        return {"n": 0, "n_eff": 0.0}
    pro = float(w[v >= 9].sum() / total)
    det = float(w[v <= 6].sum() / total)
    pas = 1 - pro - det
    n_eff = weighted_n(w.values)
    score = (pro - det) * 100
    half = 1.96 * math.sqrt(nps_var(pro, det, n_eff)) * 100 if n_eff > 0 else math.nan
    return {
        "n": int(len(v)),
        "n_eff": round(n_eff, 1),
        "nps": round(score, 1),
        "ci": [round(max(-100, score - half), 1), round(min(100, score + half), 1)],
        "promoters": round(pro * 100, 1),
        "passives": round(pas * 100, 1),
        "detractors": round(det * 100, 1),
        "mean": round(float(np.average(v, weights=w)), 2),
        "distribution": [{"code": k, "label": str(k), "pct": round(float(w[v == k].sum() / total) * 100, 1),
                          "count": int((v == k).sum())} for k in range(11)],
    }


def nps_group(codes: pd.Series) -> pd.Series:
    """Promoter / Passive / Detractor label per respondent."""
    return codes.map(lambda x: np.nan if pd.isna(x) else ("Promoter" if x >= 9 else "Passive" if x >= 7 else "Detractor"))


def categorical_summary(series: pd.Series, weights=None, max_slices: int = 8) -> dict:
    s = series.dropna().astype(str).str.strip()
    s = s[s != ""]
    w = _w(weights, s.index)
    total = w.sum()
    if total == 0:
        return {"n": 0, "options": []}
    shares = w.groupby(s).sum().sort_values(ascending=False) / total
    counts = s.value_counts()
    opts = [{"label": k, "pct": round(float(v) * 100, 1), "count": int(counts.get(k, 0))} for k, v in shares.items()]
    if len(opts) > max_slices:
        head, tail = opts[: max_slices - 1], opts[max_slices - 1:]
        opts = head + [{"label": f"Other ({len(tail)} answers)", "pct": round(sum(o["pct"] for o in tail), 1),
                        "count": sum(o["count"] for o in tail), "other": True}]
    return {"n": int(len(s)), "n_eff": round(weighted_n(w.values), 1), "options": opts, "modal": opts[0]["label"]}


def multiselect_matrix(df: pd.DataFrame, group: dict) -> pd.DataFrame:
    """Respondent x option boolean matrix for a multi-select battery.

    Exports mark a selected option with 1 / option text / 'Yes' and leave
    unselected options blank (Qualtrics, SurveyMonkey) or 0 / 'No'.
    """
    out = {}
    for c in group["columns"]:
        s = df[c]
        sel = s.notna() & ~s.astype(str).str.strip().str.lower().isin(
            ["0", "0.0", "no", "n", "false", "unchecked", "not selected", ""])
        out[group["options"][c]] = sel
    return pd.DataFrame(out, index=df.index)


def explode_multiselect_string(series: pd.Series, delimiter: str) -> pd.DataFrame:
    from .detect import delimiter_pattern
    s = series.dropna().astype(str)
    parts = s.str.split(delimiter_pattern(delimiter))
    parts = parts.map(lambda xs: [x.strip() for x in xs if x.strip()])
    options = [o for o, _ in Counter(o for xs in parts for o in xs).most_common()]
    mat = pd.DataFrame(False, index=series.index, columns=options)
    for idx, xs in parts.items():
        for x in xs:
            mat.at[idx, x] = True
    mat.loc[series.isna()] = False
    mat.attrs["answered"] = series.notna()
    return mat


def multiselect_summary(mat: pd.DataFrame, answered: pd.Series | None = None, weights=None) -> dict:
    base_note = "respondents who answered" if answered is not None else "respondents who chose at least one option"
    if answered is None:
        answered = mat.any(axis=1)
    base = mat[answered]
    w = _w(weights, base.index)
    total = w.sum()
    if total == 0:
        return {"n": 0, "options": []}
    opts = []
    for c in base.columns:
        opts.append({"label": str(c), "pct": round(float(w[base[c]].sum() / total) * 100, 1),
                     "count": int(base[c].sum())})
    opts.sort(key=lambda o: -o["pct"])
    combos = base.apply(lambda r: " + ".join(sorted(str(c) for c in base.columns[r.values.astype(bool)])), axis=1)
    combos = combos[combos != ""].value_counts().head(5)
    return {
        "n": int(len(base)),
        "n_eff": round(weighted_n(w.values), 1),
        "base_note": base_note,
        "options": opts,
        "mean_selected": round(float(np.average(base.sum(axis=1), weights=w)), 2),
        "top_combinations": [{"combo": k, "pct": round(v / len(base) * 100, 1)} for k, v in combos.items()],
    }


def numeric_summary(series: pd.Series, weights=None) -> dict:
    v = pd.to_numeric(series, errors="coerce").dropna()
    if len(v) == 0:
        return {"n": 0}
    hist, edges = np.histogram(v, bins=min(12, max(4, int(np.sqrt(len(v))))))
    return {
        "n": int(len(v)),
        "mean": round(float(v.mean()), 2),
        "median": round(float(v.median()), 2),
        "p25": round(float(v.quantile(.25)), 2),
        "p75": round(float(v.quantile(.75)), 2),
        "min": round(float(v.min()), 2),
        "max": round(float(v.max()), 2),
        "histogram": [{"from": round(float(a), 2), "to": round(float(b), 2), "count": int(c)}
                      for a, b, c in zip(edges[:-1], edges[1:], hist)],
    }
