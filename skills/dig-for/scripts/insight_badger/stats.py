"""Significance tests and corrections used for group comparisons.

All tests return plain floats so results serialise to JSON. p-values are
adjusted for the number of comparisons with Holm's method before any gap is
reported as real.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats as sps

MIN_BASE = 30          # groups smaller than this are shown greyed out, never called significant
ALPHA = 0.05
MIN_GAP_PP = 5.0       # percentage points for top-box / proportions
MIN_GAP_NPS = 10.0     # NPS points


def weighted_n(w: np.ndarray) -> float:
    """Kish effective sample size."""
    w = np.asarray(w, dtype=float)
    if w.size == 0 or w.sum() == 0:
        return 0.0
    return float(w.sum() ** 2 / (w ** 2).sum())


def prop_ci(p: float, n_eff: float, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion (0..1)."""
    if n_eff <= 0:
        return (math.nan, math.nan)
    denom = 1 + z ** 2 / n_eff
    centre = (p + z ** 2 / (2 * n_eff)) / denom
    half = z * math.sqrt(p * (1 - p) / n_eff + z ** 2 / (4 * n_eff ** 2)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def two_prop_test(p1: float, n1: float, p2: float, n2: float) -> float:
    """Two-sided z-test for the difference of two independent proportions."""
    if n1 <= 0 or n2 <= 0:
        return math.nan
    pooled = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0 if p1 == p2 else 0.0
    z = (p1 - p2) / se
    return float(2 * sps.norm.sf(abs(z)))


def nps_var(p_pro: float, p_det: float, n_eff: float) -> float:
    """Variance of NPS (as a -1..1 difference). Promoter and detractor shares
    come from one multinomial, so their covariance (-p+ p-) must be included:
    Var = (p+ + p- - (p+ - p-)^2) / n."""
    if n_eff <= 0:
        return math.nan
    return (p_pro + p_det - (p_pro - p_det) ** 2) / n_eff


def nps_diff_test(a: dict, b: dict) -> float:
    """Two-sided test for the difference between two independent NPS values."""
    va = nps_var(a["promoters"] / 100, a["detractors"] / 100, a["n_eff"])
    vb = nps_var(b["promoters"] / 100, b["detractors"] / 100, b["n_eff"])
    if not (va + vb) > 0:
        return math.nan
    z = ((a["nps"] - b["nps"]) / 100) / math.sqrt(va + vb)
    return float(2 * sps.norm.sf(abs(z)))


def chi2_test(table: np.ndarray) -> tuple[float, float]:
    """Chi-squared test of independence; returns (p, Cramér's V)."""
    table = np.asarray(table, dtype=float)
    table = table[table.sum(axis=1) > 0][:, table.sum(axis=0) > 0]
    if table.shape[0] < 2 or table.shape[1] < 2:
        return (math.nan, math.nan)
    chi2, p, _dof, _exp = sps.chi2_contingency(table, correction=False)
    n = table.sum()
    v = math.sqrt(chi2 / (n * (min(table.shape) - 1))) if n else math.nan
    return (float(p), float(v))


def rank_test(groups: list[np.ndarray]) -> float:
    """Mann-Whitney (2 groups) or Kruskal-Wallis (3+) for ordinal ratings."""
    groups = [g[~np.isnan(g)] for g in groups]
    groups = [g for g in groups if len(g) > 0]
    if len(groups) < 2:
        return math.nan
    try:
        if len(groups) == 2:
            return float(sps.mannwhitneyu(groups[0], groups[1], alternative="two-sided").pvalue)
        return float(sps.kruskal(*groups).pvalue)
    except ValueError:
        return 1.0


def holm(pvalues: list[float]) -> list[float]:
    """Holm step-down adjustment. NaNs are kept as NaN."""
    idx = [i for i, p in enumerate(pvalues) if p is not None and not math.isnan(p)]
    m = len(idx)
    out = [math.nan] * len(pvalues)
    order = sorted(idx, key=lambda i: pvalues[i])
    running = 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * pvalues[i])
        running = max(running, adj)
        out[i] = running
    return out


def verdict(p_adj: float, gap: float, min_gap: float, n_min: float) -> str:
    """Plain-language confidence label used across the report."""
    if n_min < MIN_BASE:
        return "small-base"
    if math.isnan(p_adj):
        return "untested"
    if p_adj < ALPHA and abs(gap) >= min_gap:
        return "real"
    if p_adj < 0.2 and abs(gap) >= min_gap:
        return "probable"
    return "chance"
