"""Read survey exports from the common platforms into one clean table.

Handles:
* Qualtrics CSV with its three header rows (codes, question text, ImportId JSON)
* SurveyMonkey CSV/XLSX with two header rows (question, then sub-option)
* Google Forms, Typeform, Microsoft Forms and plain CSV/XLSX with one header row
* SPSS .sav (value labels applied, variable labels used as question text)
"""

from __future__ import annotations

import csv
import io
import os
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Survey:
    df: pd.DataFrame
    labels: dict[str, str]                 # column -> full question text
    source_format: str                     # qualtrics | surveymonkey | spss | plain
    path: str = ""
    notes: list[str] = field(default_factory=list)


_UNNAMED = re.compile(r"^Unnamed: \d+(_level_\d+)?$")


def _read_csv_raw(path: str) -> pd.DataFrame:
    """Read every cell as text, trying common encodings and delimiters."""
    raw = None
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            with open(path, encoding=enc) as fh:
                raw = fh.read()
            if enc == "utf-16" and "\x00" in raw:
                continue
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if raw is None:
        raise ValueError(f"Could not decode {path}")
    sample = raw[:20000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        sep = dialect.delimiter
    except csv.Error:
        sep = ","
    return pd.read_csv(io.StringIO(raw), sep=sep, dtype=str, keep_default_na=False, header=None)


def _read_raw(path: str, sheet=None) -> tuple[pd.DataFrame, str | None]:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".csv", ".txt", ".tsv"):
        return _read_csv_raw(path), None
    if ext in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(path, sheet_name=sheet or 0, dtype=str, header=None)
        return df.fillna(""), None
    if ext == ".sav":
        return None, "spss"
    raise ValueError(f"Unsupported file type '{ext}'. Use CSV, XLSX or SPSS .sav.")


def _load_spss(path: str) -> Survey:
    try:
        import pyreadstat  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ValueError("Reading .sav files needs the pyreadstat package: pip install pyreadstat") from exc
    df, meta = pyreadstat.read_sav(path, apply_value_formats=True)
    labels = {c: (meta.column_names_to_labels.get(c) or c) for c in df.columns}
    return Survey(df=df, labels=labels, source_format="spss", path=path,
                  notes=["Read SPSS file: answer labels and question wording taken from the file."])


def _dedupe(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for n in names:
        n = str(n).strip() or "column"
        if n in seen:
            seen[n] += 1
            n = f"{n}.{seen[n]}"
        else:
            seen[n] = 0
        out.append(n)
    return out


def _is_qualtrics(raw: pd.DataFrame) -> bool:
    if len(raw) < 3:
        return False
    row2 = " ".join(raw.iloc[2].astype(str).tolist()[:5])
    if '"ImportId"' in row2 or "{'ImportId'" in row2 or "ImportId" in row2:
        return True
    head = [str(x).strip().lower() for x in raw.iloc[0].tolist()]
    sub = [str(x).strip().lower() for x in raw.iloc[1].tolist()]
    pairs = dict(zip(head, sub))
    return pairs.get("responseid") == "response id" or pairs.get("startdate") == "start date"


_SM_SUB = {"response", "open-ended response", "other (please specify)", ""}


def _is_surveymonkey(raw: pd.DataFrame) -> bool:
    if len(raw) < 3:
        return False
    head = raw.iloc[0].astype(str).tolist()
    sub = [str(x).strip().lower() for x in raw.iloc[1].tolist()]
    blank_heads = sum(1 for h in head if h.strip() == "")
    has_sm_ids = any(h.strip().lower() in ("respondent id", "collector id") for h in head)
    sm_subs = sum(1 for s in sub if s in ("response", "open-ended response"))
    return (has_sm_ids and sm_subs > 0) or (blank_heads >= max(2, len(head) * 0.2) and sm_subs > 0)


def _clean_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace(r"^\s*$", np.nan, regex=True)
    for c in df.columns:
        if df[c].dtype == object:
            s = df[c].astype("string").str.strip()
            df[c] = s.astype(object).where(s.notna(), np.nan)
            # Turn columns that are entirely numeric text into numbers
            num = pd.to_numeric(df[c], errors="coerce")
            nonnull = df[c].notna().sum()
            if nonnull and num.notna().sum() == nonnull:
                df[c] = num
    return df.dropna(axis=1, how="all")


def load_survey(path: str, sheet=None) -> Survey:
    raw, special = _read_raw(path, sheet)
    if special == "spss":
        sv = _load_spss(path)
        sv.df = _clean_values(sv.df.astype(object))
        return sv

    notes: list[str] = []
    if _is_qualtrics(raw):
        cols = _dedupe(raw.iloc[0].tolist())
        texts = [str(x).strip() for x in raw.iloc[1].tolist()]
        skip = 3 if len(raw) > 2 and "ImportId" in " ".join(raw.iloc[2].astype(str).tolist()[:5]) else 2
        df = raw.iloc[skip:].reset_index(drop=True)
        df.columns = cols
        labels = {c: (t or c) for c, t in zip(cols, texts)}
        fmt = "qualtrics"
        notes.append("Qualtrics export: used the question-wording row as labels and skipped the ImportId row.")
    elif _is_surveymonkey(raw):
        heads = raw.iloc[0].astype(str).tolist()
        subs = [str(x).strip() for x in raw.iloc[1].tolist()]
        filled, current = [], ""
        for h in heads:
            current = h.strip() or current
            filled.append(current)
        names, labels_list = [], []
        for q, s in zip(filled, subs):
            if s.lower() in _SM_SUB:
                name = q if s.lower() in ("response", "") else f"{q} | {s}"
            else:
                name = f"{q} | {s}"
            names.append(name)
            labels_list.append(name)
        cols = _dedupe(names)
        df = raw.iloc[2:].reset_index(drop=True)
        df.columns = cols
        labels = dict(zip(cols, labels_list))
        fmt = "surveymonkey"
        notes.append("SurveyMonkey export: combined the two header rows into one name per column.")
    else:
        cols = _dedupe(raw.iloc[0].tolist())
        df = raw.iloc[1:].reset_index(drop=True)
        df.columns = cols
        labels = {c: c for c in cols}
        fmt = "plain"

    df = _clean_values(df)
    labels = {c: labels.get(c, c) for c in df.columns}
    return Survey(df=df, labels=labels, source_format=fmt, path=path, notes=notes)


def load_codebook(path: str) -> dict[str, dict]:
    """Read an optional codebook: column -> {question_text, type, section, options}."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        data = pd.read_json(path)
        if isinstance(data, pd.DataFrame):
            cb = data
        else:  # pragma: no cover
            cb = pd.DataFrame(data)
    elif ext in (".xlsx", ".xls"):
        cb = pd.read_excel(path, sheet_name=0)
    else:
        cb = pd.read_csv(path)
    cb.columns = [str(c).strip().lower() for c in cb.columns]
    key = next((k for k in ("column_name", "column", "variable", "name") if k in cb.columns), None)
    if key is None:
        raise ValueError("Codebook needs a 'column_name' column.")
    out = {}
    for _, row in cb.iterrows():
        col = str(row[key]).strip()
        entry = {}
        for src, dst in (("question_text", "question_text"), ("label", "question_text"),
                         ("question_type_hint", "type"), ("type", "type"), ("section", "section"),
                         ("response_options", "options")):
            if src in cb.columns and pd.notna(row.get(src)) and dst not in entry:
                entry[dst] = str(row[src]).strip()
        out[col] = entry
    return out
