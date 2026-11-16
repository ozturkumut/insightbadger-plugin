"""Generate examples/sample-survey-qualtrics.csv: a realistic customer survey for trying Insight Badger.

Qualtrics layout (three header rows). 600 people across two waves. Built-in
patterns a good analysis should find (see examples/README.md):

1. Setup and first-month value drive NPS most, and both are rated poorly.
2. Small companies (1-10, 11-50 employees) are much less likely to recommend.
3. NPS fell between 2026 Q2 and 2026 Q3, partly because Q3 has more small
   companies and partly because new customers found setup harder.
4. A "stalled starter" group: new, small customers low on setup and value.
5. Comments: setup and price complaints; reliability and support praise.
6. Q7 is only asked of people who contacted support (skip logic).
7. Twelve speeders, a few unfinished responses, emails in the data and in
   two comments (should be removed), "Not applicable" answers on integrations.

Run: python3 examples/make_sample_survey.py
"""

from __future__ import annotations

import csv
import json
import os

import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample-survey-qualtrics.csv")
rng = np.random.default_rng(2026)
N = 600

AGREE = ["Strongly disagree", "Disagree", "Neither agree nor disagree", "Agree", "Strongly agree"]
SAT = ["Very dissatisfied", "Dissatisfied", "Neither satisfied nor dissatisfied", "Satisfied", "Very satisfied"]
SIZES = ["1-10 employees", "11-50 employees", "51-250 employees", "251-1,000 employees", "1,000+ employees"]
SIZE_EFFECT = {SIZES[0]: -0.75, SIZES[1]: -0.35, SIZES[2]: 0.05, SIZES[3]: 0.3, SIZES[4]: 0.4}
PLANS = {SIZES[0]: ["Starter", "Team"], SIZES[1]: ["Starter", "Team"], SIZES[2]: ["Team", "Business"],
         SIZES[3]: ["Business", "Enterprise"], SIZES[4]: ["Enterprise"]}
TENURE = ["Less than 6 months", "6-12 months", "1-2 years", "More than 2 years"]
ROLES = ["Founder or owner", "Manager", "Analyst", "Engineer", "Other"]
REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America"]
ITEMS = [
    "The setup process was straightforward",
    "I got real value from the product within my first month",
    "The product is reliable",
    "Support resolves my issues quickly",
    "The product is good value for money",
    "It integrates well with the other tools we use",
    "The reports give me the insights I need",
]
FEATURES = ["Dashboards", "Scheduled reports", "Alerts", "API", "Mobile app", "Integrations"]

# ── comment building blocks ──────────────────────────────────────────────────
NEG = {
    "setup": [
        "Setup took us far longer than expected", "Getting started was confusing",
        "We needed two calls with support just to import our first data",
        "Onboarding assumes you have a technical person on the team",
        "It took weeks before we saw anything useful", "Connecting our data sources was painful",
        "The first-week setup checklist skips important steps",
    ],
    "price": [
        "The per-seat price is hard to justify for a small team", "It is too expensive for a company our size",
        "We pay for seats we barely use", "Pricing jumped at renewal without much warning",
        "A cheaper plan for small teams would make this an easy yes",
    ],
    "integrations": [
        "It does not connect to our CRM", "The integrations break whenever the other tool updates",
        "We still export CSVs by hand because the integration is missing a field",
    ],
    "reports": [
        "The reports are too rigid", "I cannot customise the dashboards the way I need",
        "Scheduled reports arrive with the wrong date range",
    ],
}
POS = {
    "reliable": [
        "It just works and has never gone down on us", "Rock solid reliability during our busiest weeks",
        "We trust the numbers and it is always up",
    ],
    "support": [
        "Support fixed our issue the same afternoon", "The support team is friendly and knows the product",
        "Every support chat ended with a real answer",
    ],
    "reports": ["The dashboards save me hours every week", "Scheduled reports keep our leadership informed"],
}
DETAIL = ["", "", "", " for the whole team", " last quarter", " compared with the tool we used before",
          " especially at month end", " since we started"]
CLOSER = ["", "", "", "", " Otherwise happy.", " Please fix this.", " Thanks for asking.",
          " That is my main point.", " Would love an update on this.", " Keep it up."]
FOREIGN = ["La configuración inicial fue muy complicada para nosotros.", "Der Support antwortet schnell und hilfsbereit.",
           "Le prix est trop élevé pour une petite équipe."]


def comment(kind: str, theme: str) -> str:
    base = rng.choice((NEG if kind == "neg" else POS)[theme])
    return f"{base}{rng.choice(DETAIL)}.{rng.choice(CLOSER)}".replace("..", ".").strip()


def main():
    wave = np.where(np.arange(N) < 280, "2026 Q2", "2026 Q3")
    size = np.array([rng.choice(SIZES, p=[.18, .24, .26, .18, .14] if w == "2026 Q2" else [.27, .28, .22, .13, .10])
                     for w in wave])
    tenure = rng.choice(TENURE, N, p=[.22, .2, .28, .3])
    new = np.isin(tenure, TENURE[:2])
    latent = rng.normal(0, 1, N) + np.vectorize(SIZE_EFFECT.get)(size)
    noise = lambda: rng.normal(0, 0.75, N)
    q3_new = (wave == "2026 Q3") & new          # setup got harder for new customers in Q3

    raw = {
        1: 3.0 + 0.7 * latent - 0.6 * new - 0.5 * q3_new + noise(),           # setup
        2: 3.0 + 0.7 * latent - 0.5 * new - 0.3 * q3_new + noise(),           # first-month value
        3: 4.0 + 0.4 * latent + noise(),                                      # reliability
        4: 3.6 + 0.5 * latent + noise(),                                      # support
        5: 3.0 + 0.6 * latent + 0.5 * np.vectorize(SIZE_EFFECT.get)(size) + noise(),  # value for money
        6: 3.2 + 0.5 * latent + noise(),                                      # integrations
        7: 3.3 + 0.5 * latent + noise(),                                      # reports
    }
    codes = {k: np.clip(np.round(v), 1, 5).astype(int) for k, v in raw.items()}
    nps = np.clip(np.round(7.8 + 0.95 * (codes[1] - 3) + 0.8 * (codes[2] - 3) + 0.7 * (codes[5] - 3)
                           + 0.35 * (codes[3] - 3) + 0.25 * (codes[4] - 3) + rng.normal(0, 1.1, N)), 0, 10).astype(int)
    csat = np.clip(np.round(3.3 + 0.35 * (nps - 7) + rng.normal(0, 0.6, N)), 1, 5).astype(int)

    start = pd.Timestamp("2026-05-04 08:00")
    starts = [start + pd.Timedelta(minutes=int(m)) for m in np.sort(rng.integers(0, 60 * 24 * 20, N))]
    q3_shift = pd.Timedelta(days=91)
    starts = [s + (q3_shift if w == "2026 Q3" else pd.Timedelta(0)) for s, w in zip(starts, wave)]
    duration = rng.gamma(6, 70, N).astype(int) + 120
    speeders = rng.choice(N, 12, replace=False)
    duration[speeders] = rng.integers(25, 70, 12)
    finished = np.ones(N, dtype=int)
    unfinished = rng.choice(np.setdiff1d(np.arange(N), speeders), 34, replace=False)
    finished[unfinished] = 0

    rows = []
    for i in range(N):
        r = {
            "StartDate": starts[i].strftime("%Y-%m-%d %H:%M:%S"),
            "EndDate": (starts[i] + pd.Timedelta(seconds=int(duration[i]))).strftime("%Y-%m-%d %H:%M:%S"),
            "Status": "IP Address",
            "IPAddress": f"203.0.113.{rng.integers(1, 255)}",
            "Progress": 100 if finished[i] else int(rng.integers(35, 80)),
            "Duration (in seconds)": int(duration[i]),
            "Finished": "True" if finished[i] else "False",
            "RecordedDate": (starts[i] + pd.Timedelta(seconds=int(duration[i]))).strftime("%Y-%m-%d %H:%M:%S"),
            "ResponseId": f"R_{rng.integers(16**10, 16**11):x}",
            "RecipientEmail": f"customer{i:04d}@example.com",
            "Wave": wave[i],
            "Q1": int(nps[i]),
            "Q2": SAT[csat[i] - 1],
        }
        for k in range(1, 8):
            r[f"Q3_{k}"] = AGREE[codes[k][i] - 1]
        if rng.random() < 0.09:
            r["Q3_6"] = "Not applicable"
        used = [f for f, p in zip(FEATURES, [.82, .45, .38, .2, .3, .35]) if rng.random() < p]
        for k, f in enumerate(FEATURES, 1):
            r[f"Q4_{k}"] = "1" if f in used else ""
        contacted = rng.random() < 0.42
        r["Q5"] = "Yes" if contacted else "No"
        r["Q6"] = SAT[int(np.clip(codes[4][i] + rng.integers(-1, 2), 1, 5)) - 1] if contacted else ""
        # Comments
        if rng.random() < 0.03:
            better = rng.choice(FOREIGN)
        elif rng.random() < 0.25:
            better = ""
        elif rng.random() < 0.06:
            better = rng.choice(["N/A", "Nothing", "no", "Nothing really."])
        elif nps[i] <= 8:
            weights = np.array([1.6 if codes[1][i] <= 2 or codes[2][i] <= 2 else 0.5,
                                1.5 if codes[5][i] <= 2 else 0.4,
                                1.0 if codes[6][i] <= 2 else 0.2,
                                0.8 if codes[7][i] <= 2 else 0.2])
            theme = rng.choice(["setup", "price", "integrations", "reports"], p=weights / weights.sum())
            better = comment("neg", theme)
        else:
            better = comment("neg", rng.choice(["reports", "integrations"])) if rng.random() < 0.4 else ""
        if i in (17, 233):
            better += " Feel free to email me at alex.morgan@example.org or call +1 415 555 0134."
        likes = ""
        if rng.random() < 0.55:
            theme = rng.choice(["reliable", "support", "reports"], p=[.5, .3, .2])
            likes = comment("pos", theme) if nps[i] >= 7 or rng.random() < 0.4 else rng.choice(
                ["Not much right now.", "The idea is good but we have not got far with it."])
        r["Q7"], r["Q8"] = better, likes
        r["Q9"] = size[i]
        r["Q10"] = rng.choice(PLANS[size[i]])
        r["Q11"] = tenure[i]
        r["Q12"] = rng.choice(ROLES, p=[.3, .3, .2, .15, .05] if size[i] in SIZES[:2] else [.05, .4, .27, .2, .08])
        r["Q13"] = rng.choice(REGIONS, p=[.42, .33, .17, .08])
        if not finished[i]:  # people who left early never reached the last page
            for c in ("Q7", "Q8", "Q9", "Q10", "Q11", "Q12", "Q13"):
                r[c] = ""
        rows.append(r)

    df = pd.DataFrame(rows)
    text = {
        "StartDate": "Start Date", "EndDate": "End Date", "Status": "Response Type", "IPAddress": "IP Address",
        "Progress": "Progress", "Duration (in seconds)": "Duration (in seconds)", "Finished": "Finished",
        "RecordedDate": "Recorded Date", "ResponseId": "Response ID", "RecipientEmail": "Recipient Email",
        "Wave": "Wave",
        "Q1": "How likely are you to recommend us to a friend or colleague?",
        "Q2": "Overall, how satisfied are you with the product?",
        "Q5": "Have you contacted our support team in the last 3 months?",
        "Q6": "How satisfied were you with the support you received?",
        "Q7": "What is the one thing we could do better?",
        "Q8": "What do you like most about the product?",
        "Q9": "How many people work at your company?",
        "Q10": "Which plan are you on?",
        "Q11": "How long have you been a customer?",
        "Q12": "Which best describes your role?",
        "Q13": "Where is your company based?",
    }
    for k, it in enumerate(ITEMS, 1):
        text[f"Q3_{k}"] = f"How much do you agree with the following statements? - {it}"
    for k, f in enumerate(FEATURES, 1):
        text[f"Q4_{k}"] = f"Which features do you use? Select all that apply. - {f}"
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(df.columns)
        w.writerow([text[c] for c in df.columns])
        w.writerow([json.dumps({"ImportId": c if not c.startswith("Q") else f"QID{c[1:]}"}) for c in df.columns])
        w.writerows(df.itertuples(index=False))
    print(f"Wrote {OUT} ({len(df)} responses, {len(df.columns)} columns)")


if __name__ == "__main__":
    main()
