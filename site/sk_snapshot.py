#!/usr/bin/env python3
"""Turn Prisma Ylivieska food offers collected in a real browser into data/s-kaupat-snapshot.json.

Usage: sk_snapshot.py <browser-dump.json>
Source: s-kaupat.fi/hakutulokset?label=DISCOUNTED&storeId=685834236 (all pages), one row per
product link: [name, display_price, labels, lowest_30_day_price, comparison_price, validity, price_text].
S-kaupat cards carry no category, so the group is guessed from the product name.
"""
import json, re, sys
from pathlib import Path
from fetch_offers import OUT, unify
from hh_snapshot import group, load_dump

FIRST_RULES = [
    (r"bolsius|kynttilä|huonetuoksu", "Koti, keittiö ja siivous"),
    (r"calluna|kukka|ruukku", "Piha, kukat ja puutarha"),
    (r"taste of the wild|tintin|herkkutanko|koiran|kissan", "Lemmikit"),
    (r"vuokkoset|\bside\b|ohutside|yöside|co-test|eye patch|kangasmaski|kangasnaamio|piiink|cutrin|gunry|hand soap|hoitosuihke", "Kauneus ja terveys"),
    (r"yale|lukitusvaijeri", "Työkalut, remontti ja autoilu"),
    (r"candy|allstar mix|karkki", "Makeiset ja naposteltavat"),
    (r"noodles|nuudel|torttupohja", "Kuivat, mausteet ja kastikkeet"),
    (r"limppu", "Leivät ja leivonnaiset"),
    (r"kurpitsa", "Hedelmät ja vihannekset"),
    (r"levite|oivariini|voi\b", "Maito ja juusto"),
]

FOOD_RULES = [
    (r"naudan|ulkofilee|entrecote|filee", "Liha ja kala"),
    (r"jauheliha|broileri|kana|kalkkuna|possu|sian|nauta|liha|makkara|nakki|pekoni|kinkku|leikkele|burgeri|lohi|silli|kala|tonnikala|katkarap|seiti|muikku", "Liha ja kala"),
    (r"maito|jogurt|rahka|juusto|voi\b|levite|kerma|vanukas|viili|kefiiri|oltermanni|valio|arla|munat|kananmun|margariini|oivariini", "Maito ja juusto"),
    (r"omena|banaani|appelsiini|mandariini|peruna|porkkana|sipuli|tomaatti|kurkku|salaatti|paprika|kaali|marja|mustikka|puolukka|hedelmä|vihannes|sieni|herne|avokado|sitruuna|päärynä|viinirypäl|klementiini", "Hedelmät ja vihannekset"),
    (r"pizza|pakaste|valmisruoka|laatikko|keitto|lasagne|piirakka|pyttipannu|ateria|lihapull|kebab", "Valmisruoat ja pakasteet"),
    (r"leipä|sämpylä|patonki|ruisleip|kakku|pulla|korvapuusti|croissant|tortilla", "Leivät ja leivonnaiset"),
    (r"olut|siideri|lonkero|viini|limonadi|virvoitus|mehu|kahvi|tee\b|kaakao|smoothie|vesi\b|energiajuoma|juoma", "Juomat ja kahvi"),
]


def food_group(name):
    low = name.lower()
    for rx, grp in FIRST_RULES:
        if re.search(rx, low):
            return grp
    g = group(name)
    if g != "Muut":
        return g
    for rx, grp in FOOD_RULES:
        if re.search(rx, low):
            return grp
    g = unify(name)
    return g if g else "Muut"


def euro(text):
    m = re.search(r"(\d+)(?:,(\d{1,2}))?\s*€", text or "")
    return round(float(m.group(1) + "." + (m.group(2) or "0")), 2) if m else None


def main(argv):
    dump = load_dump(argv[0]) if not argv[0].endswith(".jsonl") else None
    offers = []
    for href, (name, shown, labels, low30, cmp_, valid, _text) in dump["data"].items():
        price, unit, note = euro(shown), "", ""
        if not price:
            continue
        was = euro(low30)
        bundle = re.search(r"(\d+)\s*kpl\s*=\s*(\d+(?:,\d+)?)\s*€", labels or "")
        if bundle:
            n, total = int(bundle.group(1)), float(bundle.group(2).replace(",", "."))
            unit, note = "%d kpl" % n, "%d kpl = %s €" % (n, bundle.group(2))
            was, price = round(price * n, 2), total
        elif labels and labels != "Kampanja":
            note = labels
        was = was if was and was > price else None
        v = re.search(r"Voimassa\s+([\d.]+)\s*asti", valid or "")
        offers.append(["Prisma Ylivieska", food_group(name), name, price, unit or cmp_, was,
                       round((1 - price / was) * 100) if was else None, note,
                       ("Voimassa %s asti" % v.group(1)) if v else "Prisma Ylivieska",
                       "https://www.s-kaupat.fi" + href])
    OUT.mkdir(exist_ok=True)
    (OUT / "s-kaupat-snapshot.json").write_text(
        json.dumps({"collected": dump["collected"], "offers": offers}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return offers


if __name__ == "__main__":
    import collections
    offers = main(sys.argv[1:])
    print(len(offers), collections.Counter(o[1] for o in offers).most_common())
    for o in offers:
        if o[1] in ("Muut", "Ruoka, muut"):
            print("  ", o[2])
