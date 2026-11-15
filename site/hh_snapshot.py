#!/usr/bin/env python3
"""Turn Halpa-Halli offers collected in a real browser into data/halpahalli-snapshot.json.

Usage: hh_snapshot.py <browser-dump.json>
A dump is {"store": ..., "collected": ..., "data": {page-slug: {sku: row}}} with rows of
[name, final_price, normal_price, discount_percent, url, brand, category_ids].
Halpa-Halli gives no readable category, so the group is guessed from the product name.
"""
import json, re, sys
from pathlib import Path
from fetch_offers import OUT

NAME_RULES = [
    (r"pyykinpes|astianpesu|pesujauhe|pesuaine|puhdistusaine|huuhtelu|ilmanraikast|\bcif\b", "Koti, keittiö ja siivous"),
    (r"after shave|partavesi|kasvovesi|hiusvesi|vitamiini", "Kauneus ja terveys"),
    (r"salaattikastike|majonee|ketsup|sinappi|relish|kurkku", "Kuivat, mausteet ja kastikkeet"),
    (r"piltti|hedelmäsose|annospussi", "Lapset ja lelut"),
    (r"gourmet|best friend|jyrsij", "Lemmikit"),
    (r"wd-40|wurth|kulmalevy|naulauslevy", "Työkalut, remontti ja autoilu"),
    (r"perlana|desinfiointi|tahranpoisto", "Koti, keittiö ja siivous"),
    (r"\blv\b|derma by|kondomi|antiperspir|lotion|serum|cream|mask\b|mousse|hairspray|got2b|lavera|veet|syoss|kiharru|kreatiini|creatine|lämpösuoja|l300", "Kauneus ja terveys"),
    (r"dolce gusto|\btea\b", "Juomat ja kahvi"),
    (r"\blaku|makeinen|patukka|protein bar|doritos|nacho", "Makeiset ja naposteltavat"),
    (r"wasa|näkki", "Leivät ja leivonnaiset"),
    (r"granola|siirappi|mayo|salsa|taateli|luumu|kuutio|punasipul|lihavalmiste|superfood", "Kuivat, mausteet ja kastikkeet"),
    (r"led |airfryer", "Elektroniikka ja kodinkoneet"),
    (r"kissan|koiran|kissalle|koiralle|latz|pedigree|whiskas|sheba|kissanhiekka|lintu(jen|ruoka)|talipallo|purina|dentastix|friskies", "Lemmikit"),
    (r"vaippa|libero|pampers|lasten|vauvan|lelu|lego|barbie|nukke|palapeli|pehmo|leikki|hot wheels|paw patrol|ryhmä hau", "Lapset ja lelut"),
    (r"kahvi|tee\b|teepuss|mehu|limsa|virvoitus|juoma|vesi\b|kivennäis|coca|pepsi|jaffa|energia|kaakao|glögi|cola|nescafe|pommac", "Juomat ja kahvi"),
    (r"suklaa|karkki|karamell|makeis|lakrits|sipsi|pähkinä|keksi|pastill|purukum|popcorn|fazer|marabou|panda|haribo|malaco|tikkari|toffee|konveht|joulukalenteri|naposte|taffel|estrella|pringles|salmiak|cloetta|maltesers|m&m|snickers|twix|kinder|dumle|geisha|wiener|lakt?ritsi", "Makeiset ja naposteltavat"),
    (r"juusto|maito|jogurt|voi\b|margariini|kerma|rahka", "Maito ja juusto"),
    (r"leipä|näkkileip|korppu|kakku|pulla|piparkak|piparit", "Leivät ja leivonnaiset"),
    (r"jauho|sokeri|pasta|riisi|makaroni|muro|mysli|hiutale|puuro|mauste|ketsup|sinappi|kastike|öljy|suola|säilyke|tonnikala|hillo|hunaja|keitto|nuudel|spagetti|tomaatti|papu|ananas|persik|majonee|marmela|leivinpap|liivate|rusina|manteli|siemen", "Kuivat, mausteet ja kastikkeet"),
    (r"shampoo|hoitoaine|saippua|suihku|deodorant|hammas|voide|rasva|meikki|ripsiväri|huuli|kynsi|hius|partaa|parran|höylä|terä|dušš|dusch|tamponi|terveysside|pikkuhousunsuoja|vanulap|vanupuik|vitamiini|laastari|kosteus|puhdistusliina|käsidesi|tuoksu|parfy|edt|after shave|lumene|nivea|schwarzkopf|gliss|l'oreal|loreal|garnier|dove|rexona|colgate|pepsodent|oral-b|gillette|always|libresse|kasvo|seerumi|naamio|geeli|rakkolaast|magnesium|d-vitamiini|kalaöljy|maitohappo", "Kauneus ja terveys"),
    (r"sukat|sukka|housu|paita|takki|pipo|hanska|käsine|lapaset|kengät|kenkä|saappaa|tossu|alus|bokser|rintaliiv|pyjama|huppari|college|legging|trikoo|farku|villapaita|neule|kaulahuiv|huivi|vyö|lippis|asu\b|mekko|hame|sukkahousu|kerrasto|tennar|lenkkar|sandaal|aamutakki|yöpaita", "Vaatteet ja kengät"),
    (r"kuuloke|kaiutin|laturi|kaapeli|usb|paristo|akku|puhelin|televisio|\btv\b|hiiri|näppäimistö|tabletti|kello|radio|lamppu led|led-lamppu|led lamppu|polttimo|imuri|mikro|vedenkeitin|kahvinkeitin|leivänpaahdin|vatkain|tehosekoitin|blender|silitysrauta|hiustenkuivaa|suoristus|parranajokone|trimmer|kamera|muistikortti|hdmi|virtapankki|jatkojohto|valosarja|jbl|philips|samsung|otsalamppu|taskulamppu", "Elektroniikka ja kodinkoneet"),
    (r"ruuvi|pora|vasara|työkalu|maali|teippi|liima|tiiviste|lukko|pensseli|sivellin|hiomapap|mittanauha|tikkaat|lasinpesu|pesuneste|moottoriöljy|autoshampoo|auton|pyyhkijän|akkulatur|jäätymisenesto|jääskraba|lumiharja|lumilapio|lapio|kärry|silikoni|vaahto|kiintoavain|ruuvimeisseli|pihdit|saha|taltta|puukko|hylsy|ruuvitaltta|terassi|öljynsuod", "Työkalut, remontti ja autoilu"),
    (r"multa|lannoite|kukka|ruukku|siemenet|kastelu|puutarha|grilli|hiili|sytytys|lintulauta|haravа|harava|kynttilälyhty|ulkovalo|hauta", "Piha, kukat ja puutarha"),
    (r"pallo|pyörä|kypärä|luistim|sukset|sauvat|kahvakuula|käsipaino|jooga|treeni|uima|retki|teltta|makuupussi|onki|vapa|uistin|viehe|kelkka|pulkka|liukuri|kortit|peli\b|lautapeli|reppu|termos|juomapullo|heijastin", "Urheilu ja vapaa-aika"),
    (r"kirja|vihko|kynä|paperi(?!pyyh)|kansio|tussi|väri(kynä|liitu)|askartelu|lanka|puikot|virkkuu|kalenteri|kortti|kirjekuor|lahjapaperi|teippirulla|lehtiö|liitu|muistikirja", "Kirjat ja toimisto"),
    (r"pesuaine|pyykki|huuhteluaine|astianpesu|tiskiaine|konetiski|yleispuhdist|wc-|wc |talouspaperi|vessapaperi|paperipyyh|roskapussi|jätesäkki|pakastepussi|leivinpaperi|folio|kelmu|siivous|moppi|harja|sieni|tiskiharja|liina|pyyhe|lakana|pussilakana|tyyny|peitto|peite|matto|verho|kynttilä|tuikku|lautanen|lasi\b|lasit|muki|kuppi|kattila|pannu|veitsi|haarukka|lusikka|aterin|kulho|vuoka|purkki|rasia|säilytys|kori|laatikko|henkari|pyykkipoik|ilmanraikast|omo|ariel|fairy|finish|lambi|lotus|serla|kotimaista|tolu|ajax|cif|domestos|bio luvil|mini risk|comfort|vanish|servetti|kertakäyttö|tulitik|sytytin|joulu|kuusen|koriste|valo|taulu|kehys|peili|lyhty|maljakko|tarjotin|pöytäliina|patja|torkkupeit|viltti|suihkuverho|wc-harja|pesuvati|ämpäri|sanko", "Koti, keittiö ja siivous"),
]


def group(name):
    low = name.lower()
    for rx, g in NAME_RULES:
        if re.search(rx, low):
            return g
    return "Muut"


def load_dump(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, list):  # saved tool result: a list of {"type": "text", "text": ...} parts
        for part in raw:
            text = part["text"]
            i = text.find('"{\\"store\\"')
            if i >= 0:
                return json.loads(json.loads(text[i:].split("\n\n(captured")[0]))
        raise SystemExit("no dump found in " + str(path))
    return raw


NOTES = {"outlet": "Outlet", "kampanjat/black-friday": "Black Friday", "kampanjat/arjen-edulliset": "Arjen edulliset"}


def main(argv):
    dump = load_dump(argv[0])
    offers, seen = [], set()
    for slug, rows in dump["data"].items():
        note = NOTES.get(slug) or NOTES.get(slug.rsplit("/", 1)[0], "")
        for sku, (name, price, was, pct, url, brand, _cats) in rows.items():
            if sku in seen or not price:
                continue
            seen.add(sku)
            if brand and brand.lower() not in name.lower():
                name = brand + " " + name
            was = was if was and was > price else None
            offers.append(["Halpa-Halli", group(name), name, price, "", was,
                           round((1 - price / was) * 100) if was else None, note,
                           "Saatavilla Ylivieskan myymälästä", url])
    OUT.mkdir(exist_ok=True)
    (OUT / "halpahalli-snapshot.json").write_text(
        json.dumps({"collected": dump["collected"], "offers": offers}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return offers


if __name__ == "__main__":
    import collections
    offers = main(sys.argv[1:])
    print(len(offers), collections.Counter(o[1] for o in offers).most_common())
    for o in offers:
        if o[1] == "Muut":
            print("  ", o[2])
