"""Report branding: Insight Badger, unbranded, or the user's own brand.

Settings come from (highest first): the --brand flag, a .insight-badger.json
file found in the working folder or any parent, then the default.

.insight-badger.json example::

    {
      "brand": "custom",                 // "insight-badger" | "none" | "custom"
      "name": "Acme Research",           // custom only
      "logo": "brand/acme-logo.png",     // custom only; path relative to this file
      "primary": "#1F5FAD",              // custom only; main colour
      "paper": "A4",                     // or "Letter"
      "confidential": false              // adds a "Confidential" label to the PDF cover
    }
"""

from __future__ import annotations

import base64
import colorsys
import json
import mimetypes
import os

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report", "assets")
CONFIG_NAME = ".insight-badger.json"
LETTER_COUNTRIES_HINT = ("en_US", "en_CA", "es_MX", "en_PH")


def _data_uri(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as fh:
        return f"data:{mime};base64,{base64.b64encode(fh.read()).decode()}"


def find_config(start: str | None = None) -> str | None:
    d = os.path.abspath(start or os.getcwd())
    while True:
        p = os.path.join(d, CONFIG_NAME)
        if os.path.isfile(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _hex_to_rgb(h: str):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_to_hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb)


def _mix(rgb, other, t):
    return tuple(a + (b - a) * t for a, b in zip(rgb, other))


def palette_from(primary: str) -> dict[str, str]:
    """Derive the five brand tints from one colour, as the teal family does."""
    rgb = _hex_to_rgb(primary)
    h, l, s = colorsys.rgb_to_hls(*rgb)
    deep = colorsys.hls_to_rgb(h, max(0.0, l * 0.72), s)
    white = (1, 1, 1)
    return {
        "--teal": _rgb_to_hex(rgb),
        "--teal-deep": _rgb_to_hex(deep),
        "--teal-mid": _rgb_to_hex(_mix(rgb, white, 0.45)),
        "--teal-pale": _rgb_to_hex(_mix(rgb, white, 0.85)),
        "--teal-wash": _rgb_to_hex(_mix(rgb, white, 0.92)),
    }


def default_paper() -> str:
    loc = os.environ.get("LC_ALL") or os.environ.get("LC_PAPER") or os.environ.get("LANG") or ""
    return "Letter" if loc.startswith(LETTER_COUNTRIES_HINT) else "A4"


def load_brand(mode: str | None = None, config_path: str | None = None) -> dict:
    cfg = {}
    path = config_path or find_config()
    if path:
        with open(path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    mode = mode or cfg.get("brand") or "insight-badger"
    if mode not in ("insight-badger", "none", "custom"):
        raise ValueError("brand must be 'insight-badger', 'none' or 'custom'")
    brand = {
        "mode": mode,
        "name": "Insight Badger",
        "tagline": "Survey insights",
        "logo": _data_uri(os.path.join(ASSETS, "logo.png")),
        "colors": {},
        "paper": cfg.get("paper") or default_paper(),
        "confidential": bool(cfg.get("confidential", False)),
        "config_path": path,
    }
    if mode == "custom":
        brand["name"] = cfg.get("name") or "Report"
        brand["tagline"] = cfg.get("tagline", "")
        logo = cfg.get("logo")
        if logo:
            lp = logo if os.path.isabs(logo) else os.path.join(os.path.dirname(path or "."), logo)
            if not os.path.isfile(lp):
                raise ValueError(f"Brand logo not found: {lp}")
            brand["logo"] = _data_uri(lp)
        else:
            brand["logo"] = None
        if cfg.get("primary"):
            brand["colors"] = palette_from(cfg["primary"])
    return brand
