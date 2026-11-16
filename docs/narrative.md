# Writing narrative.json

The report has two inputs. `results.json` (from `ib.py analyze`) holds every
number. `narrative.json` (written by Claude) holds the words: the headline,
the answer, chapter titles and text, persona names, actions and next
questions. The renderer combines them, so **never type a number into the
narrative that is not in the analyze/themes digest**.

Worked examples: `tests/fixtures/narrative_deep.json` (dig-deep) and
`tests/fixtures/narrative_for.json` (dig-for).

## Writing rules

- **Titles state findings.** "Onboarding matters most, and it scores lowest",
  not "Driver analysis". The report title is the single most important finding.
- **Plain language.** Write for someone who has never analysed a survey.
  Translate: "statistically significant" → "real, not noise"; "p < 0.05" →
  "unlikely to be chance"; Cronbach's alpha → "the questions hang together";
  top-2-box → "% who agree or strongly agree".
- **Emphasis carries meaning.** Wrap the problem phrase in `[[double brackets]]`
  (shown in clay) and a strength in `{{double braces}}` (shown in the brand
  colour). Use at most one of each per sentence, and only for the phrase that
  matters.
- **Respect the verdicts.** Only call a gap real when the digest says `real`.
  `probable` → "probably real"; `chance` → do not report it as a finding;
  `small-base` → mention only as "a small group, so treat with caution".
- **No emoji, no benchmarks you cannot source.** Only compare to an industry
  benchmark the user gave you.
- Keep the answer to 2–3 sentences, each chapter `lede` to 1–2 sentences, and
  each `so_what` to one sentence about what to do or watch.

## Fields

| Field | Used in | Notes |
|---|---|---|
| `title` | both | Headline finding. Supports `[[ ]]` and `{{ }}`. |
| `subtitle` | both | One line on what the report covers. Optional. |
| `survey_name`, `wave`, `fieldwork` | both | Shown in the top bar, cover and footer. Optional. |
| `answer` | both | 2–3 sentence answer, first thing on the first tab. |
| `question` | dig-for | The user's question, word for word. |
| `scope` | dig-for | List of short chips, e.g. `["Companies of 1-10 vs 250+", "Wave 3 only"]`. |
| `stats` | both | Up to 4 header tiles `{label, value, note, tone}`; tone `lead` (one, solid fill), `alert` (problem), `good`, `plain`. Omit to use defaults from the data. |
| `reasons` | dig-for | 1–3 cards `{label, value, text}` for the main reasons behind the answer. |
| `not_cause` | dig-for | One sentence on what is *not* driving it. |
| `labels` | both | Short display names: `{"Q2_1": "Onboarding clarity"}`. Strongly recommended: raw question text makes poor chart labels. |
| `chapters` | both | 3–5 for dig-deep, 1–3 for dig-for. See below. |
| `segments` | dig-deep | Persona names keyed by segment id: `{"0": {"name": "Settled advocates", "quote": "...", "flag": false, "description": "..."}}`. Set `flag: true` on the one segment that needs action. `quote_id: "Q7:123"` uses a coded comment instead of `quote`. |
| `actions` | both | `{priority: "now" | "next" | "protect", text}`. 2–4 items. |
| `next_questions` | both | `{text, skill: "dig-for" | "dig-deep"}`. 2–3 items. |
| `caveats` | both | `{level: "solid" | "watch", text}`. Defaults to the data caveats. |
| `confidence_title` | dig-for | Title of the "How sure we are" tab. |

### Chapters

```json
{"id": "drivers", "tab": "Drivers", "tag": "Fix first", "tone": "problem",
 "title": "Onboarding matters most, and [[it scores lowest]]",
 "summary": "One line for the story map on the first tab.",
 "lede": "One or two sentences of context.",
 "figures": [{"type": "drivers"}],
 "so_what": "What to do about it.",
 "count": 4}
```

`tone` sets the colour of the story-map card and tab: `problem` (clay, also
adds a dot on the tab), `strength` (brand colour), `watch` (ochre), `neutral`
(slate). `count` adds a small badge on the tab (for example 4 mindsets).

### Figure types

| type | Needs | Shows |
|---|---|---|
| `nps` | NPS KPI | Detractor / passive / promoter bar |
| `drivers` | driver analysis | Importance vs performance matrix with four zones |
| `groups` | `dimension` (a `--compare` column); optional `highlight: ["value"]` | KPI per group with likely ranges |
| `pair` | `dimension` with a pair (`--pair`, or the extremes) | Item-by-item gaps between two groups |
| `segments` | segmentation | Persona cards |
| `themes` | `column` of coded open text | Theme bars split by tone |
| `quotes` | `column`; optional `ids` (response ids from the themes digest) | Quote cards |
| `ratings` | optional `columns` or `group`, optional `highlight` | Diverging agree/disagree bars |
| `trend` | `--wave` | KPI by wave with likely range |
| `question` | `column` | One question card |
| `text` | `text` | A paragraph |

Any figure accepts `title` and `subtitle` to override the default chart title.
Write chart titles that say what the chart shows.

## Checks before rendering

- Every number in `title`, `answer`, `reasons`, `stats` and chapter text is in
  the digest (rounded the same way).
- Every `dimension` was passed to `--compare`, every `column` exists.
- Render prints `Warning:` lines for anything it had to skip. Fix them and
  render again; a finished report has no warnings.
