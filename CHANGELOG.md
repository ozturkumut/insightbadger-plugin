# Changelog

## 0.3.0

- New analysis engine (`scripts/ib.py`) that computes every number; the skills call it instead of writing analysis code each run.
- Reads Qualtrics (three header rows), SurveyMonkey (two header rows), Google Forms grids and checkboxes, XLSX and SPSS.
- Fixed question-type detection: whole numbers are no longer read as dates, 7-point and 1–10 scales are no longer read as NPS, real scale wording ("Neither agree nor disagree") and "Don't know" answers are handled.
- Text rating scales now work in drivers, mindsets, reliability and trends.
- Correct NPS confidence range; group gaps adjusted for multiple comparisons; groups under 30 flagged; survey weights.
- Speeders measured against the median time instead of always flagging 5%; Qualtrics multi-select blanks no longer counted as missing.
- Personal data kept out of reports and removed from quotes; no raw data rows in the report.
- Open-text themes coded by Claude in any language, counted by the engine.
- New storytelling report: headline finding, key figures, chapter tabs, story map, driver matrix, group dot plots, two-group comparisons, personas, quote cards, light colour-coded design with the badger logo.
- Download PDF with branded or unbranded output, `--pdf` export, and custom branding via `.insight-badger.json`.
- Charts are inline SVG: reports work offline and no longer load Chart.js from a CDN.
- Test suite and CI; the plugin archive is built by `tools/build.sh` instead of being committed.

## 0.2.0

- Initial standalone release with `/dig-deep` and `/dig-for`.
