"""Open-text: export answers for Claude to code into themes, then count the codes.

Claude is far better than TF-IDF clustering at reading short survey comments,
and works in any language. The script's job is to pick the sample, strip
personal data, and do the arithmetic once Claude has assigned themes.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .quality import redact
from .stats import MIN_BASE

NOTHING = {"no", "none", "n/a", "na", "nothing", "-", ".", "nope", "no comment", "no comments", "nothing else",
           "not really", "nil", "no.", "none.", "nothing.", "x", "?"}


def export_texts(df: pd.DataFrame, columns: list[str], labels: dict[str, str], context: dict[str, pd.Series],
                 max_per_question: int = 400, seed: int = 7) -> dict:
    """Return {column: {label, n_answered, n_nothing, n_sampled, responses: [...]}}."""
    out = {}
    for c in columns:
        s = df[c].dropna().astype(str).str.strip()
        s = s[s.str.len() > 0]
        nothing = s.str.lower().str.strip(" .!").isin(NOTHING)
        real = s[~nothing & (s.str.len() > 2)]
        sample = real if len(real) <= max_per_question else real.sample(max_per_question, random_state=seed)
        responses = []
        for idx, text in sample.items():
            r = {"id": str(idx), "text": redact(text)[:600]}
            for name, ser in context.items():
                v = ser.get(idx, np.nan)
                if not pd.isna(v):
                    r[name] = str(v)
            responses.append(r)
        out[c] = {
            "label": labels.get(c, c),
            "n_answered": int(len(s)),
            "n_nothing": int(nothing.sum()),
            "n_real": int(len(real)),
            "n_sampled": int(len(sample)),
            "responses": responses,
        }
    return out


def apply_codes(texts: dict, codes: dict) -> list[dict]:
    """Turn Claude's codes into theme counts.

    ``codes`` format::

        {"Q6": {"themes": [{"id": "setup", "name": "Setup took too long"}, ...],
                "codes": {"12": {"themes": ["setup"], "sentiment": "negative"}, ...}}}
    """
    results = []
    for col, spec in codes.items():
        if col not in texts:
            continue
        resp = {r["id"]: r for r in texts[col]["responses"]}
        coded = {rid: c for rid, c in spec.get("codes", {}).items() if rid in resp}
        n = len(coded)
        themes = []
        for t in spec.get("themes", []):
            members = [rid for rid, c in coded.items() if t["id"] in c.get("themes", [])]
            sent = {"negative": 0, "mixed": 0, "positive": 0}
            for rid in members:
                s = coded[rid].get("sentiment", "mixed")
                sent[s if s in sent else "mixed"] += 1
            k = len(members)
            by_group: dict = {}
            for rid in members:
                g = resp[rid].get("nps_group") or resp[rid].get("kpi_group")
                if g:
                    by_group[g] = by_group.get(g, 0) + 1
            quotes = [m for m in members if 30 <= len(resp[m]["text"]) <= 220]
            themes.append({
                "id": t["id"],
                "name": t.get("name", t["id"]),
                "count": k,
                "pct": round(k / n * 100, 1) if n else 0.0,
                "negative_pct": round(sent["negative"] / k * 100, 1) if k else 0.0,
                "mixed_pct": round(sent["mixed"] / k * 100, 1) if k else 0.0,
                "positive_pct": round(sent["positive"] / k * 100, 1) if k else 0.0,
                "by_group": by_group,
                "example_ids": (spec.get("examples", {}).get(t["id"]) or quotes[:3]),
            })
        themes.sort(key=lambda t: -t["count"])
        results.append({
            "column": col,
            "label": texts[col]["label"],
            "n_answered": texts[col]["n_answered"],
            "n_real": texts[col]["n_real"],
            "n_coded": n,
            "sampled": texts[col]["n_sampled"] < texts[col]["n_real"],
            "small_base": n < MIN_BASE,
            "themes": themes,
            "quotes": {rid: {**resp[rid]} for t in themes for rid in t["example_ids"] if rid in resp},
        })
    return results


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
