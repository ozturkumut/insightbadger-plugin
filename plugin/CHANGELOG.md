# Changelog

## 0.3.0 (not released yet)

The engine edition in `engine/`. It ships once the publisher's organization is Verified, which the directory
requires for plugins that include scripts.

### What changes for you

- Reports look different: a headline finding, key figures and chapter tabs. Ask Claude for a PDF, branded or
  unbranded. Reports no longer load anything from the internet.
- Results are saved in an `insight-badger/<file name>/` folder next to where you work, together with a few working
  files (`profile.json`, `results.json`, `texts.json`, `codes.json`, `narrative.json`) that make each run
  reproducible. You can delete them once you have the report.
- Claude now runs a bundled Python script and writes a few files, so you may see permission prompts for those.
  If Python packages are missing, Claude asks before installing them.

### Details

- New analysis engine (`scripts/ib.py`) that computes every number; the skills call it instead of writing analysis code each run.
- Reads Qualtrics (three header rows), SurveyMonkey (two header rows), Google Forms grids and checkboxes, XLSX and SPSS.
- Fixed question-type detection: whole numbers are no longer read as dates, 7-point and 1–10 scales are no longer read as NPS, real scale wording ("Neither agree nor disagree") and "Don't know" answers are handled.
- Text rating scales now work in drivers, mindsets, reliability and trends.
- Correct NPS confidence range; group gaps adjusted for multiple comparisons; groups under 30 flagged; survey weights.
- Speeders measured against the median time instead of always flagging 5%; Qualtrics multi-select blanks no longer counted as missing.
- Personal data kept out of reports and removed from quotes; no raw data rows in the report.
- Open-text themes coded by Claude in any language, counted by the engine.
- New storytelling report: headline finding, key figures, chapter tabs, story map, driver matrix, group dot plots, two-group comparisons, personas, quote cards, light colour-coded design with the badger logo.
- PDF export with a cover page and page numbers, branded or unbranded (`--pdf`, `ib.py pdf`), and custom branding via `.insight-badger.json`.
- Charts are inline SVG and fonts are system fonts: reports work offline and make no network requests (no Chart.js CDN, no Google Fonts).
- Each skill carries its own copy of the engine (Claude.ai chat copies only the skill's folder), referenced through `${CLAUDE_SKILL_DIR}`.
- PDF export keeps Chrome's sandbox on unless running as root.
- Test suite and CI; the plugin archive is built by `tools/build.sh` instead of being committed.

## 0.2.5

Same Markdown-only format as 0.2.0, with the improvements from the 0.3.0 work written into the instructions.

### What changes for you

- A new report design: a headline finding, key figures, numbered chapter tabs, a story map of the findings,
  recommended actions and next questions, with colour that means something (teal good, clay problem, ochre watch,
  slate comparison) and the badger logo.
- New charts: a driver matrix with "fix first" and "protect" zones, group scores with likely ranges, two-group
  comparisons, diverging rating bars, personas, comment themes and quote cards.
- Reports work offline and make no network requests (no Chart.js download, system fonts), and tabs work inside app
  previews.
- Ask for a PDF, branded or unbranded, or print the report from a browser: it prints with a cover page and page
  numbers. Custom branding with `.insight-badger.json`.
- Working files are saved in an `insight-badger/<file name>/` folder next to the survey.

### Fixes in the method instructions

- Qualtrics' three header rows and SurveyMonkey's two are read correctly; Google Forms grids and checkboxes too.
- Whole numbers are not read as dates; 7-point and 1–10 scales are not read as NPS; "Neither agree nor disagree",
  "Don't know" and "Not applicable" are handled; thousands separators are not mistaken for multi-select answers.
- Correct NPS likely range; group gaps adjusted for the number of comparisons; groups under 30 never called real.
- Speeders measured against the median time; routing, drop-off and optional comment boxes not counted as problems;
  multi-select blanks mean "not selected".
- Drivers leave out other overall questions; comment themes are coded by Claude in any language and counted in code.
- Personal data never shown and removed from quotes; no raw data rows in the report.

## 0.2.0

- Initial standalone release with `/dig-deep` and `/dig-for`.
