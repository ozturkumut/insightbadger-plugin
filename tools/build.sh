#!/usr/bin/env bash
# Build the distributable plugin archive: dist/insight-badger.zip
set -euo pipefail
cd "$(dirname "$0")/.."
version=$(python3 -c "import json;print(json.load(open('.claude-plugin/plugin.json'))['version'])")
for f in skills/*/SKILL.md; do
  grep -q "version: \"$version\"" "$f" || { echo "Version mismatch in $f (plugin.json says $version)"; exit 1; }
done
grep -q "__version__ = \"$version\"" skills/dig-deep/scripts/insight_badger/__init__.py || { echo "Version mismatch in the engine __init__.py"; exit 1; }
python3 tools/sync_engine.py --check
rm -rf dist && mkdir -p dist/insight-badger
cp -r .claude-plugin skills assets README.md LICENSE CHANGELOG.md dist/insight-badger/
find dist -name "__pycache__" -type d -prune -exec rm -rf {} +
(cd dist && zip -qr insight-badger.zip insight-badger)
echo "Built dist/insight-badger.zip (version $version)"
