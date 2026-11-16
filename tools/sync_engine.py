#!/usr/bin/env python3
"""Copy the engine and reference docs from dig-deep (the source) into dig-for.

Claude.ai chat copies only a skill's own folder into its sandbox, so each skill
must carry its own copy of the engine. Edit files under skills/dig-deep only,
then run:

    python3 tools/sync_engine.py          # copy
    python3 tools/sync_engine.py --check  # fail if the copies differ (CI)
"""

from __future__ import annotations

import filecmp
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "skills", "dig-deep")
TARGETS = [os.path.join(ROOT, "skills", "dig-for")]
SHARED = ["scripts", "reference"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")


def differences(a: str, b: str) -> list[str]:
    if not os.path.isdir(b):
        return [b]
    cmp = filecmp.dircmp(a, b, ignore=["__pycache__"])
    out = [os.path.join(b, x) for x in cmp.left_only + cmp.right_only + cmp.diff_files + cmp.funny_files]
    _, mismatch, errors = filecmp.cmpfiles(a, b, cmp.common_files, shallow=False)
    out += [os.path.join(b, x) for x in mismatch + errors if os.path.join(b, x) not in out]
    for sub in cmp.common_dirs:
        out += differences(os.path.join(a, sub), os.path.join(b, sub))
    return out


def main() -> int:
    check = "--check" in sys.argv
    problems = []
    for target in TARGETS:
        for name in SHARED:
            src, dst = os.path.join(SOURCE, name), os.path.join(target, name)
            if check:
                problems += differences(src, dst)
            else:
                shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst, ignore=IGNORE)
    if check and problems:
        print("Engine copies are out of sync. Run: python3 tools/sync_engine.py")
        for p in problems:
            print("  ", os.path.relpath(p, ROOT))
        return 1
    print("In sync." if check else "Copied engine and reference docs into dig-for.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
