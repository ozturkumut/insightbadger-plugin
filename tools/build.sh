#!/usr/bin/env bash
# Check both editions and build their archives:
#   dist/insight-badger-<plugin version>.zip         directory edition (plugin/)
#   dist/insight-badger-<engine version>-engine.zip  engine edition (engine/), for Verified release or local testing
set -euo pipefail
cd "$(dirname "$0")/.."

version_of() { python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['version'])" "$1/.claude-plugin/plugin.json"; }
check_skill_versions() {
  for f in "$1"/skills/*/SKILL.md; do
    grep -q "version: \"$2\"" "$f" || { echo "Version mismatch in $f ($1/.claude-plugin/plugin.json says $2)"; exit 1; }
  done
}

plugin_version=$(version_of plugin)
engine_version=$(version_of engine)
check_skill_versions plugin "$plugin_version"
check_skill_versions engine "$engine_version"
grep -q "__version__ = \"$engine_version\"" engine/skills/dig-deep/scripts/insight_badger/__init__.py \
  || { echo "Version mismatch in the engine __init__.py"; exit 1; }

python3 tools/sync_engine.py --check
python3 tools/build_edition_025.py --check
python3 tools/check_plugin_policy.py plugin

rm -rf dist && mkdir -p dist/stage
pack() {  # pack <folder> <zip name>
  rm -rf dist/stage/insight-badger && cp -r "$1" dist/stage/insight-badger
  find dist/stage -name "__pycache__" -type d -prune -exec rm -rf {} +
  (cd dist/stage && zip -qr "../$2" insight-badger)
}
pack plugin "insight-badger-$plugin_version.zip"
pack engine "insight-badger-$engine_version-engine.zip"
rm -rf dist/stage
echo "Built dist/insight-badger-$plugin_version.zip (directory edition) and dist/insight-badger-$engine_version-engine.zip"
