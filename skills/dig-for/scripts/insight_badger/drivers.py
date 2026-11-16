"""Key-driver analysis and battery reliability."""

from __future__ import annotations

import numpy as np
import pandas as pd


def cronbach_alpha(codes: pd.DataFrame) -> float | None:
    items = codes.dropna()
    k = items.shape[1]
    if k < 2 or len(items) < 10:
        return None
    total_var = items.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return None
    return float((k / (k - 1)) * (1 - items.var(axis=0, ddof=1).sum() / total_var))


def relative_weights(X: pd.DataFrame, y: pd.Series) -> tuple[pd.Series, float]:
    """Johnson's relative weights: each driver's share of explained variance (R²).

    Robust to drivers that are correlated with each other, which rating items
    almost always are.
    """
    Z = (X - X.mean()) / X.std(ddof=0)
    yz = (y - y.mean()) / y.std(ddof=0)
    n = len(yz)
    R = np.corrcoef(Z.values.T)
    rxy = Z.values.T @ yz.values / n
    evals, evecs = np.linalg.eigh(R)
    evals = np.clip(evals, 1e-10, None)
    lam = evecs @ np.diag(np.sqrt(evals)) @ evecs.T
    beta = np.linalg.solve(lam, rxy)
    raw = (lam ** 2) @ (beta ** 2)
    r2 = float((beta ** 2).sum())
    return pd.Series(raw, index=X.columns), r2


def driver_analysis(codes: pd.DataFrame, kpi: pd.Series, top_codes: dict[str, list[int]],
                    labels: dict[str, str]) -> dict:
    """Importance (relative weight share) and performance (top-box %) per driver."""
    notes = []
    keep = [c for c in codes.columns if codes[c].notna().mean() >= 0.6 and codes[c].nunique() > 1]
    dropped = [c for c in codes.columns if c not in keep]
    if dropped:
        notes.append(f"Left out {len(dropped)} item(s) answered by fewer than 60% of people: {', '.join(dropped[:5])}")
    if len(keep) < 3:
        return {"available": False, "reason": "Fewer than 3 usable rating items to compare."}
    data = codes[keep].copy()
    data["_y"] = kpi
    data = data.dropna(subset=["_y"])
    if len(data) < 50:
        return {"available": False, "reason": f"Only {len(data)} people answered the KPI; at least 50 are needed."}
    if len(data) < 10 * len(keep):
        notes.append("Few respondents for the number of items, so rankings of close drivers may swap.")
    X = data[keep].fillna(data[keep].median())
    y = data["_y"]
    raw, r2 = relative_weights(X, y)
    share = raw / raw.sum() * 100 if raw.sum() > 0 else raw * 0
    corr = X.apply(lambda c: c.corr(y, method="spearman"))
    rows = []
    for c in keep:
        perf = float(codes[c].dropna().isin(top_codes[c]).mean() * 100)
        rows.append({
            "column": c,
            "label": labels.get(c, c),
            "importance": round(float(share[c]), 1),
            "performance": round(perf, 1),
            "direction": "positive" if corr[c] >= 0 else "negative",
            "correlation": round(float(corr[c]), 2),
        })
    rows.sort(key=lambda r: -r["importance"])
    mean_imp = 100 / len(rows)
    mean_perf = float(np.mean([r["performance"] for r in rows]))
    for r in rows:
        hi_imp = r["importance"] >= mean_imp
        hi_perf = r["performance"] >= mean_perf
        r["zone"] = ("protect" if hi_perf else "fix") if hi_imp else ("nice" if hi_perf else "monitor")
    neg = [r["label"] for r in rows if r["direction"] == "negative"]
    if neg:
        notes.append("Higher scores on these go with a lower KPI (check wording): " + ", ".join(neg[:4]))
    return {
        "available": True,
        "n": int(len(data)),
        "r2": round(r2 * 100, 1),
        "split_importance": round(mean_imp, 1),
        "split_performance": round(mean_perf, 1),
        "drivers": rows,
        "notes": notes,
    }
