"""Question-type detection, including every misread found in the v0.2 review."""

import os

import numpy as np
import pandas as pd
import pytest

from insight_badger import scales
from insight_badger.detect import build_profile, detect_column
from insight_badger.loading import load_survey

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
rng = np.random.default_rng(0)


def t(series, name="Q10", label=None):
    return detect_column(pd.Series(series), name, label or name)["type"]


def test_integer_columns_are_not_dates():
    # v0.2 read every whole-number column as a date (pandas treats 7 as a timestamp)
    assert t(rng.integers(0, 11, 300), "Q1", "How likely are you to recommend us?") == "nps"
    assert t(rng.integers(1, 6, 300)) == "likert"
    assert t(rng.integers(1, 8, 300)) == "likert"


def test_seven_point_and_ten_point_scales_are_not_nps():
    info = detect_column(pd.Series(rng.integers(1, 8, 300)), "Q10_1", "Q10_1")
    assert info["type"] == "likert" and info["points"] == 7
    assert t(rng.integers(1, 11, 300), "rate_quality") == "rating"


def test_likely_in_name_does_not_force_nps_on_five_point_scale():
    assert t(rng.integers(1, 6, 300), "likely_to_renew") == "likert"


def test_real_likert_wording_and_not_applicable():
    vals = rng.choice(["Strongly disagree", "Disagree", "Neither agree nor disagree", "Agree", "Strongly agree",
                       "Not applicable", "Don't know"], 300)
    info = detect_column(pd.Series(vals), "Q11", "Q11")
    assert info["type"] == "likert" and info["points"] == 5
    codes = scales.encode(pd.Series(vals), info["scale"])
    assert codes.max() == 5 and codes.min() == 1
    assert codes.isna().sum() == sum(v in ("Not applicable", "Don't know") for v in vals)


def test_seven_point_text_scale_keeps_seven_positions():
    vals = ["Strongly disagree", "Disagree", "Somewhat disagree", "Neither agree nor disagree",
            "Somewhat agree", "Agree", "Strongly agree"] * 20
    info = detect_column(pd.Series(vals), "Q12", "Q12")
    assert info["points"] == 7
    codes = scales.encode(pd.Series(vals), info["scale"])
    assert sorted(codes.unique()) == [1, 2, 3, 4, 5, 6, 7]


def test_numbered_text_nps():
    vals = rng.choice(["0 - Not at all likely"] + [str(i) for i in range(1, 10)] + ["10 - Extremely likely"], 300)
    assert t(vals, "Q2", "How likely are you to recommend us?") == "nps"


def test_status_and_language_questions_are_not_metadata():
    assert t(rng.choice(["Employed", "Student", "Retired"], 200), "Employment status") != "metadata"
    assert t(rng.choice(["English", "German"], 200), "Preferred language") != "metadata"


def test_google_forms_comma_multiselect_vs_comments():
    ms = rng.choice(["Speed, Reliability", "Price", "Speed", "Reliability, Price, Support"], 200)
    assert t(ms, "Which features matter?") == "multi-select-string"
    comments = [f"The setup was slow, and support took {i} days, which hurt us a lot" for i in range(200)]
    assert t(comments, "Any other comments?") == "open-text"


def test_qualtrics_three_header_rows(q_profile, qualtrics):
    assert qualtrics.source_format == "qualtrics"
    assert len(qualtrics.df) == 420
    assert qualtrics.labels["Q1"].startswith("How likely")
    types = {c["id"]: c["type"] for c in q_profile["columns"]}
    assert types["Q1"] == "nps"
    assert all(types[f"Q2_{i}"] == "likert" for i in range(1, 7))
    assert types["Q3"] == "demographic"
    assert types["Q7"] == "open-text"
    kinds = {g["kind"]: g for g in q_profile["groups"]}
    assert kinds["multi-select"]["columns"] == ["Q4_1", "Q4_2", "Q4_3", "Q4_4"]
    assert kinds["battery"]["columns"] == [f"Q2_{i}" for i in range(1, 7)]
    assert q_profile["kpi_candidates"][0] == "Q1"
    assert [c["id"] for c in q_profile["columns"] if c["pii"]] == ["RecipientEmail"]


@pytest.mark.parametrize("name", ["surveymonkey", "googleforms"])
def test_other_platforms(name):
    sv = load_survey(os.path.join(FIX, f"{name}.csv"))
    prof = build_profile(sv)
    counts = prof["type_counts"]
    assert counts.get("likert") == 6
    assert counts.get("nps") == 1
    assert len(prof["demographics"]) == 1
    assert any(g["kind"] == "battery" and len(g["columns"]) == 6 for g in prof["groups"])
    if name == "surveymonkey":
        assert sv.source_format == "surveymonkey"
        assert any(g["kind"] == "multi-select" and len(g["columns"]) == 4 for g in prof["groups"])
    else:
        assert counts.get("multi-select-string") == 1
    assert counts.get("open-text") == 1


def test_codebook_overrides_labels(tmp_path, qualtrics):
    cb = tmp_path / "cb.csv"
    cb.write_text("column_name,question_text\nQ3,Company size band\n")
    from insight_badger.loading import load_codebook
    prof = build_profile(qualtrics, load_codebook(str(cb)))
    assert next(c for c in prof["columns"] if c["id"] == "Q3")["label"] == "Company size band"


def test_thousands_separator_is_not_a_multiselect():
    vals = rng.choice(["1-10 employees", "11-50 employees", "251-1,000 employees", "1,000+ employees"], 300)
    assert t(vals, "Q9", "How many people work at your company?") == "demographic"


def test_location_question_is_demographic():
    assert t(rng.choice(["Europe", "North America", "Asia Pacific"], 300), "Q13", "Where is your company based?") == "demographic"


def test_qualtrics_status_column_is_metadata():
    assert t(rng.choice(["IP Address", "Survey Preview"], 300), "Status", "Response Type") == "metadata"
