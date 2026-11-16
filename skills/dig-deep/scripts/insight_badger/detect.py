"""Question-type detection and questionnaire reconstruction.

Every column gets a type. Related columns are grouped into rating batteries
(matrix questions) and multi-select questions. The result is the *profile*,
which Claude reviews and can correct before analysis.
"""

from __future__ import annotations

import re
from collections import defaultdict

import numpy as np
import pandas as pd

from . import scales

RATING_TYPES = ("likert", "csat", "ces", "rating", "nps")
ORDINAL_TYPES = ("likert", "csat", "ces", "rating")

_META = re.compile(
    r"(^|\b)(response ?id|respondent ?id|responseid|respondentid|collector ?id|recipient\w*|"
    r"external ?(data )?reference|externalreference|ip ?address|ipaddress|"
    r"location ?(latitude|longitude)|locationlatitude|locationlongitude|distribution ?channel|"
    r"distributionchannel|user ?language|userlanguage|start ?date|end ?date|startdate|enddate|"
    r"recorded ?date|recordeddate|progress|finished|duration( \(in seconds\))?|"
    r"timestamp|submitted at|submission date|completion time|start time|end time|"
    r"network id|custom data|q_(recaptchascore|relevantid\w*|totalduration|ballotboxstuffing|"
    r"languagecode|url|duplicate\w*))($|\b)",
    re.IGNORECASE,
)
_PII = re.compile(
    r"(e-?mail|ip ?address|ipaddress|first ?name|last ?name|full ?name|^name$|your name|phone ?number|"
    r"telephone|mobile ?(number|phone)|^phone$|latitude|longitude|recipient|postcode|post code|zip ?code|"
    r"street|home address|postal address)",
    re.IGNORECASE,
)
_NPS_HINT = re.compile(r"(nps|recommend)", re.IGNORECASE)
_CSAT_HINT = re.compile(r"(csat|satisf)", re.IGNORECASE)
_CES_HINT = re.compile(r"(effort|\bces\b|easy|ease)", re.IGNORECASE)
_TEXT_HINT = re.compile(
    r"(why|comment|feedback|verbatim|please (explain|describe|specify|tell)|tell us|anything else|"
    r"what (else|could|would|is the one)|suggest|improve|_text$|other \(please)",
    re.IGNORECASE,
)
_DEMO_HINT = re.compile(
    r"(\bage\b|gender|\bsex\b|region|country|\bstate\b|province|city|\brole\b|job|title|seniority|"
    r"department|industry|sector|company ?size|employees|organi[sz]ation size|team size|"
    r"how many (people|staff|employees)|people work|work at your|number of (staff|people)|"
    r"tenure|how long have you|customer for|\bplan\b|\btier\b|segment|education|income|ethnic|"
    r"customer type|account type)",
    re.IGNORECASE,
)
_DATE = re.compile(r"^\s*\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}([ T]\d{1,2}:\d{2}(:\d{2})?.*)?\s*$")
_BINARY_TEXT = {"1", "0", "yes", "no", "y", "n", "true", "false", "checked", "unchecked", "selected",
                "not selected", "x"}


def _is_int_like(s: pd.Series) -> bool:
    return bool(np.all(np.isclose(s, np.round(s))))


def _text_stats(s: pd.Series):
    st = s.astype(str)
    return st.str.len().mean(), s.nunique(), len(s)


def _delimited_multiselect(s: pd.Series, delim: str) -> bool:
    """'A; B; C' or Google Forms 'A, B, C' answers: a small set of short options
    that recur across respondents. Free-text comments fail this test."""
    st = s.astype(str)
    pattern = r"\s*" + re.escape(delim) + r"\s*"
    if st.str.contains(re.escape(delim)).mean() < 0.15:
        return False
    tokens = st.str.split(pattern).explode().str.strip()
    tokens = tokens[tokens != ""]
    if len(tokens) == 0:
        return False
    counts = tokens.value_counts()
    recurring = counts[counts >= 3]
    if len(recurring) == 0:
        return False
    coverage = recurring.sum() / len(tokens)
    words = tokens.str.split().str.len()
    multi = (st.str.split(pattern).str.len() > 1).mean()
    return (coverage >= 0.85 and len(recurring) <= 40 and words.median() <= 5
            and tokens.str.len().mean() < 40 and multi >= 0.15)


def detect_column(series: pd.Series, name: str, label: str) -> dict:
    """Return {'type': ..., plus details} for one column."""
    hint = f"{name} {label}"
    s = series.dropna()
    s = s[s.astype(str).str.strip() != ""]
    info: dict = {"pii": bool(_PII.search(name) or _PII.search(label[:80]))}
    if len(s) == 0:
        return {**info, "type": "empty"}
    if _META.search(name) or (label != name and _META.fullmatch(label.strip() or "-")):
        return {**info, "type": "metadata"}

    numeric = pd.to_numeric(s, errors="coerce")
    if numeric.notna().mean() >= 0.98:
        v = numeric.dropna()
        vals = set(v.unique())
        lo, hi = v.min(), v.max()
        if _is_int_like(v):
            if vals <= {0, 1}:
                return {**info, "type": "binary"}
            if lo >= 0 and hi <= 10 and (_NPS_HINT.search(hint) or (0 in vals and hi >= 9 and len(vals) >= 6)):
                return {**info, "type": "nps", "points": 11}
            if lo >= 1 and hi <= 5:
                t = "csat" if _CSAT_HINT.search(hint) else "likert"
                return {**info, "type": t, "points": 5}
            if lo >= 1 and hi <= 7:
                t = "ces" if _CES_HINT.search(hint) else "likert"
                return {**info, "type": t, "points": 7}
            if lo >= 0 and hi <= 10 and len(vals) >= 3:
                return {**info, "type": "rating", "points": 10 if lo >= 1 else 11, "min": int(lo)}
            if _DEMO_HINT.search(hint):
                return {**info, "type": "demographic", "numeric": True}
            if len(vals) <= 12 and hi <= 20:
                return {**info, "type": "single-choice"}
        if _DEMO_HINT.search(hint):
            return {**info, "type": "demographic", "numeric": True}
        return {**info, "type": "numeric"}

    # Text answers
    st = s.astype(str)
    if st.map(lambda x: bool(_DATE.match(x))).mean() > 0.9:
        return {**info, "type": "datetime"}

    m = scales.match_scale(st.unique())
    if m:
        name_, points = m
        t = "likert"
        if name_.startswith("satisfied") and _CSAT_HINT.search(hint):
            t = "csat"
        if name_.startswith("easy") and _CES_HINT.search(hint):
            t = "ces"
        return {**info, "type": t, "scale": name_, "points": points}

    # "10 - Extremely likely" / "0 - Not at all likely" style NPS or numbered scales
    nums = st[~st.map(scales.is_na_answer)].map(scales.leading_number)
    if len(nums) and nums.notna().mean() > 0.95:
        nv = set(nums.dropna().astype(int))
        if nv <= set(range(0, 11)) and (_NPS_HINT.search(hint) or (0 in nv and max(nv) >= 9)):
            return {**info, "type": "nps", "points": 11, "numbered_text": True}
        if nv <= set(range(1, 6)):
            return {**info, "type": "csat" if _CSAT_HINT.search(hint) else "likert", "points": 5, "numbered_text": True}
        if nv <= set(range(1, 8)):
            return {**info, "type": "ces" if _CES_HINT.search(hint) else "likert", "points": 7, "numbered_text": True}
        if nv <= set(range(0, 11)):
            return {**info, "type": "rating", "points": 11 if 0 in nv else 10, "numbered_text": True}

    low = {x.strip().lower() for x in st.unique()}
    if low <= _BINARY_TEXT and len(low) <= 2:
        return {**info, "type": "binary"}

    for delim in (";", "|", ","):
        if _delimited_multiselect(st, delim):
            return {**info, "type": "multi-select-string", "delimiter": delim}

    avg_len, n_unique, n = _text_stats(st)
    if avg_len > 30 or (n_unique / n > 0.6 and avg_len > 12 and n >= 10):
        return {**info, "type": "open-text"}
    if _TEXT_HINT.search(hint) and n_unique / n > 0.3 and avg_len > 8:
        return {**info, "type": "open-text"}
    if _DEMO_HINT.search(hint) and n_unique <= 40:
        return {**info, "type": "demographic"}
    if n_unique <= 25:
        return {**info, "type": "single-choice"}
    if avg_len > 10:
        return {**info, "type": "open-text"}
    return {**info, "type": "unknown"}


_STEM = re.compile(r"^(?P<stem>.*?)(?:[_.\-#](?P<item>[A-Za-z]?\d+[A-Za-z]?|[A-Za-z]))$")


def _stem(col: str, label: str) -> str | None:
    """Group key for matrix / multi-select items."""
    m = _STEM.match(col)
    if m and m.group("stem"):
        return m.group("stem")
    for sep in (" | ", " - "):
        if sep in label:
            return label.split(sep)[0].strip()
    m = re.match(r"^(.*)\[(.+)\]\s*$", label)  # Google Forms grid: "Question [Row]"
    if m:
        return m.group(1).strip()
    return None


def _item_label(col: str, label: str) -> str:
    for sep in (" | ", " - "):
        if sep in label:
            return label.split(sep, 1)[1].strip()
    m = re.match(r"^(.*)\[(.+)\]\s*$", label)
    if m:
        return m.group(2).strip()
    return label


def build_profile(survey, codebook: dict | None = None, overrides: dict | None = None) -> dict:
    df, labels = survey.df, dict(survey.labels)
    codebook = codebook or {}
    for col, entry in codebook.items():
        if col in labels and entry.get("question_text"):
            labels[col] = entry["question_text"]

    cols: dict[str, dict] = {}
    for c in df.columns:
        info = detect_column(df[c], c, labels.get(c, c))
        cb_type = codebook.get(c, {}).get("type")
        if cb_type:
            info["type"] = cb_type
            info["from_codebook"] = True
        info.update({"id": c, "label": labels.get(c, c)})
        cols[c] = info

    # Multi-select batteries: sibling columns that hold one value (or 0/1) each.
    groups: list[dict] = []
    by_stem: dict[str, list[str]] = defaultdict(list)
    for c, info in cols.items():
        st = _stem(c, info["label"])
        if st:
            by_stem[st].append(c)
    used: set[str] = set()
    for stem, members in by_stem.items():
        if len(members) < 2:
            continue
        ms = []
        for c in members:
            s = df[c].dropna()
            if c.upper().endswith("_TEXT"):
                continue
            distinct = {str(v).strip().lower() for v in s.unique()}
            if cols[c]["type"] in ("binary",) or (len(distinct) == 1 and cols[c]["type"] in
                                                  ("single-choice", "binary", "unknown", "demographic", "likert", "numeric")):
                ms.append(c)
        if len(ms) >= 2 and len(ms) >= 0.6 * len([m for m in members if not m.upper().endswith("_TEXT")]):
            gid = f"g{len(groups) + 1}"
            options = {}
            for c in ms:
                s = df[c].dropna()
                vals = {str(v).strip().lower() for v in s.unique()}
                if vals <= _BINARY_TEXT:
                    options[c] = _item_label(c, cols[c]["label"])
                else:
                    options[c] = str(s.iloc[0]).strip() if len(s) else _item_label(c, cols[c]["label"])
                cols[c].update({"type": "multi-select-option", "group": gid, "option": options[c]})
                used.add(c)
            groups.append({"id": gid, "kind": "multi-select", "stem": stem,
                           "label": _group_label(stem, cols[ms[0]]["label"]), "columns": ms, "options": options})

    # Rating batteries: same stem, same rating type and number of points.
    for stem, members in by_stem.items():
        rated = [c for c in members if c not in used and cols[c]["type"] in ORDINAL_TYPES]
        if len(rated) < 2:
            continue
        sig = defaultdict(list)
        for c in rated:
            sig[(cols[c].get("points"), cols[c].get("scale"))].append(c)
        for (_points, scale), members2 in sig.items():
            if len(members2) < 2:
                continue
            gid = f"g{len(groups) + 1}"
            for c in members2:
                cols[c]["group"] = gid
                cols[c]["item"] = _item_label(c, cols[c]["label"])
            groups.append({"id": gid, "kind": "battery", "stem": stem,
                           "label": _group_label(stem, cols[members2[0]]["label"]), "columns": members2,
                           "scale": scale, "points": cols[members2[0]].get("points")})

    # Battery items with a mixed scale: give a shared text scale to every item
    for g in groups:
        if g["kind"] == "battery" and g.get("scale") is None:
            texts = pd.concat([df[c].dropna().astype(str) for c in g["columns"]])
            if len(texts) and pd.to_numeric(texts, errors="coerce").isna().all():
                m = scales.match_scale(texts.unique())
                if m:
                    g["scale"], g["points"] = m
                    for c in g["columns"]:
                        cols[c]["scale"], cols[c]["points"] = m

    if overrides:
        for c, t in overrides.items():
            if c in cols:
                cols[c]["type"] = t
                cols[c]["override"] = True

    kpis = _kpi_candidates(cols)
    demos = [c for c, i in cols.items() if i["type"] == "demographic"
             or (i["type"] == "single-choice" and _DEMO_HINT.search(f"{c} {i['label']}"))]
    counts = defaultdict(int)
    for i in cols.values():
        counts[i["type"]] += 1

    return {
        "file": survey.path,
        "source_format": survey.source_format,
        "n_rows": int(len(df)),
        "notes": list(survey.notes),
        "columns": list(cols.values()),
        "groups": groups,
        "kpi_candidates": kpis,
        "demographics": demos,
        "type_counts": dict(counts),
    }


def _group_label(stem: str, first_label: str) -> str:
    for sep in (" | ", " - "):
        if sep in first_label:
            return first_label.split(sep)[0].strip()
    m = re.match(r"^(.*)\[(.+)\]\s*$", first_label)
    if m:
        return m.group(1).strip()
    return stem


def _kpi_candidates(cols: dict) -> list[str]:
    scored = []
    for c, i in cols.items():
        t = i["type"]
        text = f"{c} {i['label']}".lower()
        score = 0
        if t == "nps":
            score = 100 if "recommend" in text or "nps" in text else 80
        elif t in ("csat", "likert", "rating") and re.search(r"overall|in general|overall satisfaction", text):
            score = 70
        elif t == "csat":
            score = 50
        elif t in ("likert", "rating") and re.search(r"renew|repurchase|continue|recommend|likely", text):
            score = 40
        if score:
            if i.get("group"):
                score -= 15
            scored.append((score, c))
    return [c for _, c in sorted(scored, key=lambda x: -x[0])][:5]


def column_map(profile: dict) -> dict[str, dict]:
    return {c["id"]: c for c in profile["columns"]}


def summary_text(profile: dict) -> str:
    """Short plain-text summary for Claude to read."""
    cm = profile["columns"]
    tc = profile["type_counts"]
    lines = [f"File: {profile['file']} ({profile['source_format']} export), {profile['n_rows']} rows, {len(cm)} columns."]
    parts = [f"{v} {k}" for k, v in sorted(tc.items(), key=lambda x: -x[1])]
    lines.append("Column types: " + ", ".join(parts))
    for g in profile["groups"]:
        lines.append(f"  {g['kind']} {g['id']}: '{g['label'][:70]}' -> {len(g['columns'])} items "
                     f"({', '.join(g['columns'][:6])}{'...' if len(g['columns']) > 6 else ''})")
    lines.append("KPI candidates: " + (", ".join(profile["kpi_candidates"]) or "none found"))
    lines.append("Demographic candidates: " + (", ".join(profile["demographics"]) or "none found"))
    pii = [c["id"] for c in cm if c.get("pii")]
    if pii:
        lines.append("Personal data columns (kept out of reports): " + ", ".join(pii))
    for n in profile["notes"]:
        lines.append("Note: " + n)
    return "\n".join(lines)
