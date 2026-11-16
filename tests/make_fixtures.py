"""Generate synthetic survey exports in each platform's real layout.

Run: python tests/make_fixtures.py   (writes tests/fixtures/*)
The data has a known structure so tests can check that the analysis finds it:
onboarding (Q2_1) and value (Q2_5) drive NPS; small companies score lower.
"""

from __future__ import annotations

import csv
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fixtures")

AGREE = ["Strongly disagree", "Disagree", "Neither agree nor disagree", "Agree", "Strongly agree"]
ITEMS = ["Onboarding was clear", "Support responds quickly", "The product is reliable",
         "Documentation is helpful", "Pricing is good value", "Integrations meet my needs"]
TAILS = ["", "Thanks.", "Overall fine otherwise.", "Hope this helps!", "That is my main point, really.",
         "Please look into it.", "We have mentioned this before.", "Keep it up.", "(sent from my phone)",
         "Would love an update on this.", "Not a big deal, but worth fixing."]
SIZES = ["1-10", "11-50", "51-250", "250+"]
COMMENTS = {
    "neg": ["Setup took far too long and we needed a call to import our first file.",
            "The price per seat is hard to justify for a team of three.",
            "Onboarding was confusing, I could not find where to connect our data.",
            "Too expensive for a small company like ours, email me at jo@example.com"],
    "pos": ["It just works, never had downtime during a launch.",
            "Support fixed our issue the same afternoon, great people.",
            "Reliable and fast, the dashboards are excellent."],
}


def generate(n: int = 420, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    size = rng.choice(SIZES, n, p=[.3, .3, .24, .16])
    size_eff = pd.Series(size).map({"1-10": -0.8, "11-50": -0.3, "51-250": 0.2, "250+": 0.5}).values
    latent = rng.normal(0, 1, n)
    item_codes = {}
    for j in range(len(ITEMS)):
        shift = size_eff if j in (0, 4) else 0
        raw = 3.2 + 0.8 * latent + shift + rng.normal(0, 0.8, n) + (0.6 if j == 2 else 0)
        item_codes[j] = np.clip(np.round(raw), 1, 5).astype(int)
    nps_raw = 6.8 + 1.2 * (item_codes[0] - 3) + 1.0 * (item_codes[4] - 3) + 0.3 * (item_codes[2] - 3) + rng.normal(0, 1.2, n)
    nps = np.clip(np.round(nps_raw), 0, 10).astype(int)
    df = pd.DataFrame({
        "StartDate": pd.date_range("2026-10-02", periods=n, freq="37min").strftime("%Y-%m-%d %H:%M:%S"),
        "EndDate": "",
        "Duration (in seconds)": rng.integers(240, 900, n),
        "Finished": rng.choice([1, 1, 1, 1, 1, 1, 1, 0], n),
        "ResponseId": [f"R_{i:05d}" for i in range(n)],
        "RecipientEmail": [f"person{i}@example.com" for i in range(n)],
        "Q1": nps,
    })
    for j in range(len(ITEMS)):
        df[f"Q2_{j + 1}"] = [AGREE[c - 1] for c in item_codes[j]]
    # Not applicable answers on documentation
    na = rng.random(n) < 0.06
    df.loc[na, "Q2_4"] = "Not applicable"
    df["Q3"] = size
    for k, opt in enumerate(["Dashboards", "Alerts", "API", "Reports"]):
        df[f"Q4_{k + 1}"] = np.where(rng.random(n) < [0.7, 0.4, 0.25, 0.5][k], "1", "")
    df["Q5"] = rng.choice(["Yes", "No"], n, p=[.55, .45])
    # Q6 asked only if Q5 == Yes (skip logic)
    df["Q6"] = np.where(df["Q5"] == "Yes", rng.choice(["Daily", "Weekly", "Monthly"], n), "")
    texts = []
    for i in range(n):
        if rng.random() < 0.35:
            texts.append("")
        else:
            base = rng.choice(COMMENTS["neg"] if nps[i] <= 8 else COMMENTS["pos"])
            texts.append(f"{base} {rng.choice(TAILS)}".strip())
    df["Q7"] = texts
    # Speeders and a straight-liner
    df.loc[:4, "Duration (in seconds)"] = 40
    for j in range(len(ITEMS)):
        df.loc[10, f"Q2_{j + 1}"] = "Agree"
    # Drop-off: unfinished people skip the last questions
    unfinished = df["Finished"] == 0
    df.loc[unfinished, ["Q7"]] = ""
    return df


def write_qualtrics(df: pd.DataFrame, path: str):
    text = {"StartDate": "Start Date", "EndDate": "End Date", "Duration (in seconds)": "Duration (in seconds)",
            "Finished": "Finished", "ResponseId": "Response ID", "RecipientEmail": "Recipient Email",
            "Q1": "How likely are you to recommend us to a friend or colleague?",
            "Q3": "How many people work at your company?",
            "Q5": "Do you use the mobile app?", "Q6": "How often do you use the mobile app?",
            "Q7": "What is the one thing we could do better?"}
    for j, it in enumerate(ITEMS):
        text[f"Q2_{j + 1}"] = f"How much do you agree with the following? - {it}"
    for k, opt in enumerate(["Dashboards", "Alerts", "API", "Reports"]):
        text[f"Q4_{k + 1}"] = f"Which features do you use? (select all) - {opt}"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(df.columns)
        w.writerow([text[c] for c in df.columns])
        w.writerow([json.dumps({"ImportId": f"QID{i}"}) for i, _ in enumerate(df.columns)])
        for row in df.itertuples(index=False):
            w.writerow(row)


def write_surveymonkey(df: pd.DataFrame, path: str):
    heads, subs, cols = [], [], []
    def add(h, s, c):
        heads.append(h); subs.append(s); cols.append(c)
    add("Respondent ID", "", "ResponseId")
    add("Start Date", "", "StartDate")
    add("How likely are you to recommend us to a friend or colleague?", "Response", "Q1")
    for j, it in enumerate(ITEMS):
        add("How much do you agree with the following?" if j == 0 else "", it, f"Q2_{j + 1}")
    add("How many people work at your company?", "Response", "Q3")
    for k, opt in enumerate(["Dashboards", "Alerts", "API", "Reports"]):
        add("Which features do you use? (select all)" if k == 0 else "", opt, f"Q4_{k + 1}")
    add("What is the one thing we could do better?", "Open-Ended Response", "Q7")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(heads)
        w.writerow(subs)
        opts = ["Dashboards", "Alerts", "API", "Reports"]
        for _, r in df.iterrows():
            row = []
            for c in cols:
                if c.startswith("Q4_"):
                    row.append(opts[int(c[-1]) - 1] if r[c] == "1" else "")
                else:
                    row.append(r[c])
            w.writerow(row)


def write_googleforms(df: pd.DataFrame, path: str):
    opts = ["Dashboards", "Alerts", "API", "Reports"]
    g = pd.DataFrame({
        "Timestamp": pd.to_datetime(df["StartDate"]).dt.strftime("%d/%m/%Y %H:%M:%S"),
        "How likely are you to recommend us to a friend or colleague?": df["Q1"],
    })
    for j, it in enumerate(ITEMS):
        g[f"How much do you agree with the following? [{it}]"] = df[f"Q2_{j + 1}"]
    g["How many people work at your company?"] = df["Q3"]
    g["Which features do you use?"] = [", ".join(o for k, o in enumerate(opts) if df.loc[i, f"Q4_{k + 1}"] == "1")
                                       for i in df.index]
    g["What is the one thing we could do better?"] = df["Q7"]
    g.to_csv(path, index=False)


def main():
    os.makedirs(OUT, exist_ok=True)
    df = generate()
    write_qualtrics(df, os.path.join(OUT, "qualtrics.csv"))
    write_surveymonkey(df, os.path.join(OUT, "surveymonkey.csv"))
    write_googleforms(df, os.path.join(OUT, "googleforms.csv"))
    print("wrote fixtures to", OUT)


if __name__ == "__main__":
    main()
