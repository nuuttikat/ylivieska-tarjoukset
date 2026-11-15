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
