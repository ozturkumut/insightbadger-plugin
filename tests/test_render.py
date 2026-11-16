"""Report rendering, branding and the command line."""

import json
import os
import subprocess
import sys

from insight_badger.brand import load_brand, palette_from
from insight_badger.report.render import render_report

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
IB = os.path.join(HERE, "..", "skills", "dig-deep", "scripts", "ib.py")


def _coded(q_results):
    from code_texts import code
    from insight_badger.text import apply_codes
    r, texts = q_results
    r = json.loads(json.dumps(r, default=str))
    coded = {c["column"]: c for c in apply_codes(texts, code(texts))}
    for o in r["open_text"]:
        o.update(coded[o["column"]])
    return r


def test_deep_report_renders_without_warnings(q_results):
    r = _coded(q_results)
    narrative = json.load(open(os.path.join(FIX, "narrative_deep.json")))
    html, warnings = render_report(r, narrative, load_brand("insight-badger"))
    assert warnings == []
    for needle in ('id="p-overview"', 'id="p-ch-drivers"', 'id="p-questions"', 'id="p-data"', "FIX FIRST",
                   'class="pdf-menu"', 'data-brand="unbranded"', "Frustrated small teams", 'class="cover"'):
        assert needle in html
    assert "example.com" not in html and "RecipientEmail" not in html
    assert "<script src" not in html  # no external scripts: works offline
    assert "googleapis" not in html and "<link" not in html  # no external fonts or stylesheets


def test_narrative_text_is_escaped(q_results):
    r = _coded(q_results)
    html, _ = render_report(r, {"title": "<script>alert(1)</script> [[bad]]", "answer": "x"}, load_brand("none"))
    assert "<script>alert(1)" not in html
    assert '<em class="hl-problem">bad</em>' in html


def test_unbranded_and_custom_brand(tmp_path, q_results):
    r = _coded(q_results)
    html, _ = render_report(r, {"title": "T"}, load_brand("none"))
    assert "Generated with Insight Badger" not in html and 'class="unbranded' not in html.split("<body")[0]
    assert 'data-default-brand="none"' in html
    cfg = tmp_path / ".insight-badger.json"
    cfg.write_text(json.dumps({"brand": "custom", "name": "Acme Research", "primary": "#1F5FAD", "paper": "Letter"}))
    b = load_brand(None, str(cfg))
    html, _ = render_report(r, {"title": "T"}, b)
    assert "Prepared by Acme Research" in html and "--teal:#1F5FAD" in html and "size: letter" in html
    assert palette_from("#1F5FAD")["--teal-pale"].startswith("#")


def test_unknown_figures_warn(q_results):
    r = _coded(q_results)
    _, warnings = render_report(r, {"title": "T", "chapters": [{"title": "x", "figures": [{"type": "pie"}]}]},
                                load_brand("insight-badger"))
    assert any("pie" in w for w in warnings)


def test_cli_end_to_end(tmp_path):
    env = dict(os.environ, PYTHONPATH="")
    data = os.path.join(FIX, "googleforms.csv")
    run = lambda *a: subprocess.run([sys.executable, IB, *a], cwd=tmp_path, capture_output=True, text=True, env=env)
    p = run("profile", data)
    assert p.returncode == 0, p.stderr
    assert "nps" in p.stdout
    a = run("analyze", data)
    assert a.returncode == 0, a.stderr
    work = tmp_path / "insight-badger" / "googleforms"
    assert (work / "results.json").exists() and (work / "texts.json").exists()
    json.loads((work / "results.json").read_text())  # valid JSON (no NaN)
    nar = tmp_path / "n.json"
    nar.write_text(json.dumps({"title": "Test", "answer": "Fine", "chapters": [
        {"tab": "Ratings", "title": "All ratings", "figures": [{"type": "ratings"}, {"type": "drivers"}]}]}))
    rr = run("render", "--narrative", str(nar), "--results", str(work / "results.json"), "--brand", "none")
    assert rr.returncode == 0, rr.stderr
    out = [f for f in os.listdir(work) if f.endswith(".html")]
    assert out and os.path.getsize(work / out[0]) > 20000


def test_engine_copies_in_sync():
    tool = os.path.join(HERE, "..", "tools", "sync_engine.py")
    res = subprocess.run([sys.executable, tool, "--check"], capture_output=True, text=True)
    assert res.returncode == 0, res.stdout
