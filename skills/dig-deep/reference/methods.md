# Methods: what ib.py does, and how to explain it

`scripts/ib.py` (in this skill's folder) does every calculation. This page lists what it does so you
can choose options, correct the profile, and explain results in plain words.

## Reading the file

- **Qualtrics** exports have three header rows (codes, question wording,
  ImportId); the wording row becomes the question labels.
- **SurveyMonkey** exports have two header rows (question, then sub-option);
  they are combined into one name per column.
- **Google Forms / Typeform / Microsoft Forms / plain CSV or XLSX** use the first
  row. Google Forms grids (`Question [Row]`) become rating batteries; comma-
  separated checkbox answers become multi-select questions.
- **SPSS .sav** needs `pyreadstat`; answer labels and question wording come from the file.
- An optional codebook (`--codebook`, CSV/JSON/XLSX with `column_name`,
  `question_text`, optional `type`) overrides labels and types.

## Question types

`nps`, `likert`, `csat`, `ces`, `rating` (other numeric scales such as 1–10),
`single-choice`, `binary`, `multi-select` (a group of option columns or one
delimited column), `open-text`, `numeric`, `demographic`, `datetime`,
`metadata`, `unknown`.

Correct a wrong type with `--types types.json` (`{"Q14": "demographic"}`).
Answers such as "Don't know" and "Not applicable" are left out of the base of
every percentage.

## Data quality (always run)

- **Finished**: from Qualtrics `Finished`/`Progress`, otherwise people who answered most questions.
- **Speeders**: finished in under a third of the median time. Removed from the analysis by default (`--keep-flagged` keeps them).
- **Straight-liners**: identical answers across every rating battery, with at least 8 rated items. Removed by default.
- **Missing answers** are explained as routing (asked only after a certain earlier answer), drop-off (left the survey early), an optional comment box, or genuinely left blank. Only the last counts against a question.
- **Personal data** (emails, names, phone numbers, IP addresses, locations) is never shown; emails, phone numbers, links and long ID numbers are removed from quotes.

## Metrics

| Question | Headline | Also |
|---|---|---|
| Rating (agree, satisfied…) | % in the top two boxes ("agree or strongly agree") | bottom two, net, average (secondary only), full distribution |
| NPS | % 9–10 minus % 0–6 | likely range that accounts for promoters and detractors coming from the same people |
| Single choice | % per answer | |
| Multi-select | % of people choosing each option | average number chosen, common combinations |
| Numeric | median and middle half | histogram |

Survey weights: `--weights COLUMN`. Likely ranges use the effective sample size.

## Comparing groups (`--compare`, `--pair`)

Each group is tested against everyone else: proportions with a z-test, NPS
with its own variance. p-values are adjusted for the number of tests (Holm).
A gap is **real** when the adjusted p < 0.05 and it is at least 5 points
(10 for NPS); **probably real** when p < 0.2. Groups under 30 people are shown
greyed out and are never called real. `--pair A,B` compares two groups on every
rating item; without it the highest and lowest groups are used.

## Drivers

Relative-weights analysis: splits the explained variation in the KPI across
the rating items, and stays fair when items are related to each other. Each
item also gets its performance (% rated well). The four zones:
**fix first** (important, rated low), **strengths to protect** (important,
rated high), **monitor**, **nice to have**. Items with a negative link to the
KPI are listed in the notes: check their wording (reverse-worded items).

## Mindsets (segments)

K-means on standardised rating answers; 3–6 groups, chosen by how clearly they
separate, with no group under 5%. Needs 100+ complete answer sets and 5+ rating
items. Each segment comes with its KPI, the items it rates highest and lowest,
and the demographic groups it over-represents. Name each one as a person would
recognise it ("Frustrated small teams"), never "Cluster 2".

## Open text

`texts.json` holds up to 400 answers per question (random sample if more),
with personal details removed and each person's NPS group. You read them and
write `codes.json`:

```json
{"Q7": {"themes": [{"id": "setup", "name": "Setup took too long"}, {"id": "price", "name": "Price for small teams"}],
        "codes": {"12": {"themes": ["setup"], "sentiment": "negative"},
                  "40": {"themes": ["price", "setup"], "sentiment": "negative"}},
        "examples": {"setup": ["12"]}}}
```

Use 4–8 themes that a manager would recognise, plus "Other" only if needed.
Each answer can have several themes. Sentiment is `negative`, `mixed` or
`positive`. `examples` (optional) picks the quotes to show; otherwise
mid-length coded answers are used. `ib.py themes` counts everything.

## Trends (`--wave COLUMN`)

KPI per wave with its likely range, a test of the latest change, and a check
whether the mix of respondents shifted between waves (which can move the
score on its own).
