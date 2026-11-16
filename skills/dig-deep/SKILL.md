---
name: dig-deep
description: >
  Perform fully automated exploratory analysis on a survey-response file (CSV, XLSX or SPSS) with no prior guidance,
  and deliver a storytelling HTML report with optional PDF. Use when the user says "dig deep", "analyse this survey",
  "explore this survey", "what's interesting in this survey", "find insights", "what can you tell me about these
  responses", or drops a survey export without specific questions. Also triggers on "run dig-deep" or "/dig-deep".
argument-hint: "[survey file] [codebook file]"
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/ib.py *), Bash(python ${CLAUDE_SKILL_DIR}/scripts/ib.py *)
metadata:
  version: "0.3.0"
---

# Dig Deep: autonomous survey analysis

The user has a survey export (Qualtrics, SurveyMonkey, Google Forms, Typeform,
Microsoft Forms, SPSS or custom) and no specific question. Find what matters and
deliver a report a non-technical manager can act on.

**All numbers come from `ib.py`.** Do not compute statistics yourself or write
your own analysis scripts: the engine handles header rows, scales, "don't know"
answers, skip logic, weights, multiple-comparison adjustment and personal data.
Your job is judgement and words: check the profile, choose the KPI, code the
open text, and write the narrative.

## 0. Set up

`IB` below means `python3 ${CLAUDE_SKILL_DIR}/scripts/ib.py` (use `python` if
`python3` is not found). If that path does not exist (for example in Claude.ai
chat, where it may stay a placeholder), the engine is in the `scripts/` folder
next to this SKILL.md: find it with `find / -name ib.py -path "*dig-deep*" 2>/dev/null | head -1`
and use that path.

The engine needs pandas, numpy, scipy, scikit-learn and openpyxl. If a command
fails with a missing package, **ask the user before installing anything**, then
run `pip install -r <scripts folder>/requirements.txt`.

Save working files and the report where the user can open them: by default
`./insight-badger/<file name>/` in the current folder; on Claude.ai, pass
`--out` with the outputs folder the environment provides.

Method details: [reference/methods.md](reference/methods.md).
Narrative format: [reference/narrative.md](reference/narrative.md).

## 1. Profile

```bash
IB profile "<survey file>" [--codebook "<codebook>"]
```


Read the column list. Check that:
- the KPI candidate is right (NPS, overall satisfaction, likelihood to renew);
- demographics (company size, region, role, plan…) are tagged `demographic`;
- rating batteries and multi-select groups were reconstructed;
- nothing important is `unknown`.

Fix wrong types with a small JSON file and `--types types.json` (see
methods.md). If the file is not a survey at all, say so and offer a generic
analysis instead of forcing it.

## 2. Analyze

```bash
IB analyze "<survey file>" [--kpi COL] [--compare COL1,COL2] [--wave COL] [--weights COL]
```

- `--compare`: up to 5 demographic columns (default: the detected demographics).
- `--wave`: if the file holds several survey waves or periods.
- `--weights`: if there is a weight column.

Read the digest it prints. It lists the KPI with its likely range, drivers
with zones, every group comparison with a verdict (`real`, `probable`,
`chance`, `small-base`), segments, and caveats. Only `real` and `probable`
gaps are findings.

## 3. Code the open-text answers

If the digest lists open-text questions, read
`insight-badger/<file>/texts.json`. For each question, build 4–8 themes a
manager would recognise and assign every answer one or more themes plus a
sentiment (`negative`, `mixed`, `positive`). Pick 1–2 vivid, representative
examples per theme. Write `codes.json` in the same folder (format in
[reference/methods.md](reference/methods.md)) and run:

```bash
IB themes --codes insight-badger/<file>/codes.json --results insight-badger/<file>/results.json
```

## 4. Write the narrative

Write `insight-badger/<file>/narrative.json` following
[reference/narrative.md](reference/narrative.md). For dig-deep:

- **title**: the single most important finding, as a sentence.
- **answer**: 2–3 sentences, leading with the KPI and its biggest driver.
- **chapters**: 3–5, ordered by importance. Typical: Drivers (`drivers`),
  Groups (`groups` and `pair` for the biggest real gap), Mindsets (`segments`),
  Comments (`themes`, `quotes`), All ratings (`ratings`). Skip a chapter when the
  data does not support it; never pad.
- **labels**: short names for every rating item and compared column.
- **segments**: a human name for each segment; flag the one that needs action.
- **actions**: 2–4, tagged now / next / protect.
- **next_questions**: 2–3 follow-ups worth running with `/dig-for`.

## 5. Render

```bash
IB render --narrative insight-badger/<file>/narrative.json --results insight-badger/<file>/results.json
```

Fix every `Warning:` line and render again. Add `--pdf` if the user wants a
PDF, and `--brand none` for an unbranded one. A `.insight-badger.json` file
can set a default brand, a custom logo and colour, and A4 or Letter paper (see
the README).

## 6. Reply

2–3 short paragraphs: the KPI and the most actionable finding, the biggest
gap or segment, and what to do next. Give the report path and suggest opening
it in a web browser (Chrome, Edge, Safari, Firefox): app previews may show it
as one long page and cannot print. Mention that the report's **Download PDF**
button offers branded and unbranded versions. Do not paste tables. No emoji.

## PDF requests

When the user asks for a PDF (for example "save this report as a PDF", or
"unbranded"), run:

```bash
IB pdf <report.html> [--brand none]
```

It uses Chrome, Edge or WeasyPrint if one is available. If it reports that no
PDF engine is available (common in sandboxes), tell the user to open the
report in their browser and use its **Download PDF** button.

## Guardrails

- Never quote personal details; the engine removes them from quotes and the report.
- Never report a gap the digest marks `chance` or `small-base` as a finding.
- Never invent benchmarks. Compare to an industry figure only if the user supplied it.
- If the sample is under 100, or completion is low, say so in the answer.
