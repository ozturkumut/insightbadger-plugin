"""Keyword stand-in for Claude's open-text coding, used in tests and demos."""
import json
import sys

RULES = [("setup", "Setup and onboarding", ("setup", "onboarding", "import", "connect")),
         ("price", "Price for small teams", ("price", "expensive", "per seat")),
         ("reliable", "Reliable, just works", ("works", "reliable", "downtime")),
         ("support", "Helpful support", ("support fixed", "great people"))]


def code(texts: dict) -> dict:
    out = {}
    for col, block in texts.items():
        codes = {}
        for r in block["responses"]:
            t = r["text"].lower()
            hits = [rid for rid, _n, kws in RULES if any(k in t for k in kws)]
            if hits:
                neg = hits[0] in ("setup", "price")
                codes[r["id"]] = {"themes": hits, "sentiment": "negative" if neg else "positive"}
        out[col] = {"themes": [{"id": rid, "name": n} for rid, n, _k in RULES], "codes": codes}
    return out


if __name__ == "__main__":
    texts = json.load(open(sys.argv[1]))
    json.dump(code(texts), open(sys.argv[2], "w"), indent=1)
