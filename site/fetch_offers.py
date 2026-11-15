#!/usr/bin/env python3
"""Fetch this week's offers for Ylivieska stores into data/offers.json.

Standard library only, so it runs anywhere (for example GitHub Actions).
Sources that can be read by a plain script:
  - Lidl        (lidl.fi search API, national weekly offers)
  - Kärkkäinen  (karkkainen.com campaign products in stock in the Ylivieska store)
  - Prisma      (prisma.fi sale products, online store)
K-Citymarket, K-Market and Prisma food offers refuse automated requests, so
they come from data/k-ruoka-snapshot.json, which is collected in a real browser.
"""
import json, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = "Mozilla/5.0 (compatible; tarjoushaku/1.0; family offers page)"
PAUSE = 1.0  # seconds between requests, to stay gentle on the stores
OUT = Path(__file__).parent / "data"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "fi"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as f:
                body = f.read().decode("utf-8", "replace")
            time.sleep(PAUSE)
            return body
        except Exception as e:  # network hiccup: wait and retry
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))


RULES = [
    (r"hedelm|vihann", "Hedelmät ja vihannekset"),
    (r"lemmik", "Lemmikit"),
    (r"laps|lasten|lelu|vauva", "Lapset ja lelut"),
    (r"valmisruo|pakaste", "Valmisruoat ja pakasteet"),
    (r"liha|kala|merenel|äyriäis", "Liha ja kala"),
    (r"maito|juust|kananmun", "Maito ja juusto"),
    (r"kuiva|mauste|öljy|texmex|murot|säilyk|kastik", "Kuivat, mausteet ja kastikkeet"),
    (r"leiv|leivon|paistopiste|keksi", "Leivät ja leivonnaiset"),
    (r"makeis|napostel|snack", "Makeiset ja naposteltavat"),
    (r"juoma|kahvi|olut|siideri|alkoholi", "Juomat ja kahvi"),
    (r"vaat|kenk|kengä|muoti|pukeutu", "Vaatteet ja kengät"),
    (r"kosmet|kauneu|hygien|hyvinvoin|terveys", "Kauneus ja terveys"),
    (r"urheilu|vapaa-aika|erä |retkeily|käsityö|harraste", "Urheilu ja vapaa-aika"),
    (r"kodinkone|elektroniikka|pelaaminen", "Elektroniikka ja kodinkoneet"),
    (r"sähkö|pienrauta|auto|työkalu|remont|koneet", "Työkalut, remontti ja autoilu"),
    (r"piha|puutarha|kukat|kasvit", "Piha, kukat ja puutarha"),
    (r"koti|keittiö|sisustus|kodinhoito|taloustarv|kodinteks", "Koti, keittiö ja siivous"),
    (r"kirjat|lehdet|paperitarv", "Kirjat ja toimisto"),
    (r"ruoka|elintarvik", "Ruoka, muut"),
]


def unify(raw):
    s = (raw or "").lower() + " "
    for pat, group in RULES:
        if re.search(pat, s):
            return group
    return "Muut"


def offer(store, cat, name, price, unit="", was=None, pct=None, note="", valid="", url=""):
    if pct is None and price and was and was > price:
        pct = round((1 - price / was) * 100)
    if pct is not None and pct <= 0:
        pct = None
    return [store, unify(cat), name.strip(), price, unit, was, pct, note, valid, url]


# ---------------------------------------------------------------- Lidl
LIDL_CATS = {
    10068374: "Ruoka ja juoma", 10068166: "Keittiö ja kodinhoito", 10068222: "Remontointi ja puutarha",
    10068226: "Urheilu ja vapaa-aika", 10068371: "Koti ja sisustus", 10068373: "Muoti ja asusteet",
    10068225: "Vauvat, lapset ja lelut",
}


def lidl():
    out, seen = [], set()
    for cid, label in LIDL_CATS.items():
        offset = 0
        while True:
            d = json.loads(get("https://www.lidl.fi/q/api/search?offset=%d&fetchsize=100&locale=fi_FI"
                               "&assortment=FI&version=2.1.0&category.id=%d" % (offset, cid)))
            items = d.get("items", [])
            for it in items:
                g = (it.get("gridbox") or {}).get("data") or {}
                pid = g.get("itemId")
                if not g.get("fullTitle") or pid in seen:
                    continue
                p = g.get("price") or {}
                plus = (g.get("lidlPlus") or [None])[0]
                price, was, pct, note = p.get("price"), p.get("oldPrice") or (p.get("discount") or {}).get("deletedPrice"), None, ""
                unit = (p.get("packaging") or {}).get("text", "")
                if plus and (plus.get("price") or {}).get("price"):
                    pp = plus["price"]
                    was = was or price
                    price = pp["price"]
                    unit = (pp.get("packaging") or {}).get("text", "") or unit
                    note = "Lidl Plus -sovelluksella"
                    m = re.search(r"(\d+)\s*%", plus.get("highlightText") or "")
                    pct = int(m.group(1)) if m else None
                badges = [b.get("text", "") for b in ((g.get("stockAvailability") or {}).get("badgeInfo") or {}).get("badges", [])]
                valid = next((b for b in badges if re.search(r"\d+\.\d+\.", b)), "")
                if not price or not (valid or was or note):
                    continue  # permanent assortment, not an offer
                path = ((g.get("keyfacts") or {}).get("wonCategoryPrimary") or "").split("/")
                raw = path[2] if len(path) > 2 and path[1].startswith("Ruoka") else (path[1] if len(path) > 1 else label)
                if cid != 10068374:
                    raw = label
                seen.add(pid)
                out.append(offer("Lidl", raw, g["fullTitle"].lstrip("- "), price, unit, was, pct, note,
                                 valid.replace(" - ", "–"), "https://www.lidl.fi" + (g.get("canonicalUrl") or "")))
            offset += len(items)
            if not items or offset >= d.get("numFound", 0):
                break
    return out


# ---------------------------------------------------------------- Kärkkäinen
KARK = "https://www.karkkainen.com/verkkokauppa"
KARK_CATS = {
    "ruoka-tarjoukset": "Ruoka", "pukeutuminen-tarjoukset-54840001": "Pukeutuminen", "tyokalu-tarjoukset": "Työkalu ja työvaate (työkalu)",
    "koti-ja-sisustus-tarjoukset": "Koti ja sisustus", "era-ja-retkeily-tarjoukset": "Erä ja retkeily",
    "elektroniikka-ja-pelaaminen-tarjoukset": "Elektroniikka ja pelaaminen", "autoilu-ja-caravan-tarjoukset-32379001--11": "Autoilu",
    "lelut-ja-lastentarvikkeet-tarjoukset-32379009--11": "Lelut ja lastentarvikkeet", "piha-ja-puutarha-tarjoukset-32379012--11": "Piha ja puutarha",
    "urheilu-tarjoukset-32379016--11": "Urheilu", "koneet-tarjoukset": "Koneet", "kasityot-taiteet-ja-harrasteet-tarjoukset": "Käsityöt ja harrasteet",
    "lemmikit-tarjoukset": "Lemmikit", "remontointi-tarjoukset-32379013--11": "Remontointi",
}
KARK_FACET = urllib.parse.quote("attributes.Saatavuus myymälästä:Ylivieska")


def karkkainen():
    out, seen = [], set()
    for slug, label in KARK_CATS.items():
        offset, total = 0, 1
        while offset < total and offset < 1500:
            html = get("%s/%s?facet=%s&offset=%d" % (KARK, slug, KARK_FACET, offset))
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
            if not m:
                break
            fb = json.loads(m.group(1))["props"]["pageProps"].get("fallback", {})
            key = next((k for k in fb if "Product_LISTING" in k), None)
            if not key:
                break
            listing = fb[key]
            total = listing.get("total", 0)
            contents = listing.get("contents", [])
            for p in contents:
                prices = {x.get("usage"): x.get("value") for x in p.get("price") or []}
                now, was = prices.get("Offer"), prices.get("Display")
                if p.get("id") in seen or not now or not was or was <= now:
                    continue
                seen.add(p.get("id"))
                out.append(offer("Kärkkäinen", label, p.get("name", ""), now, "", was, None, "",
                                 "Saatavilla Ylivieskan myymälästä", KARK + ((p.get("seo") or {}).get("href") or "")))
            if not contents:
                break
            offset += len(contents)
    return out


# ---------------------------------------------------------------- Prisma
PRISMA_CATS = {
    "11/kodinkoneet": "Kodinkoneet", "15/elektroniikka": "Elektroniikka", "5/muoti": "Muoti", "6/urheilu-ja-vapaa-aika": "Urheilu ja vapaa-aika",
    "4/koti": "Koti", "14/piha-ja-puutarha": "Piha ja puutarha", "7/lemmikit": "Lemmikit", "3/remontointi": "Remontointi",
    "17/kauneus-ja-hyvinvointi": "Kauneus ja hyvinvointi", "1857/kirjat": "Kirjat",
}


def prisma_products(html):
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, re.S)
    text = ""
    for c in chunks:
        try:
            text += json.loads('"' + c + '"')
        except ValueError:
            pass
    i = text.find('"products":[')
    if i < 0:
        return []
    try:
        return json.JSONDecoder().raw_decode(text, i + len('"products":'))[0]
    except ValueError:
        return []


def prisma():
    out, seen = [], set()
    for path, label in PRISMA_CATS.items():
        for page in range(1, 26):
            prods = prisma_products(get("https://www.prisma.fi/kampanjat/ale/kategoria/%s?page=%d" % (path, page)))
            fresh = 0
            for p in prods:
                sid = p.get("sokId")
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                fresh += 1
                final, ao, reg = p.get("finalPrice"), p.get("aoPrice"), p.get("regularPrice")
                price = min(x for x in (final, ao) if x) / 100 if (final or ao) else None
                was = reg / 100 if reg and price and reg / 100 > price else None
                if not price or not was:
                    continue
                note = "S-Etukortilla, muuten %s €" % ("%.2f" % (final / 100)).replace(".", ",") if ao and final and ao < final else ""
                out.append(offer("Prisma.fi", label, p.get("productName", ""), price, "", was, None, note,
                                 "Prisma.fi-verkkokauppa", "https://www.prisma.fi/tuotteet/%s/%s" % (sid, p.get("slug", ""))))
            if not fresh:
                break
    return out


def main():
    OUT.mkdir(exist_ok=True)
    previous = []
    try:  # keep last run's offers for a store that fails this time
        previous = json.loads((OUT / "offers.json").read_text(encoding="utf-8"))["offers"]
    except Exception:
        pass
    offers, status = [], {}
    for name, fn in (("Lidl", lidl), ("Kärkkäinen", karkkainen), ("Prisma.fi", prisma)):
        try:
            got = fn()
            if not got:
                raise RuntimeError("no offers found")
            status[name] = len(got)
            offers += got
        except Exception as e:  # one store failing must not lose the others
            old = [o for o in previous if o[0] == name]
            status[name] = "virhe: %s (käytetään edellistä hakua, %d tarjousta)" % (e, len(old))
            offers += old
            print("FAILED", name, e, file=sys.stderr)
    payload = {"fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": status, "offers": offers}
    (OUT / "offers.json").write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(status)


if __name__ == "__main__":
    main()
