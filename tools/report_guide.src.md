# Report design and template

Every report is one self-contained HTML file that works offline: inline CSS and
SVG charts, system fonts, no external files, no network requests.

**Build the HTML with a Python script (`build_report.py`) that reads
`results.json`.** Never type a number into the report by hand: the words come
from you, the numbers from the data.

---

## 1. Writing rules

- **Titles state findings.** "Onboarding matters most, and it scores lowest",
  not "Driver analysis". The report title is the single most important finding.
- **Plain language.** Write for someone who has never analysed a survey.
  "statistically significant" → "real, not noise"; "p < 0.05" → "unlikely to be
  chance"; Cronbach's alpha → "the questions hang together"; top-2-box → "% who
  agree or strongly agree".
- **Emphasis carries meaning.** Wrap the problem phrase in
  `<em class="hl-problem">` (clay) and a strength in `<em class="hl-good">`
  (brand colour). At most one of each per sentence.
- **Respect the verdicts** (methods.md §6). Only `real` and `probably real` gaps
  are findings; never report `chance`; mention `small group` only as a caution.
- No emoji. No benchmarks unless the user supplied them.
- Answer: 2–3 sentences. Chapter lede: 1–2 sentences. "So what": one sentence
  about what to do or watch.
- Escape every piece of survey text you insert (`html.escape`).

## 2. Colour means something

| Colour | Meaning | Used for |
|---|---|---|
| Brand teal | brand, good | lead KPI tile, positive answers, strengths, "Protect" |
| Clay | problem to act on | drops, "Fix first", the struggling group, "Act now", negative answers |
| Ochre | watch, uncertain | "Probably real" / "Watch" labels, "Plan next", data-quality flags |
| Slate | comparison, explore further | the comparison group, the dig-for question box, next questions |

Grey everything that is not the point; colour only what the reader should look at.

## 3. Page structure

```
top bar      brand (logo + name) on the left · "Generated on <date>" on the right
hero         mode label · [dig-for: "You asked" + the question] · title · one-line subtitle
             [dig-for: scope chips] · key-figure block (up to 4 tiles, one solid "lead" tile)
tab bar      first tab · divider · numbered chapter tabs · reference tabs on the right
panels       one per tab; previous / next buttons at the bottom
footer       brand · "Generated with Insight Badger · <date> · <file name>"
print only   cover page (brand, title, survey, date, logo) and the key figures
```

**dig-deep tabs:** Overview, then 3–5 numbered chapters (typically Drivers,
Groups, Mindsets, Comments, All ratings), then **All questions** and
**Data & method**.

- *Overview*: the answer; the NPS composition bar (if NPS); "The story in N
  chapters" story map (one card per chapter: tag, chapter number, title, one-line
  summary, "Open …"); "What to do about it" (actions tagged Act now / Plan next /
  Protect) next to "Keep digging" (2–3 follow-up questions with `/dig-for`).
- *Chapters*: kicker ("Chapter 1 · Drivers"), finding title, lede, figures, "So what".
- *All questions*: one card per question; rating batteries as one diverging chart.
- *Data & method*: quality chips, a table of how completely each question was
  answered (with routing notes), methods in plain words, a collapsible codebook.
  **No raw data rows.**

**dig-for tabs:** Answer (answer, 1–3 clay "reason" cards with their number, a
teal "Not the cause" note, actions, next questions), 1–3 numbered chapters
(Evidence, In their words), **How sure we are** (Solid / Watch caveats), and
**Data & method**. The hero uses the slate variant (`class="hero for"`).

Mark a chapter tab whose finding is a problem with `<span class="flag">` (a clay
dot), and add a count badge where useful (`<span class="ct">286</span>`).

## 4. Charts

All charts are inline SVG or HTML drawn to one scale, inside
`<div class="figure"><div class="ftitle">…</div><div class="fsub">…</div> … <div class="src">…</div></div>`.
Every chart title says what it shows. Every SVG gets `role="img"` and an
`aria-label` listing the values. Colour SVG text and marks with the classes in
the template (`c-teal`, `d-clay`, …), never hard-coded colours.

**NPS composition** (HTML): `<div class="npsbar">` with three `<span>` widths =
detractors / passives / promoters %, classes `det`, `pas`, `pro`, plus a legend.

**Driver matrix** (SVG, viewBox `0 0 640 410`, plot x 60–610, y 20–350):
x = importance (0 → max rounded up to 10), y = % rated well (range rounded to
10s, at least 30 points wide). Four zone rectangles split at the average
importance and average performance: top-left `z-slate` NICE TO HAVE, top-right
`z-teal` STRENGTHS TO PROTECT, bottom-left `z-ochre` MONITOR, bottom-right `z-clay`
FIX FIRST (zone labels in the matching `c-*` class, `q-lab`). White grid lines
(`grid-w`). Points coloured by zone (`d-clay` r=9 for fix first, others r=6.5) with
labels in the zone colour; put labels left of points in the right third, and
nudge labels 14px apart when they would overlap.

**Groups with likely ranges** (SVG, width 640, 45px per row, labels at x 10,
plot x 170–620): per group a range line (`ci-teal`, or `ci-clay` for the
highlighted group, `ci-grey` + hollow dot `d-hollow` for groups under 30), a dot,
the value above it, the label and "n = …" on the left. Highlight the group the
story is about with a `pill-clay` row background. A dashed `ref` line marks the
overall score with an ochre "overall …" label. Ticks at nice steps.

**Two-group comparison / dumbbell** (SVG, width 640, 40px per row, labels at x 0,
plot x 190–540 for 0–100%): per item a line between group A (`d-clay`) and group B
(`d-slate`) with the percentages outside the dots and the gap in a `pill-clay`
badge on the right. Gaps that could be chance: grey line (`lk-grey`), hollow dots,
muted labels and the word "chance". Sort by gap.

**Diverging ratings** (HTML): rows `lk-row` = label · track · top-box %. The track
has a centre line at `neg_max / (neg_max + pos_max)`; disagree segments (`s-sd`,
`s-d`) grow left from it, agree segments (`s-a`, `s-sa`) right. Give `.lk-neg`
`left:0; right:<100-mid>%` and `.lk-pos` `left:<mid>%; right:0`, and size each
segment as a % **of its own half** (value / neg_max or value / pos_max), otherwise
the bars collapse. Neutral answers are not drawn. Highlighted rows get `hl`.

**Themes** (HTML): rows `theme` = name · bar · %. Bar length = share of coded
comments (scaled to the largest), split into `neg` / `mix` / `pos` by tone.

**Personas** (HTML): `<article class="persona">` cards with name, share, size bar,
KPI, "Rate highly", "Rate low", "More often", a quote. Colour classes in order:
none (teal), `c1` (ochre), `c2` (slate), `c3`; the segment that needs action gets
`focus` and a "Needs action" `pflag`.

**Quotes** (HTML): `<figure class="quote neg|pos">` with theme label, quote and who
said it (NPS group · a demographic). Never names or contact details.

**Trend** (SVG): line through wave values with a shaded `band-teal` likely range;
last point `d-clay` when the drop is real.

## 5. Branding

Settings come from a `.insight-badger.json` in the working folder or any parent:

```json
{"brand": "insight-badger | none | custom", "name": "Acme Research", "logo": "brand/logo.png",
 "primary": "#1F5FAD", "paper": "A4 | Letter", "confidential": false}
```

- **insight-badger** (default): `reference/logo.png` (next to this file) as a
  base64 data URI in `--logo`; name "Insight Badger", tagline "Survey insights";
  footer "Generated with Insight Badger".
- **none**: no logo, no product name; the top bar shows the survey name; no credit.
- **custom**: their logo and name; footer "Prepared by <name>". Derive the teal
  family from `primary`: `--teal` = primary, `--teal-deep` = same hue at 72%
  lightness, `--teal-mid` / `--teal-pale` / `--teal-wash` = primary mixed with
  white at 45% / 85% / 92%.

## 6. PDF

The template's print styles add a cover page, one chapter per page and page
numbers. When the user asks for a PDF:

1. Ask before running anything. If Chrome, Chromium or Edge is installed, print
   headless (add `--no-sandbox` only when running as root):
   `<chrome> --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf=<report>.pdf file://<report>.html`
2. For an unbranded PDF, build a copy of the report with brand `none` and print that.
3. Otherwise, tell the user to open the report in a browser and print it
   (Cmd/Ctrl+P, then Save as PDF).

## 7. Checks before you hand over the report

- Every number in the text matches `results.json`.
- No `http` URLs, no `<link>`, no `<script src>` in the file.
- Tabs are `<button>` elements with `data-tab`; story cards and pager buttons use
  `data-go`. **Never use `href="#…"` links for navigation**: inside app previews
  they replace the report with a blank page.
- The `<html>` tag starts with `class="no-js"` and the inline script switches it to
  `js`, so without scripts every section shows as one long page.
- Open the file once (or take a screenshot if you can) and look at every tab.

---

## 8. Template

### Head and top bar

```html
<!DOCTYPE html><html lang="en" class="no-js"><head><meta charset="utf-8">
<script>document.documentElement.className='js';</script>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{plain-text title}</title><meta name="generator" content="Insight Badger">
<style>{CSS below, with __PAPER__ replaced by A4 or letter}
:root{--logo:url('data:image/png;base64,{logo}');{custom colour variables}}</style></head>
<body class="deep-report|for-report[ unbranded][ nologo]" data-default-brand="insight-badger|none|custom">
<div class="appbar wrap screen-only"><div class="inner">
  <div class="brand"><span class="mark" role="img" aria-label="logo"></span>
    <span class="name">Insight Badger<small>Survey insights</small></span></div>
  <span class="stamp num">Generated on 16 Nov 2026</span>
</div></div>
```

### Print cover (shown only when printing)

```html
<section class="cover[ for]">{brand block}[<span class="conf-label">Confidential</span>]
  <div class="band"><span class="kind">Full exploration</span><h1>{title}</h1>
  <p class="meta num">{survey} · {wave} · {n} responses · {date}</p></div><div class="bigmark"></div></section>
<div class="print-only"><div class="stats print-stats num">{stat tiles}</div></div>
```

### Hero

```html
<header class="hero[ for] wrap"><div class="inner"><div class="hero-text">
  <span class="mode">Full exploration · /dig-deep</span>
  <!-- dig-for: <div class="asked"><span class="k">You asked</span><span class="q">&ldquo;…&rdquo;</span></div> -->
  <h1>Customers rely on the product, but <em class="hl-problem">a slow start</em> is costing recommendations</h1>
  <p class="sub">One line on what the report covers.</p>
  <!-- dig-for: <div class="scope"><span>Companies of 1-10 vs 1,000+</span>…</div> -->
</div>
<div class="stats num">
  <div class="stat lead"><span class="k">Net Promoter Score</span><span class="v">−7</span><span class="d">likely −14 to 0</span></div>
  <div class="stat alert"><span class="k">Since 2026 Q2</span><span class="v">−11</span><span class="d">from −1</span></div>
  <div class="stat"><span class="k">Responses</span><span class="v">588</span><span class="d">of 600 in the file</span></div>
  <div class="stat"><span class="k">Finished</span><span class="v">94%</span><span class="d">566 of 600</span></div>
</div></div></header>
```

### Tabs and panels

```html
<nav class="tabbar wrap" aria-label="Report sections"><div class="inner tabs" role="tablist">
  <button type="button" class="tab" role="tab" aria-controls="p-overview" data-tab="overview">Overview</button>
  <span class="divider" aria-hidden="true"></span>
  <button type="button" class="tab" role="tab" aria-controls="p-ch-drivers" data-tab="ch-drivers"><span class="no">1</span>Drivers<span class="flag"></span></button>
  …
  <button type="button" class="tab ref" role="tab" aria-controls="p-questions" data-tab="questions">All questions<span class="ct num">28</span></button>
  <button type="button" class="tab" role="tab" aria-controls="p-data" data-tab="data">Data &amp; method</button>
</div></nav>
<main>
  <section class="panel wrap active" id="p-overview" role="tabpanel"><div class="inner">
    <p class="answer">NPS is <em class="hl-problem">below zero</em>. …</p>
    <div class="head"><span class="kicker">The story in 4 chapters</span></div>
    <div class="storymap">
      <div class="story tone-problem" data-go="ch-drivers" role="link" tabindex="0"><div class="top">
        <span class="tag">Fix first</span><span class="ch">Chapter 1</span></div>
        <h3>Onboarding matters most, and scores lowest</h3><p>One-line summary.</p><span class="go">Open Drivers →</span></div>
    </div>
    <div class="split"><div><h3>What to do about it</h3><div class="actions">
      <div class="action now"><span class="tag">Act now</span>…</div>
      <div class="action next"><span class="tag">Plan next</span>…</div>
      <div class="action protect"><span class="tag">Protect</span>…</div></div></div>
    <div><h3>Keep digging</h3><div class="nextq"><div><span>Why are small companies less happy?</span><code>/dig-for</code></div></div></div></div>
    <div class="pager"><button type="button" class="nx" data-go="ch-drivers"><span>Next</span><b>1 · Drivers →</b></button></div>
  </div></section>
  <section class="panel wrap" id="p-ch-drivers" role="tabpanel"><div class="inner">
    <div class="head"><span class="kicker">Chapter 1 · Drivers</span><h2>…</h2></div>
    <p class="lede">…</p>
    <div class="figure">…</div>
    <div class="sowhat"><b>So what</b>…</div>
    <div class="pager"><button type="button" data-go="overview"><span>Previous</span><b>← Overview</b></button>
      <button type="button" class="nx" data-go="ch-groups"><span>Next</span><b>2 · Groups →</b></button></div>
  </div></section>
  …
</main>
<footer class="foot wrap"><div class="inner">{brand block}<span><span class="credit">Generated with Insight Badger · </span>16 Nov 2026 · survey.csv</span></div></footer>
<script>{JS below}</script></body></html>
```

Tab tones: story cards and tags take `tone-problem`, `tone-strength`, `tone-watch`
or nothing (slate). Kickers: `kicker` (teal), `kicker slate`, `kicker ochre`.
Confidence chips: `<span class="conf">Real, not noise</span>`,
`<span class="conf watch">Probably real</span>`, `<span class="conf grey">Could be chance</span>`.

### CSS

```css
{{CSS}}
```

### JavaScript

```js
{{JS}}
```
