# Ylivieskan tarjoukset

This week's offers from Ylivieska stores on one page, searchable by product, store and category.

## How it updates

- **Lidl, Kärkkäinen (Ylivieska store stock) and Prisma.fi sale items** are fetched by `site/fetch_offers.py`.
  The GitHub Actions workflow `.github/workflows/refresh.yml` runs it every Monday and Thursday at 06:00 Finnish time,
  rebuilds the page and publishes it on GitHub Pages. It can also be started by hand from the Actions tab.
- **K-Citymarket Ylivieska, K-Market Mustikka, Prisma Ylivieska (S-kaupat) and Halpa-Halli Ylivieska** do not allow automated fetching,
  so their offers are collected in a browser and saved as `site/data/k-ruoka-snapshot.json` and
  `site/data/halpahalli-snapshot.json` and `site/data/s-kaupat-snapshot.json` (converted with `k_snapshot.py`, `hh_snapshot.py` and `sk_snapshot.py`).
  They change only when a new snapshot is committed.

## Files

| File | What it does |
| --- | --- |
| `site/fetch_offers.py` | Fetches Lidl, Kärkkäinen and Prisma.fi offers into `site/data/offers.json` (standard library only). If a store fails, its previous offers are kept. |
| `site/build.py` | Merges all data files into `site/index.html` using `site/template.html`. |
| `site/k_snapshot.py`, `site/hh_snapshot.py` | Turn browser-collected dumps into snapshot files. |

Offer rows are `[store, category, name, price, unit, normal_price, discount_percent, note, valid, url]`.

Run locally: `python site/fetch_offers.py && python site/build.py`, then open `site/index.html`.

Prices are copied from the stores' own sites; always check the price in the store.

## Price alerts (hintavahdit)

- **On the page:** open "Hintavahdit", type a product or brand and an optional maximum price. Alerts are saved in the
  viewer's browser and matching offers get a red border.
- **By email:** anyone can also enter an email address. The page posts the alert to a Google Apps Script web app
  (`apps-script/Code.gs`) that keeps alerts in a private Google Sheet. The alert starts only after its owner clicks the
  confirmation link, so nobody can sign someone else up. Once a day the script reads `offers.json` from the published page
  and emails each confirmed alert's new matches once, with links to stop one or all alerts. Limits: 15 alerts per address,
  5 new per address per day, 100 new per day in total, plus Google's own daily email quota.

### Setting up the email alerts

1. Open a new Apps Script project (script.new) and replace the editor's contents with `apps-script/Code.gs`, then save.
   The script creates its own private "Hintavahdit" Sheet the first time it runs.
2. (Or paste it into a Sheet's **Extensions → Apps Script**; then it uses that Sheet.)
3. Choose the `setup` function and press **Run**, then allow the permissions it asks for (sheet, email, fetching the page,
   daily trigger).
4. **Deploy → New deployment → Web app**, execute as **Me**, access **Anyone**. Copy the web app URL.
5. Put the URL in `site/data/alerts-config.json` as `"api"` and push. The email field then appears on the page.
