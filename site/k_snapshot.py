#!/usr/bin/env python3
"""Turn K-Ruoka offers collected in a real browser into data/k-ruoka-snapshot.json.

Usage: k_snapshot.py <browser-dump.json> [<more dumps>...] [--mustikka kmm.json]
A dump is {"store": ..., "collected": ..., "data": {slug: {"cat": ..., "rows": [...]}}}
with rows of [name, price, qty, unit, plussa, normal_price, badge_percent, mobile].
"""
import json, sys
from pathlib import Path
from fetch_offers import offer, OUT

SHORT = {"K-Citymarket Ylivieska": "K-Citymarket", "K-Market Mustikka": "K-Market Mustikka"}


def rows_to_offers(store, cat, rows):
    out = []
    for name, price, qty, unit, plussa, was, badge, mobile in rows:
        qty = qty or 1
        pct = round((1 - price / qty / was) * 100) if price and was else badge
        if not price and not pct:
            continue
        note = "K-Ruoka-sovelluksella" if mobile else ("Plussa-kortilla" if plussa else "")
        out.append(offer(store, cat, name, price, ("%d %s" % (qty, unit)) if qty > 1 else unit, was, pct, note, "", ""))
    return out


def load_dump(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, list):  # saved tool result: [{"type": "text", "text": "\"{...}\"\n\n(captured ...)"}]
        text = raw[0]["text"].split("\n\n(captured")[0]
        raw = json.loads(text)
        if isinstance(raw, str):
            raw = json.loads(raw)
    return raw


def main(argv):
    offers, collected, seen = [], "", set()
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == "--mustikka":
            m = json.loads(Path(args.pop(0)).read_text(encoding="utf-8"))
            for ci, name, price, qty, unit, plussa, was, badge in m["rows"]:
                offers += rows_to_offers("K-Market Mustikka", m["cats"][ci], [[name, price, qty, unit, plussa, was, badge, 0]])
            continue
        d = load_dump(a)
        store = SHORT.get(d["store"], d["store"])
        collected = max(collected, d.get("collected", ""))
        for slug, block in d["data"].items():
            for o in rows_to_offers(store, block["cat"], block["rows"]):
                key = (o[0], o[2], o[3])
                if key not in seen:
                    seen.add(key)
                    offers.append(o)
    OUT.mkdir(exist_ok=True)
    (OUT / "k-ruoka-snapshot.json").write_text(
        json.dumps({"collected": collected, "offers": offers}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    counts = {}
    for o in offers:
        counts[o[0]] = counts.get(o[0], 0) + 1
    print(counts)


if __name__ == "__main__":
    main(sys.argv[1:])
