"""Save a report as PDF without the browser's print dialog.

Tries, in order: Playwright (Python), a Chrome/Chromium/Edge binary in
headless mode, then WeasyPrint. If none is available the report's own
"Download PDF" button still works in any browser.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

CHROME_CANDIDATES = [
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge", "microsoft-edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/opt/pw-browsers/chromium",
]


def _print_html(html_path: str, brand_mode: str) -> str:
    """Copy of the report that opens ready to print in the chosen branding."""
    with open(html_path, encoding="utf-8") as fh:
        html = fh.read()
    cls = "unbranded" if brand_mode == "none" else ""
    html = html.replace('<body class="', f'<body class="{cls} ', 1) if cls else \
        html.replace(" unbranded", "", 1)
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8",
                                      dir=os.path.dirname(os.path.abspath(html_path)))
    tmp.write(html)
    tmp.close()
    return tmp.name


def _find_chrome() -> str | None:
    env = os.environ.get("CHROME_PATH")
    if env and os.path.exists(env):
        return env
    for c in CHROME_CANDIDATES:
        p = shutil.which(c) or (c if os.path.isabs(c) and os.path.exists(c) else None)
        if p:
            if os.path.isdir(p):
                inner = os.path.join(p, "chrome")
                if os.path.exists(inner):
                    return inner
                continue
            return p
    return None


def html_to_pdf(html_path: str, out: str | None = None, brand_mode: str = "insight-badger",
                paper: str = "A4") -> tuple[str | None, str]:
    out = out or os.path.splitext(html_path)[0] + ("-unbranded" if brand_mode == "none" else "") + ".pdf"
    src = _print_html(html_path, brand_mode)
    try:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.goto("file://" + os.path.abspath(src))
                page.wait_for_timeout(400)
                page.pdf(path=out, format="Letter" if paper.lower() == "letter" else "A4", print_background=True,
                         prefer_css_page_size=True)
                browser.close()
            return out, f"Wrote PDF {out}"
        except Exception:
            pass
        chrome = _find_chrome()
        if chrome:
            cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
                   f"--print-to-pdf={os.path.abspath(out)}", "file://" + os.path.abspath(src)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if os.path.exists(out) and os.path.getsize(out) > 0:
                return out, f"Wrote PDF {out}"
            last = (res.stderr or "").strip().splitlines()[-1:] or [""]
            err = f"Chrome could not print the report: {last[0]}"
        else:
            err = "No Chrome, Chromium or Edge found"
        try:
            import weasyprint  # type: ignore
            weasyprint.HTML(src).write_pdf(out)
            return out, f"Wrote PDF {out} (WeasyPrint)"
        except ImportError:
            pass
        return None, (f"{err}, and WeasyPrint is not installed. Open the HTML report in a browser and use its "
                      "Download PDF button instead, or install a PDF engine: pip install weasyprint")
    finally:
        try:
            os.unlink(src)
        except OSError:
            pass
