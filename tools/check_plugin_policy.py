#!/usr/bin/env python3
"""Check a plugin folder against the directory rules for organizations that are
not Verified (from the directory's refusal of 0.3.0):

- only Markdown, text, JSON, YAML and PNG/JPEG/GIF/WebP/ICO images
  (plus LICENSE and .gitignore as UTF-8 text)
- no file starting with '#!'
- no `allowed-tools` / `allowedTools` beyond Read, Grep, Glob and LS
- `.claude-plugin/` holds only plugin.json (or marketplace.json, or an image)
- no `.claude/skills` folder, no hooks.json / .mcp.json / .lsp.json / monitors.json
- text files are UTF-8 without NUL bytes

    python3 tools/check_plugin_policy.py plugin
"""

from __future__ import annotations

import os
import re
import sys

TEXT = {".md", ".txt", ".json", ".yaml", ".yml"}
IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
NAMED_TEXT = {"LICENSE", "LICENCE", "LICENSE.md", ".gitignore", "README", "NOTICE"}
FORBIDDEN_NAMES = {"hooks.json", ".mcp.json", ".lsp.json", "monitors.json", "package.json", "pnpm-workspace.yaml",
                   "requirements.txt", "pyproject.toml"}
SAFE_TOOLS = {"Read", "Grep", "Glob", "LS"}


def main(folder: str) -> int:
    problems = []
    for dirpath, dirnames, filenames in os.walk(folder):
        rel_dir = os.path.relpath(dirpath, folder)
        if rel_dir.replace("\\", "/").endswith(".claude/skills"):
            problems.append(f"{rel_dir}: .claude/skills folders are refused")
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, folder)
            ext = os.path.splitext(name)[1].lower()
            data = open(path, "rb").read()
            if name in FORBIDDEN_NAMES:
                problems.append(f"{rel}: file type refused for unverified organizations")
            if os.path.basename(dirpath) == ".claude-plugin" and name not in ("plugin.json", "marketplace.json") \
                    and ext not in IMAGES:
                problems.append(f"{rel}: only plugin.json, marketplace.json or images may sit in .claude-plugin")
            if ext in IMAGES:
                continue
            if ext not in TEXT and name not in NAMED_TEXT:
                problems.append(f"{rel}: not Markdown, text, JSON, YAML or an image")
                continue
            if data.startswith(b"#!"):
                problems.append(f"{rel}: starts with #!")
            if b"\x00" in data:
                problems.append(f"{rel}: contains NUL bytes")
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                problems.append(f"{rel}: not UTF-8")
                continue
            if name == "SKILL.md" or ext == ".json":
                for m in re.finditer(r"(?im)^\s*\"?(allowed-tools|allowedTools)\"?\s*:\s*(.*)$", text):
                    tools = re.findall(r"[A-Za-z]+(?:\([^)]*\))?", m.group(2))
                    extra = [t for t in tools if t not in SAFE_TOOLS]
                    if extra:
                        problems.append(f"{rel}: allowed-tools beyond Read, Grep, Glob, LS: {', '.join(extra)}")
    if problems:
        print(f"{folder}: would be refused by the directory for an unverified organization:")
        for p in problems:
            print("  -", p)
        return 1
    print(f"{folder}: only allowed file types, no scripts, no pre-approved tools.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "plugin"))
