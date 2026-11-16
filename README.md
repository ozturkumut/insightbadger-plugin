# Insight Badger: development repository

This repository holds two editions of the Insight Badger plugin.

| Folder | Edition | Status |
|---|---|---|
| [`plugin/`](plugin/) | **0.2.5**, Markdown only: Claude writes the analysis each run, guided by `reference/methods.md` and the report template in `reference/report.md` | Submitted to the plugin directory. **Submit this folder.** |
| [`engine/`](engine/) | **0.3.0**, with a tested Python engine that computes every number | Ships once the publisher's organization is Verified: the directory accepts scripts and pre-approved commands only from Verified organizations |

User documentation: [plugin/README.md](plugin/README.md).

## Layout

```
plugin/      the directory edition (Markdown, JSON and PNG only)
engine/      the engine edition (skills with scripts/, reference docs)
tests/       pytest suite for the engine, with synthetic Qualtrics, SurveyMonkey and Google Forms exports
examples/    sample survey with known patterns, for trying either edition
tools/       sync, generation and build scripts
```

## Development

```bash
pip install -r engine/skills/dig-deep/scripts/requirements.txt pytest
python3 -m pytest                      # engine tests
python3 tools/sync_engine.py           # copy the engine from engine/skills/dig-deep into dig-for
python3 tools/build_edition_025.py     # regenerate plugin/skills/*/reference from methods.md and the engine's CSS/JS
./tools/build.sh                       # check everything and build dist/insight-badger-<version>.zip for both editions
```

- Edit 0.2.5 method guidance in `plugin/skills/dig-deep/reference/methods.md` and the report guide in
  `tools/report_guide.src.md`; the build script copies them into both skills.
- The report template's CSS and JavaScript live once, in the engine
  (`engine/skills/dig-deep/scripts/insight_badger/report/assets/`), and are copied into the 0.2.5 guide, so both
  editions render the same design.
- CI fails if `plugin/` contains anything the directory would refuse from an unverified organization: files other
  than Markdown, text, JSON, YAML or images, files starting with `#!`, or `allowed-tools` entries.

## Releasing

1. Raise `version` in the edition's `.claude-plugin/plugin.json` and both `SKILL.md` files (the engine edition also
   in `scripts/insight_badger/__init__.py`); the build checks they match. Users only get an update when the version
   changes.
2. `./tools/build.sh`, then `claude plugin validate --strict plugin`.
3. Merge to `main` and publish the version in the developer portal.

When the organization is Verified: move `engine/` into `plugin/` (keeping its `allowed-tools` in the
`${CLAUDE_PLUGIN_ROOT}` or `${CLAUDE_SKILL_DIR}` form), raise the version to 0.3.0 and submit.
