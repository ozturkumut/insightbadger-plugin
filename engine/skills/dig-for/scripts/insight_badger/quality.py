"""Survey health: completion, speeders, straight-liners, skip logic, PII."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .metrics import encode_column

QUESTION_TYPES = {"likert", "csat", "ces", "rating", "nps", "single-choice", "binary", "multi-select-string",
                  "open-text", "numeric", "demographic"}

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\w)(\+?\d[\d\s().-]{7,}\d)(?!\w)")
_URL = re.compile(r"https?://\S+")
_LONGNUM = re.compile(r"\b\d{9,}\b")


def redact(text: str) -> str:
    """Remove emails, phone numbers, URLs and long ID numbers from a quote."""
    t = _EMAIL.sub("[email removed]", str(text))
    t = _URL.sub("[link removed]", t)
    t = _PHONE.sub("[number removed]", t)
    t = _LONGNUM.sub("[number removed]", t)
    return t


def find_completion(df: pd.DataFrame, cols: dict) -> pd.Series:
    """True for respondents who finished."""
    for c, i in cols.items():
        lc = c.lower()
        if i["type"] == "metadata" and lc in ("finished", "complete", "completed"):
            v = df[c].astype(str).str.strip().str.lower()
            return v.isin(["1", "1.0", "true", "yes", "complete", "completed"])
        if i["type"] == "metadata" and lc == "progress":
            return pd.to_numeric(df[c], errors="coerce").fillna(0) >= 100
    qcols = [c for c, i in cols.items() if i["type"] in QUESTION_TYPES]
    if not qcols:
        return pd.Series(True, index=df.index)
    answered = df[qcols].notna().mean(axis=1)
    return answered >= 0.8 * answered.quantile(0.9)


def find_duration(df: pd.DataFrame, cols: dict) -> pd.Series | None:
    for c in df.columns:
        if "duration" in c.lower() or "time taken" in c.lower():
            d = pd.to_numeric(df[c], errors="coerce")
            if d.notna().mean() > 0.5:
                return d
    starts = [c for c in df.columns if re.search(r"start ?date|start ?time|startdate", c, re.I)]
    ends = [c for c in df.columns if re.search(r"end ?date|end ?time|enddate|submitted|recorded ?date", c, re.I)]
    if starts and ends:
        s = pd.to_datetime(df[starts[0]], errors="coerce")
        e = pd.to_datetime(df[ends[0]], errors="coerce")
        d = (e - s).dt.total_seconds()
        if d.notna().mean() > 0.5 and (d > 0).mean() > 0.5:
            return d
    return None


def speeders(duration: pd.Series | None, complete: pd.Series) -> pd.Series:
    """Finished in under a third of the median time of completers."""
    if duration is None:
        return pd.Series(False, index=complete.index)
    med = duration[complete].median()
    if not med or np.isnan(med):
        return pd.Series(False, index=complete.index)
    return (duration < med / 3) & complete


def straightliners(df: pd.DataFrame, profile: dict, cols: dict) -> pd.Series:
    """Same answer to every item in every rating battery of 4+ items they answered."""
    flags, items = [], []
    for g in profile["groups"]:
        if g["kind"] != "battery" or len(g["columns"]) < 4:
            continue
        codes = pd.DataFrame({c: encode_column(df[c], cols[c]) for c in g["columns"]})
        n_ans = codes.notna().sum(axis=1)
        same = (codes.nunique(axis=1) == 1).astype(float)
        flags.append(same.where(n_ans >= 4))
        items.append(n_ans.where(n_ans >= 4, 0))
    if not flags:
        return pd.Series(False, index=df.index)
    f = pd.concat(flags, axis=1)
    n_batteries = f.notna().sum(axis=1)
    all_same = (f == 1).sum(axis=1) == n_batteries
    # Needs at least 8 rated items in total: agreeing with all of one short
    # battery is a plausible honest answer.
    total_items = pd.concat(items, axis=1).sum(axis=1)
    return all_same & (n_batteries >= 1) & (total_items >= 8)


def classify_missing(df: pd.DataFrame, profile: dict, cols: dict, complete: pd.Series) -> list[dict]:
    """Explain missing answers per question: routing (skip logic), drop-off, or not answered."""
    qcols = [c for c, i in cols.items() if i["type"] in QUESTION_TYPES]
    routers = [c for c in qcols if cols[c]["type"] in ("single-choice", "binary", "demographic")
               and df[c].nunique() <= 12]
    out = []
    order = list(df.columns)
    for c in qcols:
        miss = df[c].isna()
        rate = float(miss.mean())
        entry = {"column": c, "label": cols[c]["label"][:120], "type": cols[c]["type"],
                 "answered_pct": round((1 - rate) * 100, 1), "missing_pct": round(rate * 100, 1),
                 "reason": "none", "status": "green", "note": ""}
        if rate < 0.02:
            out.append(entry)
            continue
        if cols[c]["type"] == "open-text":
            entry.update(reason="optional", status="green",
                         note="Optional comment box; blanks are expected")
            out.append(entry)
            continue
        explained = False
        # Routing: missing for exactly the people who gave certain answers earlier
        for r in routers:
            if r == c or order.index(r) > order.index(c):
                continue
            sub = pd.DataFrame({"m": miss, "r": df[r]}).dropna(subset=["r"])
            if len(sub) < 20:
                continue
            by = sub.groupby("r")["m"].mean()
            asked = by[by < 0.1].index.tolist()
            skipped = by[by > 0.9].index.tolist()
            covered = sub["r"].isin(asked + skipped).mean()
            if asked and skipped and covered > 0.9:
                entry.update(reason="skip-logic", status="green",
                             note=f"Asked only if {r} was {', '.join(map(str, asked[:3]))}")
                explained = True
                break
        if not explained:
            # Drop-off: missing mostly among people who did not finish
            miss_complete = float(miss[complete].mean()) if complete.any() else rate
            if miss_complete < 0.05 and rate >= 0.05:
                entry.update(reason="drop-off", status="green",
                             note="Missing only for people who left the survey early")
                explained = True
        if not explained:
            unexplained = float(miss[complete].mean()) if complete.any() else rate
            entry["reason"] = "not-answered"
            entry["status"] = "green" if unexplained < 0.10 else "yellow" if unexplained < 0.25 else "red"
            entry["note"] = f"{round(unexplained * 100)}% of people who finished left it blank"
        out.append(entry)
    return out


def health(df: pd.DataFrame, profile: dict, cols: dict) -> dict:
    complete = find_completion(df, cols)
    duration = find_duration(df, cols)
    spd = speeders(duration, complete)
    sl = straightliners(df, profile, cols)
    missing = classify_missing(df, profile, cols, complete)
    return {
        "started": int(len(df)),
        "completed": int(complete.sum()),
        "completion_pct": round(float(complete.mean()) * 100, 1),
        "speeders": int(spd.sum()),
        "speeder_rule": "Finished in under a third of the median completion time" if duration is not None else
                        "No timing column, so speeders could not be checked",
        "median_minutes": round(float(duration[complete].median()) / 60, 1) if duration is not None else None,
        "straightliners": int(sl.sum()),
        "columns": missing,
        "red": sum(1 for m in missing if m["status"] == "red"),
        "yellow": sum(1 for m in missing if m["status"] == "yellow"),
        "routed": sum(1 for m in missing if m["reason"] == "skip-logic"),
        "_complete": complete,
        "_speeders": spd,
        "_straightliners": sl,
    }
