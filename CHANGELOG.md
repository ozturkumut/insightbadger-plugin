# Changelog

## 0.3.0

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

## 0.2.0

- Initial standalone release with `/dig-deep` and `/dig-for`.
