<p align="center"><img src="assets/logo.png" width="120" alt="Insight Badger logo"></p>

# Insight Badger

Survey insights for people who don't analyse surveys for a living. Drop a survey export from Qualtrics, SurveyMonkey,
Google Forms, Typeform, Microsoft Forms, SPSS or any CSV/XLSX, and get a plain-language, storytelling report: what
drives your score, who is unhappy, what people say in their own words, and what to do next.

No spreadsheet formulas, no SPSS, no coding.

## Skills

### `/dig-deep`: explore a survey

Hand over a file and Insight Badger works out the rest: the questionnaire structure, the KPI, what drives it, which
groups differ, the customer mindsets in your data and the themes in open comments.

Try: *"dig deep into survey.csv"*, *"what's interesting in these responses?"*

### `/dig-for`: answer one question

You have a question; Insight Badger asks one or two clarifying questions, then delivers a focused brief that leads
with the answer.

Try: *"what's driving our NPS?"*, *"why are small customers less happy?"*, *"compare enterprise vs SMB on onboarding"*,
*"what do detractors complain about?"*

## The report

Every run produces a single self-contained HTML file that works offline:

- **Header** with the headline finding and the key figures (score, likely range, change since last wave, completion).
- **Overview / Answer** tab: the answer in two or three sentences, a story map of the chapters, recommended actions
  and the next questions to dig into.
- **Chapter tabs**: drivers (importance vs performance with "fix first" and "protect" zones), group gaps with likely
  ranges, two-group item comparisons, customer mindsets as personas, open-text themes with quotes.
- **Reference tabs**: every question as a card, data quality and plain-language methods.
- **Colour means something**: brand teal for strengths, clay for problems, ochre for "watch", slate for comparisons.

### PDF, branded or unbranded

The **Download PDF** button at the top right offers two versions:

- **Insight Badger branded**: logo on the cover, credit in the footer.
- **Unbranded**: no logo or product name, ready to send as your own.

Either version prints with a cover page, one chapter per page and page numbers. You can also ask for a PDF in chat
("…and give me an unbranded PDF"); the skill saves it next to the report using Chrome, Edge or WeasyPrint.

### Your own brand

Put a `.insight-badger.json` file in your project folder (or any parent folder):

```json
{
  "brand": "custom",
  "name": "Acme Research",
  "logo": "brand/acme-logo.png",
  "primary": "#1F5FAD",
  "paper": "Letter",
  "confidential": true
}
```

`brand` can be `insight-badger` (default), `none` or `custom`. With `custom`, the report uses your name, logo and
colour, and the footer reads "Prepared by Acme Research".

## What it handles

- **Exports from every major platform**: Qualtrics' three header rows, SurveyMonkey's two header rows, Google Forms
  grids and checkbox answers, XLSX, SPSS `.sav` (with `pyreadstat`), and an optional codebook.
- **Question types**: NPS, agree/satisfied/frequency/quality/likelihood scales (5- or 7-point, text or numbers),
  CSAT, CES, other numeric ratings, single choice, multi-select, open text, numbers, demographics.
- **"Don't know" and "Not applicable"** are left out of percentages instead of being counted as answers.
- **Data quality**: completion, speeders (under a third of the median time), straight-liners, questions skipped by
  survey routing, drop-off, all reported in plain words.
- **Sound statistics**: correct NPS confidence ranges, survey weights, group gaps tested and adjusted for the number
  of comparisons, groups under 30 people flagged and never called significant.
- **Drivers** with relative-weights analysis; **mindsets** with k-means on rating answers; **open text** themed by
  Claude in any language, with counts and sentiment computed by the engine.
- **Privacy**: names, emails, phone numbers and IP addresses never appear in the report, and are removed from quotes.

## Requirements

Python 3.9+ with `pandas`, `numpy`, `scipy`, `scikit-learn` and `openpyxl`:

```bash
pip install -r requirements.txt
```

Optional: `pyreadstat` for SPSS files, `weasyprint` for PDF export when no Chrome or Edge is installed.

## How it works

The skills drive a tested analysis engine in `scripts/`:

```bash
python3 scripts/ib.py profile survey.csv          # question types, batteries, KPI and group candidates
python3 scripts/ib.py analyze survey.csv --compare Q3
python3 scripts/ib.py themes --codes codes.json   # after Claude codes the comments
python3 scripts/ib.py render --narrative narrative.json [--pdf] [--brand none]
```

The engine computes every number; Claude reviews the profile, codes the comments and writes the narrative
(`docs/narrative.md`), so the words can never drift from the data. Methods are described in `docs/methods.md`.

## Development

```bash
pip install -r requirements.txt pytest
python3 tests/make_fixtures.py   # synthetic Qualtrics, SurveyMonkey and Google Forms exports
python3 -m pytest
./tools/build.sh                 # builds dist/insight-badger.zip
```

## Licence

Apache 2.0
