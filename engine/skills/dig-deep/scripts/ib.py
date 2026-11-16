#!/usr/bin/env python3
"""Insight Badger command line. The skills call this; people can too.

  python3 ib.py profile  survey.csv                       # question types, KPI and group candidates
  python3 ib.py analyze  survey.csv [--kpi Q1 --compare Q3 ...]
  python3 ib.py themes   --codes codes.json               # after Claude codes the open-text answers
  python3 ib.py render   --narrative narrative.json [--brand none] [--pdf]
  python3 ib.py pdf      report.html [--brand none]

Every command prints a short plain-text digest and writes JSON into the
working folder (default: ./insight-badger/<file name>/).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

import numpy as np  # noqa: E402


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if math.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, float) and math.isnan(o):
        return None
    return str(o)


def _clean(o):
    """Replace NaN with None so the JSON is valid everywhere."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, float) and math.isnan(o):
        return None
    if isinstance(o, np.floating):
        return None if math.isnan(float(o)) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_clean(data), fh, ensure_ascii=False, indent=1, default=_default)


def read_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def workdir(data_path: str | None, out: str | None) -> str:
    if out:
        return out
    stem = os.path.splitext(os.path.basename(data_path))[0] if data_path else "survey"
    return os.path.join(os.getcwd(), "insight-badger", stem)


def _split(v):
    return [x.strip() for x in v.split(",") if x.strip()] if v else None


def cmd_profile(a):
    from insight_badger.detect import build_profile, summary_text
    from insight_badger.loading import load_codebook, load_survey
    sv = load_survey(a.data, a.sheet)
    cb = load_codebook(a.codebook) if a.codebook else None
    overrides = read_json(a.types) if a.types else None
    prof = build_profile(sv, cb, overrides)
    prof["file"] = os.path.abspath(a.data)
    prof["sheet"] = a.sheet
    prof["codebook"] = os.path.abspath(a.codebook) if a.codebook else None
    out = workdir(a.data, a.out)
    write_json(os.path.join(out, "profile.json"), prof)
    print(summary_text(prof))
    print("\nColumns (id | type | label):")
    for c in prof["columns"]:
        if c["type"] in ("metadata", "empty"):
            continue
        extra = f" [{c['group']}]" if c.get("group") else ""
        print(f"  {c['id'][:48]} | {c['type']}{extra} | {c['label'][:80]}")
    print(f"\nWrote {os.path.join(out, 'profile.json')}")


def cmd_analyze(a):
    from insight_badger.analyze import run, summary_text
    from insight_badger.detect import build_profile
    from insight_badger.loading import load_codebook, load_survey
    out = workdir(a.data, a.out)
    prof_path = a.profile or os.path.join(out, "profile.json")
    if os.path.exists(prof_path):
        prof = read_json(prof_path)
        data = a.data or prof["file"]
        sv = load_survey(data, prof.get("sheet"))
    else:
        if not a.data:
            sys.exit("Give the survey file, or run 'profile' first.")
        sv = load_survey(a.data, a.sheet)
        prof = build_profile(sv, load_codebook(a.codebook) if a.codebook else None)
        prof["file"] = os.path.abspath(a.data)
        write_json(prof_path, prof)
    if a.types:
        for c in prof["columns"]:
            t = read_json(a.types).get(c["id"])
            if t:
                c["type"] = t
    results, texts = run(
        sv, prof, kpi=a.kpi, driver_cols=_split(a.drivers), compare=_split(a.compare), pair=_split(a.pair),
        filters=a.filter, weights_col=a.weights, wave=a.wave,
        do_segments=not a.no_segments and (a.mode == "deep" or a.segments),
        keep_flagged=a.keep_flagged, mode=a.mode, max_texts=a.max_texts)
    if a.question:
        results["meta"]["question"] = a.question
    write_json(os.path.join(out, "results.json"), results)
    write_json(os.path.join(out, "texts.json"), texts)
    print(summary_text(results))
    if texts:
        print(f"\nOpen-text answers to code: {os.path.join(out, 'texts.json')}")
    print(f"Wrote {os.path.join(out, 'results.json')}")


def cmd_themes(a):
    from insight_badger.text import apply_codes
    out = a.out or os.path.dirname(os.path.abspath(a.results or "")) or os.getcwd()
    rpath = a.results or os.path.join(out, "results.json")
    tpath = a.texts or os.path.join(os.path.dirname(rpath), "texts.json")
    results, texts, codes = read_json(rpath), read_json(tpath), read_json(a.codes)
    coded = {c["column"]: c for c in apply_codes(texts, codes)}
    for o in results["open_text"]:
        if o["column"] in coded:
            o.update(themes=coded[o["column"]]["themes"], quotes=coded[o["column"]]["quotes"],
                     n_coded=coded[o["column"]]["n_coded"], sampled=coded[o["column"]]["sampled"])
    write_json(rpath, results)
    for c in coded.values():
        print(f"{c['column']}: {c['n_coded']} answers coded" + (" (sample)" if c["sampled"] else ""))
        for t in c["themes"]:
            print(f"  {t['name']}: {t['pct']}% ({t['count']}), negative {t['negative_pct']}%, "
                  f"positive {t['positive_pct']}%, by group {t['by_group']}, examples {t['example_ids']}")
    print(f"Updated {rpath}")


def cmd_render(a):
    from insight_badger.report.render import render_report
    from insight_badger.brand import load_brand
    rpath = a.results or os.path.join(a.workdir or os.getcwd(), "results.json")
    results = read_json(rpath)
    narrative = read_json(a.narrative)
    brand = load_brand(a.brand, a.config)
    html, warnings_ = render_report(results, narrative, brand)
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(rpath)), _report_name(results, narrative))
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    for w in warnings_:
        print("Warning:", w)
    print(f"Wrote report {out}")
    if a.pdf:
        from insight_badger.pdf import html_to_pdf
        pdf_path, msg = html_to_pdf(out, brand_mode=brand["mode"], paper=brand.get("paper", "A4"))
        print(msg)


def _report_name(results, narrative) -> str:
    stem = os.path.splitext(os.path.basename(results["meta"]["file"]))[0]
    return f"{stem}-{results['meta']['mode']}-{results['meta']['generated']}.html"


def cmd_pdf(a):
    from insight_badger.pdf import html_to_pdf
    from insight_badger.brand import load_brand
    brand = load_brand(a.brand, a.config)
    path, msg = html_to_pdf(a.report, out=a.out, brand_mode=brand["mode"], paper=a.paper or brand.get("paper", "A4"))
    print(msg)
    if not path:
        sys.exit(1)


def main(argv=None):
    p = argparse.ArgumentParser(prog="ib.py", description="Insight Badger survey analysis")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("profile", help="Detect question types, batteries, KPI and group candidates")
    s.add_argument("data")
    s.add_argument("--codebook")
    s.add_argument("--sheet")
    s.add_argument("--types", help="JSON file {column: type} to correct detected types")
    s.add_argument("--out", help="Working folder (default ./insight-badger/<file>/)")
    s.set_defaults(func=cmd_profile)

    s = sub.add_parser("analyze", help="Compute every number for the report")
    s.add_argument("data", nargs="?")
    s.add_argument("--profile")
    s.add_argument("--codebook")
    s.add_argument("--sheet")
    s.add_argument("--types")
    s.add_argument("--kpi", help="KPI column (default: best candidate)")
    s.add_argument("--drivers", help="Comma-separated driver columns (default: all rating items)")
    s.add_argument("--compare", help="Comma-separated columns to compare groups by (dig-deep default: demographics)")
    s.add_argument("--pair", help="Two group values to compare item by item, e.g. '1-10,250+'")
    s.add_argument("--filter", action="append", help="e.g. 'Q3=1-10|11-50' or 'Tenure>=2'; repeatable")
    s.add_argument("--weights", help="Weight column")
    s.add_argument("--wave", help="Column holding the survey wave / period")
    s.add_argument("--no-segments", action="store_true")
    s.add_argument("--segments", action="store_true", help="Run mindset segmentation in dig-for mode")
    s.add_argument("--keep-flagged", action="store_true", help="Keep speeders and straight-liners")
    s.add_argument("--mode", choices=["deep", "for"], default="deep")
    s.add_argument("--question", help="The user's question (dig-for)")
    s.add_argument("--max-texts", type=int, default=400, help="Open-text answers per question to code")
    s.add_argument("--out")
    s.set_defaults(func=cmd_analyze)

    s = sub.add_parser("themes", help="Count Claude's open-text codes")
    s.add_argument("--codes", required=True)
    s.add_argument("--results")
    s.add_argument("--texts")
    s.add_argument("--out")
    s.set_defaults(func=cmd_themes)

    s = sub.add_parser("render", help="Build the HTML report (and optionally a PDF)")
    s.add_argument("--narrative", required=True)
    s.add_argument("--results")
    s.add_argument("--workdir")
    s.add_argument("--out")
    s.add_argument("--brand", choices=["insight-badger", "none", "custom"])
    s.add_argument("--config", help="Path to .insight-badger.json (default: search from the working folder up)")
    s.add_argument("--pdf", action="store_true")
    s.set_defaults(func=cmd_render)

    s = sub.add_parser("pdf", help="Save a report as PDF")
    s.add_argument("report")
    s.add_argument("--out")
    s.add_argument("--brand", choices=["insight-badger", "none", "custom"])
    s.add_argument("--config")
    s.add_argument("--paper", choices=["A4", "Letter"])
    s.set_defaults(func=cmd_pdf)

    a = p.parse_args(argv)
    try:
        a.func(a)
    except (ValueError, FileNotFoundError) as exc:
        sys.exit(f"Error: {exc}")


if __name__ == "__main__":
    main()
