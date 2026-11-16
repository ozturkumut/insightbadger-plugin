#!/usr/bin/env python3
"""Generate the Markdown-only edition's shared reference files (plugin/, v0.2.5).

The directory accepts only Markdown, text, JSON, YAML and images from
organizations that are not Verified, so the 0.2.5 edition ships the methods and
the report template as Markdown. The template's CSS and JavaScript come from the
engine edition (engine/), so both editions render the same design.

    python3 tools/build_edition_025.py          # write plugin/skills/*/reference/*
    python3 tools/build_edition_025.py --check  # fail if they are out of date (CI)
"""

from __future__ import annotations

import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "engine", "skills", "dig-deep", "scripts", "insight_badger", "report", "assets")
SOURCE_SKILL = os.path.join(ROOT, "plugin", "skills", "dig-deep", "reference")
TARGET_SKILLS = [os.path.join(ROOT, "plugin", "skills", "dig-for", "reference")]


def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def report_guide() -> str:
    src = read(os.path.join(ROOT, "tools", "report_guide.src.md"))
    css = read(os.path.join(ASSETS, "report.css")).strip()
    js = read(os.path.join(ASSETS, "report.js")).strip()
    return src.replace("{{CSS}}", css).replace("{{JS}}", js)


def expected() -> dict[str, bytes]:
    """File name -> content for each skill's reference folder."""
    files = {
        "report.md": report_guide().encode("utf-8"),
        "logo.png": open(os.path.join(ASSETS, "logo.png"), "rb").read(),
        "methods.md": open(os.path.join(SOURCE_SKILL, "methods.md"), "rb").read(),
    }
    return files


def main() -> int:
    check = "--check" in sys.argv
    files = expected()
    stale = []
    for folder in [SOURCE_SKILL] + TARGET_SKILLS:
        os.makedirs(folder, exist_ok=True)
        for name, content in files.items():
            path = os.path.join(folder, name)
            current = open(path, "rb").read() if os.path.exists(path) else None
            if current != content:
                if check:
                    stale.append(os.path.relpath(path, ROOT))
                else:
                    with open(path, "wb") as fh:
                        fh.write(content)
    if check and stale:
        print("0.2.5 reference files are out of date. Run: python3 tools/build_edition_025.py")
        for s in stale:
            print("  ", s)
        return 1
    print("Up to date." if check else "Wrote plugin reference files (edit methods.md under plugin/skills/dig-deep).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
