#!/usr/bin/env python3
"""Email new offers that match the price alerts in data/watches.json.

Runs after every refresh (see .github/workflows/refresh.yml). A watch matches an offer when every
word of "q" appears in the product or store name (accents ignored) and the price is at most "max".
Each match is emailed once; data/alerts-sent.json remembers what was already sent.

Email settings come from environment variables (GitHub repository secrets), never from the repo:
  SMTP_HOST (default smtp.gmail.com), SMTP_PORT (default 465), SMTP_USER, SMTP_PASS,
  ALERT_TO (one or more addresses, comma-separated). Without SMTP_USER/SMTP_PASS/ALERT_TO it only
  prints the matches.
"""
import json, os, smtplib, ssl, sys, unicodedata
from email.message import EmailMessage
from pathlib import Path

DATA = Path(__file__).parent / "data"
PAGE = "https://nuuttikat.github.io/ylivieska-tarjoukset/"


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def all_offers():
    offers = json.loads((DATA / "offers.json").read_text(encoding="utf-8"))["offers"]
    for name in ("k-ruoka-snapshot.json", "s-kaupat-snapshot.json", "halpahalli-snapshot.json"):
        f = DATA / name
        if f.exists():
            offers += json.loads(f.read_text(encoding="utf-8"))["offers"]
    return offers


def matches(watch, o):
    words = norm(watch.get("q")).split()
    text = norm(o[2] + " " + o[0])
    mx = watch.get("max")
    return bool(words) and all(w in text for w in words) and (not mx or (o[3] and o[3] <= mx))


def fmt(x):
    return ("%.2f" % x).replace(".", ",") + " €"


def main():
    watches = json.loads((DATA / "watches.json").read_text(encoding="utf-8")).get("watches", [])
    sent_file = DATA / "alerts-sent.json"
    sent = set(json.loads(sent_file.read_text(encoding="utf-8"))) if sent_file.exists() else set()
    current, new = set(), []
    for o in all_offers():
        for w in watches:
            if matches(w, o):
                key = "|".join(str(x) for x in (o[0], o[2], o[3], o[8]))
                current.add(key)
                if key not in sent:
                    new.append((w, o))
                break
    print("%d watches, %d matching offers, %d new" % (len(watches), len(current), len(new)))
    if not new:
        sent_file.write_text(json.dumps(sorted(sent & current), ensure_ascii=False, indent=0), encoding="utf-8")
        return
    lines = []
    for w, o in new:
        was = " (ennen %s)" % fmt(o[5]) if o[5] else ""
        lines.append("- %s: %s %s%s%s\n  %s" % (o[0], o[2], fmt(o[3]), was, (", " + o[8]) if o[8] else "", o[9] or PAGE))
    body = "Hintavahtisi löysivät uusia tarjouksia:\n\n" + "\n".join(lines) + "\n\nKaikki tarjoukset: " + PAGE + "\n"
    print(body)
    user, pw, to = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASS"), os.environ.get("ALERT_TO")
    if not (user and pw and to):
        print("Email settings missing; not sending and not marking as sent.")
        return
    msg = EmailMessage()
    msg["Subject"] = "Hintavahti: %d uutta tarjousta" % len(new)
    msg["From"] = user
    msg["To"] = to
    msg.set_content(body)
    host, port = os.environ.get("SMTP_HOST") or "smtp.gmail.com", int(os.environ.get("SMTP_PORT") or 465)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=30) as s:
                s.login(user, pw); s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls(context=ssl.create_default_context()); s.login(user, pw); s.send_message(msg)
    except Exception as e:
        print("Sending failed:", e, file=sys.stderr)
        sys.exit(1)
    sent_file.write_text(json.dumps(sorted(current), ensure_ascii=False, indent=0), encoding="utf-8")
    print("Sent to", len([a for a in to.split(",") if a.strip()]), "address(es).")


if __name__ == "__main__":
    main()
