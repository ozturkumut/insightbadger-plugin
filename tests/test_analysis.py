"""Metrics, statistics, quality checks and the full analysis run."""

import math

import numpy as np
import pandas as pd

from insight_badger import metrics as m
from insight_badger import stats as st
from insight_badger.quality import redact, speeders


def test_nps_interval_matches_bootstrap():
    # v0.2 ignored the covariance of promoters and detractors: interval ~20% too narrow
    rng = np.random.default_rng(1)
    x = pd.Series(rng.choice(range(11), 400, p=[.03] * 7 + [.13, .13, .25, .28]))
    s = m.nps_summary(x)
    half = (s["ci"][1] - s["ci"][0]) / 2
    boots = [m.nps_summary(x.sample(len(x), replace=True, random_state=i))["nps"] for i in range(1500)]
    b_half = (np.percentile(boots, 97.5) - np.percentile(boots, 2.5)) / 2
    assert abs(half - b_half) / b_half < 0.1


def test_nps_basics_and_weights():
    s = m.nps_summary(pd.Series([10, 9, 8, 7, 6, 0]))
    assert s["nps"] == 0.0 and s["promoters"] == round(2 / 6 * 100, 1)
    w = pd.Series([3, 1, 1, 1, 1, 1], dtype=float)
    sw = m.nps_summary(pd.Series([10, 9, 8, 7, 6, 0]), w)
    assert sw["nps"] > 0 and sw["n_eff"] < 6


def test_rating_summary_seven_point_uses_top_two_of_seven():
    info = {"type": "likert", "points": 7}
    s = m.rating_summary(pd.Series([7, 6, 5, 4, 1, 2.0]), info)
    assert s["top_box"] == round(2 / 6 * 100, 1)
    assert s["bottom_box"] == round(2 / 6 * 100, 1)


def test_multiselect_blank_means_not_selected():
    df = pd.DataFrame({"Q5_1": [1, np.nan, 1, np.nan], "Q5_2": [np.nan, np.nan, 1, 1]})
    g = {"columns": ["Q5_1", "Q5_2"], "options": {"Q5_1": "A", "Q5_2": "B"}}
    mat = m.multiselect_matrix(df, g)
    s = m.multiselect_summary(mat)
    assert s["n"] == 3  # the respondent who chose nothing is outside the base
    combos = {c["combo"]: c["pct"] for c in s["top_combinations"]}
    assert set(combos) == {"A", "A + B", "B"}


def test_speeder_rule_does_not_flag_honest_sample():
    rng = np.random.default_rng(2)
    d = pd.Series(rng.normal(600, 60, 1000))
    assert speeders(d, pd.Series(True, index=d.index)).sum() == 0
    d.iloc[:7] = 90
    assert speeders(d, pd.Series(True, index=d.index)).sum() == 7


def test_holm_and_verdicts():
    adj = st.holm([0.01, 0.04, 0.03, math.nan])
    assert adj[0] == 0.03 and math.isnan(adj[3])
    assert adj[2] == 0.06 and adj[1] == 0.06
    assert st.verdict(0.001, 12, 5, 20) == "small-base"
    assert st.verdict(0.001, 12, 5, 200) == "real"
    assert st.verdict(0.3, 12, 5, 200) == "chance"


def test_redaction():
    out = redact("Call me on +44 7700 900123 or mail jo.smith@example.co.uk, see https://x.y/z")
    assert "@" not in out and "7700" not in out and "https" not in out


def test_full_run_finds_planted_structure(q_results):
    r, texts = q_results
    assert r["kpi"]["column"] == "Q1" and r["kpi"]["kind"] == "nps"
    # Text Likert items work in drivers (v0.2 crashed here)
    d = r["drivers"]
    assert d["available"]
    top2 = {x["column"] for x in d["drivers"][:2]}
    assert top2 == {"Q2_1", "Q2_5"}
    assert all(x["zone"] == "fix" for x in d["drivers"][:2])
    # Small companies are lowest and the gap is real; groups in natural order
    comp = r["comparisons"][0]
    assert [g["value"] for g in comp["groups"]] == ["1-10", "11-50", "51-250", "250+"]
    assert comp["extremes"]["low"] == "1-10" and comp["extremes"]["verdict"] == "real"
    assert {i["column"] for i in comp["pair"]["items"] if i["verdict"] == "real"} >= {"Q2_1", "Q2_5"}
    # Segments run on text Likert (v0.2 crashed here)
    assert r["segments"]["available"]
    # Quality: speeders removed, skip logic recognised, multi-select not flagged as missing
    assert r["meta"]["excluded"]["speeders"] == 5
    notes = {c["column"]: c for c in r["health"]["columns"]}
    assert notes["Q6"]["reason"] == "skip-logic" and "Q5" in notes["Q6"]["note"]
    assert "Q4_1" not in notes
    # Personal data never reaches the report or the coding file
    assert not any(q["id"] == "RecipientEmail" for q in r["questions"])
    assert not any("@" in x["text"] for x in texts["Q7"]["responses"])
    # Battery reliability is computed on text answers (v0.2 returned None)
    assert r["batteries"][0]["alpha"] > 0.6


def test_filters_and_dig_for_pair(qualtrics, q_profile):
    from insight_badger.analyze import run
    r, _ = run(qualtrics, q_profile, compare=["Q3"], pair=["1-10", "250+"], filters=["Q5=Yes"], mode="for",
               do_segments=False)
    assert r["meta"]["filters"] == ["Q5 = Yes"]
    assert r["meta"]["n_analysed"] < 300
    assert r["comparisons"][0]["pair"]["a"] == "1-10"
    assert r["segments"]["available"] is False


def test_themes_counting(q_results):
    from code_texts import code
    from insight_badger.text import apply_codes
    _, texts = q_results
    out = apply_codes(texts, code(texts))[0]
    names = [t["name"] for t in out["themes"]]
    assert set(names[:2]) == {"Price for small teams", "Setup and onboarding"}
    assert out["themes"][0]["negative_pct"] == 100.0
    assert all(rid in out["quotes"] for t in out["themes"] for rid in t["example_ids"])
