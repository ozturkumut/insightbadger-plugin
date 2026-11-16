---
name: dig-for
description: >
  Perform guided survey analysis when the user has a direction but needs help articulating it, and deliver a focused
  one-question HTML report with optional PDF. Use when the user says "dig for", "what's driving NPS", "why is
  satisfaction down", "compare power users vs light users", "compare these segments", "break down Y by Z",
  "what do people complain about", "why did X change", or has a survey export and a rough question. Also triggers on
  "run dig-for" or "/dig-for".
argument-hint: "[question] [survey file]"
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/ib.py *), Bash(python ${CLAUDE_SKILL_DIR}/scripts/ib.py *)
metadata:
  version: "0.3.0"
---

# Dig For: guided survey investigation

The user has a survey export and a rough question. Sharpen the question, run a
focused analysis, and deliver a one-question brief: the answer first, then the
evidence, then how sure we are.

**All numbers come from `ib.py`.** Do not compute statistics yourself or write
your own analysis scripts. Your job is to clarify the question, pick the
comparison, code the relevant comments and write the narrative.

## 0. Set up

`IB` below means `python3 ${CLAUDE_SKILL_DIR}/scripts/ib.py` (use `python` if
`python3` is not found). If that path does not exist (for example in Claude.ai
chat, where it may stay a placeholder), the engine is in the `scripts/` folder
next to this SKILL.md: find it with `find / -name ib.py -path "*dig-for*" 2>/dev/null | head -1`
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

Note the KPI candidates, demographics, batteries and open-text questions. Fix
wrong types with `--types types.json`.

## 2. Clarify (AskUserQuestion)

Ask only what the user's message leaves open, 1–3 questions, offering the
columns you found:

- **KPI**: which question measures success (offer the NPS / satisfaction candidates).
- **Comparison**: which groups to compare (offer demographics with their values),
  and which two groups matter most if there are many.
- **Scope**: everyone, or a subset (one wave, one plan, completed responses only).
- **Time**: compare waves, if a wave or date column exists.

If the message already answers these ("what's driving NPS for enterprise
customers"), skip the questions.

## 3. Analyze

Map the question to options:

| Question | Options |
|---|---|
| What's driving X? | `--kpi X` (drivers run automatically) |
| Compare A vs B / break down X by Y | `--compare Y --pair "A,B"` |
| Why did X change? | `--wave COL --compare <demographics>` |
| How do <subgroup> feel about X? | `--filter "COL=value"` |
| What do people complain about? | read the open text after analyze |
| Find personas | `--segments` |

```bash
IB analyze "<survey file>" --mode for --question "<the user's question>" [options]
```

Read the digest. Only `real` and `probable` gaps are findings; `small-base`
groups need a caution.

## 4. Code the relevant comments

If comments help answer the question, read `insight-badger/<file>/texts.json`.
Each answer carries the person's NPS group and compared-group values, so you
can focus on the groups in question. Write `codes.json` (format in [reference/methods.md](reference/methods.md)),
then:

```bash
IB themes --codes insight-badger/<file>/codes.json --results insight-badger/<file>/results.json
```

## 5. Write the narrative

Write `insight-badger/<file>/narrative.json` following
[reference/narrative.md](reference/narrative.md). For dig-for:

- **question**: the user's question, word for word; **scope**: 2–3 chips.
- **title**: the answer, as a sentence.
- **answer**: 2–3 sentences, leading with the headline number.
- **stats**: 3–4 tiles that answer the question (the gap, the biggest reason, the group sizes).
- **reasons**: the 1–3 main reasons, each with its number; **not_cause**: what is not driving it.
- **chapters**: 1–3, usually Evidence (`groups`, `pair` or `drivers`) and In their words (`quotes`).
- **caveats**: what the conclusion rests on (`solid`) and what to watch (`watch`).
- **actions** and **next_questions**.

## 6. Render

```bash
IB render --narrative insight-badger/<file>/narrative.json --results insight-badger/<file>/results.json
```

Fix every `Warning:` line and render again. `--pdf` also saves a PDF;
`--brand none` makes it unbranded.

## 7. Reply

Lead with the direct answer and its number, like briefing a colleague. One
short paragraph of supporting evidence, one line of caveats, then the report
path and a mention of the **Download PDF** button (branded or unbranded). No
emoji, no tables.

## Guardrails

- Never report a gap marked `chance` or `small-base` as a finding.
- Never quote personal details.
- Never invent benchmarks.
