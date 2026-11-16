"""Attitudinal segmentation: groups of people who answered the rating items alike."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


def segment(codes: pd.DataFrame, labels: dict[str, str], exclude: pd.Series | None = None,
            k_range=range(3, 7), seed: int = 42) -> dict:
    usable = [c for c in codes.columns if codes[c].notna().mean() >= 0.8 and codes[c].nunique() > 1]
    if len(usable) < 5:
        return {"available": False, "reason": "Fewer than 5 rating items answered by most people."}
    X = codes[usable]
    rows = X.notna().mean(axis=1) >= 0.8
    if exclude is not None:
        rows &= ~exclude.reindex(X.index).fillna(False).astype(bool)
    X = X[rows]
    if len(X) < 100:
        return {"available": False, "reason": f"Only {len(X)} complete answer sets; at least 100 are needed."}
    X = X.fillna(X.median())
    Z = (X - X.mean()) / X.std(ddof=0).replace(0, 1)
    best = None
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=seed, n_init=10).fit(Z)
        sizes = np.bincount(km.labels_, minlength=k) / len(Z)
        if sizes.min() < 0.05:
            continue
        sil = silhouette_score(Z, km.labels_, sample_size=min(2000, len(Z)), random_state=seed)
        if best is None or sil > best[0]:
            best = (sil, k, km)
    if best is None:
        return {"available": False, "reason": "No grouping produced segments of a useful size."}
    sil, k, km = best
    lab = pd.Series(km.labels_, index=X.index)
    # Order segments by average rating, highest first, so ids are stable and meaningful
    order = X.mean(axis=1).groupby(lab).mean().sort_values(ascending=False).index.tolist()
    remap = {old: new for new, old in enumerate(order)}
    lab = lab.map(remap)
    grand = X.mean()
    sd = X.std(ddof=0).replace(0, 1)
    segs = []
    for s in range(k):
        member = X[lab == s]
        diff = ((member.mean() - grand) / sd).sort_values()
        segs.append({
            "id": s,
            "size_pct": round(len(member) / len(X) * 100, 1),
            "n": int(len(member)),
            "high": [{"column": c, "label": labels.get(c, c), "z": round(float(diff[c]), 2)}
                     for c in diff.index[::-1][:3] if diff[c] > 0.2],
            "low": [{"column": c, "label": labels.get(c, c), "z": round(float(diff[c]), 2)}
                    for c in diff.index[:3] if diff[c] < -0.2],
            "means": {c: round(float(member[c].mean()), 2) for c in usable},
        })
    return {
        "available": True,
        "k": int(k),
        "silhouette": round(float(sil), 3),
        "strength": "clear" if sil >= 0.25 else "moderate" if sil >= 0.12 else "weak",
        "items": usable,
        "segments": segs,
        "_labels": lab,
    }
