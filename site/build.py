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
config_file = HERE / "data" / "alerts-config.json"  # {"api": "<Google Apps Script web app URL>"}
alert_api = json.loads(config_file.read_text(encoding="utf-8")).get("api", "") if config_file.exists() else ""
data = {"fetched": fetched["fetched"], "offers": offers, "alertApi": alert_api}
# Plain data for the email-alert script (published next to the page as offers.json).
(HERE / "offers-data.json").write_text(json.dumps({"fetched": fetched["fetched"], "offers": offers},
                                                  ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
page = (HERE / "template.html").read_text(encoding="utf-8").replace(
    "__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
(HERE / "index.html").write_text(page, encoding="utf-8")
# The GitHub Pages copy needs its own document head (the Claude page adds one itself).
(HERE / "standalone.html").write_text(
    '<!doctype html><html lang="fi"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
    '<style>body{margin:0}</style></head><body>' + page + '</body></html>', encoding="utf-8")
print(len(offers), "offers,", len(page) // 1024, "KB")
