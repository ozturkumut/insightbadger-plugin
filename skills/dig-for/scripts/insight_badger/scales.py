"""Answer-scale vocabulary and ordinal encoding.

Text answers such as "Neither agree nor disagree" are matched against known
ordered scales so that every downstream method works on numeric codes
(1 = lowest). "Don't know" style answers are treated as missing, so they never
enter the base of a percentage.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

# Each scale is listed from lowest to highest. Several spellings can share a
# position: a tuple at a position means "any of these".
SCALES: dict[str, list] = {
    "agree-5": [("strongly disagree",), ("disagree", "somewhat disagree", "tend to disagree"),
                ("neither agree nor disagree", "neutral", "neither", "neither agree or disagree", "undecided"),
                ("agree", "somewhat agree", "tend to agree"), ("strongly agree",)],
    "agree-7": [("strongly disagree",), ("disagree",), ("somewhat disagree", "slightly disagree"),
                ("neither agree nor disagree", "neutral", "neither", "neither agree or disagree"),
                ("somewhat agree", "slightly agree"), ("agree",), ("strongly agree",)],
    "agree-4": [("strongly disagree",), ("disagree", "somewhat disagree"), ("agree", "somewhat agree"), ("strongly agree",)],
    "satisfied-5": [("very dissatisfied", "extremely dissatisfied"), ("dissatisfied", "somewhat dissatisfied"),
                    ("neither satisfied nor dissatisfied", "neutral", "neither", "neither satisfied or dissatisfied"),
                    ("satisfied", "somewhat satisfied"), ("very satisfied", "extremely satisfied")],
    "satisfied-7": [("extremely dissatisfied", "very dissatisfied"), ("dissatisfied", "moderately dissatisfied"),
                    ("somewhat dissatisfied", "slightly dissatisfied"),
                    ("neither satisfied nor dissatisfied", "neutral", "neither"),
                    ("somewhat satisfied", "slightly satisfied"), ("satisfied", "moderately satisfied"),
                    ("extremely satisfied", "very satisfied")],
    "frequency-5": [("never",), ("rarely",), ("sometimes", "occasionally"), ("often", "frequently", "usually"),
                    ("always", "very often")],
    "quality-5": [("very poor", "terrible"), ("poor",), ("fair", "average", "okay", "ok"), ("good",),
                  ("excellent", "very good")],
    "likely-5": [("very unlikely", "extremely unlikely", "not at all likely"), ("unlikely", "somewhat unlikely"),
                 ("neither likely nor unlikely", "neutral", "not sure"), ("likely", "somewhat likely"),
                 ("very likely", "extremely likely")],
    "important-5": [("not at all important",), ("slightly important", "not very important", "low importance"),
                    ("moderately important", "somewhat important", "neutral"), ("very important", "important"),
                    ("extremely important",)],
    "easy-5": [("very difficult", "extremely difficult"), ("difficult", "somewhat difficult"),
               ("neither easy nor difficult", "neutral", "neither"), ("easy", "somewhat easy"),
               ("very easy", "extremely easy")],
    "expectations-5": [("much worse than expected", "far below expectations"),
                       ("worse than expected", "below expectations"),
                       ("as expected", "met expectations", "about what i expected"),
                       ("better than expected", "above expectations"),
                       ("much better than expected", "far exceeded expectations", "far above expectations")],
}

# Answers that mean "no opinion"; excluded from the base of every metric.
NOT_APPLICABLE = {
    "n/a", "na", "not applicable", "does not apply", "doesn't apply", "don't know", "dont know",
    "do not know", "dk", "not sure / don't know", "prefer not to say", "prefer not to answer",
    "no opinion", "unsure", "can't say", "cannot say", "don't know / not applicable",
    "not applicable / don't know", "i don't know", "rather not say",
}

_PREFIX = re.compile(r"^\s*\(?(\d{1,2})\)?\s*[-:=.)]\s*")
_SUFFIX = re.compile(r"\s*[\(\[]\s*(\d{1,2})\s*[\)\]]\s*$")


def norm(value) -> str:
    """Lower-case, trim, and drop numeric prefixes like '5 - Strongly agree'."""
    s = str(value).strip().lower()
    s = s.replace("’", "'").replace("‘", "'")
    s = _PREFIX.sub("", s)
    s = _SUFFIX.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s


def leading_number(value):
    """Return the integer at the start of '10 - Extremely likely', else None."""
    s = str(value).strip()
    m = re.match(r"^\s*(\d{1,2})(?:\s*[-:=.)]|\s|$)", s)
    if m:
        return int(m.group(1))
    try:
        f = float(s)
        if f.is_integer():
            return int(f)
    except ValueError:
        pass
    return None


def is_na_answer(value) -> bool:
    return norm(value) in NOT_APPLICABLE


def _positions(scale: list) -> dict[str, int]:
    out = {}
    for i, spellings in enumerate(scale):
        for sp in spellings:
            out[sp] = i + 1
    return out


SCALE_LOOKUP = {name: _positions(levels) for name, levels in SCALES.items()}


def match_scale(values, min_distinct: int = 2):
    """Find the known scale that covers every non-N/A value.

    Returns ``(scale_name, n_points)`` or ``None``. Prefers the scale with the
    fewest points that still covers all values, so a 5-point agreement item is
    not read as 7-point.
    """
    vals = {norm(v) for v in values if not pd.isna(v) and str(v).strip() != ""}
    vals = {v for v in vals if v not in NOT_APPLICABLE}
    if len(vals) < min_distinct:
        return None
    best = None
    for name, lookup in SCALE_LOOKUP.items():
        if vals.issubset(lookup.keys()):
            n_points = len(SCALES[name])
            # Different answers must land on different positions: data holding
            # both "disagree" and "somewhat disagree" is a 7-point scale.
            if len({lookup[v] for v in vals}) != len(vals):
                continue
            if best is None or n_points < best[1]:
                best = (name, n_points)
    return best


def scale_labels(scale_name: str) -> list[str]:
    """Display label per position (first spelling, sentence case)."""
    return [spellings[0].capitalize() for spellings in SCALES[scale_name]]


def encode(series: pd.Series, scale: str | None = None) -> pd.Series:
    """Encode answers to numeric codes. N/A and unknown text become NaN.

    * Known text scale -> 1..k
    * '5 - Strongly agree' style -> the leading number
    * Numbers -> float
    """
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)
    if scale and scale in SCALE_LOOKUP:
        lookup = SCALE_LOOKUP[scale]
        return series.map(lambda v: np.nan if pd.isna(v) else lookup.get(norm(v), np.nan)).astype(float)

    def conv(v):
        if pd.isna(v) or is_na_answer(v):
            return np.nan
        n = leading_number(v)
        return float(n) if n is not None else np.nan

    return series.map(conv).astype(float)
