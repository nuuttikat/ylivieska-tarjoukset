#!/usr/bin/env python3
"""Merge the fetched offers and the K-Ruoka snapshot into one self-contained index.html."""
import json
from pathlib import Path

HERE = Path(__file__).parent
fetched = json.loads((HERE / "data" / "offers.json").read_text(encoding="utf-8"))
offers = list(fetched["offers"])
for name in ("k-ruoka-snapshot.json", "s-kaupat-snapshot.json", "halpahalli-snapshot.json"):  # collected in a real browser
    snap = HERE / "data" / name
    if snap.exists():
        offers += json.loads(snap.read_text(encoding="utf-8"))["offers"]
watches_file = HERE / "data" / "watches.json"
watches = json.loads(watches_file.read_text(encoding="utf-8")).get("watches", []) if watches_file.exists() else []
data = {"fetched": fetched["fetched"], "offers": offers, "watches": watches}
page = (HERE / "template.html").read_text(encoding="utf-8").replace(
    "__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
(HERE / "index.html").write_text(page, encoding="utf-8")
# The GitHub Pages copy needs its own document head (the Claude page adds one itself).
(HERE / "standalone.html").write_text(
    '<!doctype html><html lang="fi"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    '<style>body{margin:0}</style></head><body>' + page + '</body></html>', encoding="utf-8")
print(len(offers), "offers,", len(page) // 1024, "KB")
