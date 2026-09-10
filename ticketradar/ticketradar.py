#!/usr/bin/env python3
"""
Ticketradar – sucht regelmäßig nach Ticket-Angeboten für ein bestimmtes Konzert
(Standard: Electric Callboy, Westfalenhalle Dortmund, 27.02.2027) auf
Kleinanzeigen, eBay und weiteren Portalen und schickt bei neuen passenden
Angeboten eine Push-Nachricht (ntfy.sh) – inkl. vorformulierter Nachricht an
den Verkäufer.

Das Skript AGIERT NIE selbst (kein Kauf, kein Gebot, keine Nachricht an
Verkäufer). Es informiert nur.

Aufruf:
    python3 ticketradar.py                 # ein Durchlauf, Push bei neuen Treffern
    python3 ticketradar.py --dry-run       # ohne Push, ohne Speichern
    python3 ticketradar.py --print         # alle aktuellen Treffer ausgeben
    python3 ticketradar.py --loop 600      # alle 600 s wiederholen (Dauerbetrieb)
    python3 ticketradar.py --test-push     # Test-Push an das ntfy-Topic

Exit-Codes: 0 ok, 3 = Netzwerk zu allen Portalen blockiert (Egress-Sperre).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("Bitte zuerst: pip install -r requirements.txt")

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
STATE_PATH = HERE / "state" / "seen.json"
LOG_PATH = HERE / "state" / "radar.log"


# --------------------------------------------------------------------------- #
# Hilfsfunktionen
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


NUM = r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?"
PRICE_RE = re.compile(rf"(?:€|eur)\s*({NUM})|({NUM})\s*(?:€|eur)", re.I)
COUNT_RE = re.compile(
    r"(?:(\d)\s*(?:x|×|stk|stück|tickets?|karten)|(zwei|two)\s*(?:tickets?|karten)|(ein|eine|1)\s*(?:ticket|karte)\b)",
    re.I,
)


def parse_price(text: str) -> float | None:
    """Erste Euro-Angabe im Text, z. B. '120 €', 'EUR 230,00', '1.200,50 €', '2 x 110€'."""
    if not text:
        return None
    m = PRICE_RE.search(text.replace("\xa0", " "))
    if not m:
        return None
    raw = m.group(1) or m.group(2) or ""
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", raw):
        raw = raw.replace(".", "")
    raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def price_text_of(*texts: str) -> str:
    for t in texts:
        m = PRICE_RE.search((t or "").replace("\xa0", " "))
        if m:
            return m.group(0).strip()
    return ""


def parse_count(text: str) -> int | None:
    t = (text or "").lower()
    m = COUNT_RE.search(t)
    if not m:
        return None
    if m.group(1):
        return int(m.group(1))
    if m.group(2):
        return 2
    if m.group(3):
        return 1
    return None


def classify_section(text: str) -> str:
    """innenraum | sitzplatz_unten | oberrang | unbekannt"""
    t = (text or "").lower()
    if any(w in t for w in ("innenraum", "stehplatz", "steh-platz", "standing", "front of stage", "fos", "wellenbrecher")):
        return "innenraum"
    if any(w in t for w in ("oberrang", "obere", "hinten oben", "kategorie 3", "kat 3", "kat. 3", "kat.3")):
        return "oberrang"
    if any(w in t for w in ("unterrang", "mittelrang", "sitzplatz", "sitzplätze", "sitzplaetze", "block", "reihe", "row", "tribüne", "tribuene", "kategorie 1", "kategorie 2", "kat 1", "kat 2", "kat. 1", "kat. 2")):
        return "sitzplatz_unten"
    return "unbekannt"


def contains_any(text: str, words: list[str]) -> bool:
    t = text.lower()
    return any(w.lower() in t for w in words)


def item_id(source: str, raw_id: str) -> str:
    return f"{source}:{raw_id}"


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
class Blocked(Exception):
    pass


class Http:
    def __init__(self, cfg: dict):
        self.s = requests.Session()
        self.s.headers.update(
            {
                "User-Agent": cfg["http"]["user_agent"],
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
                "Cache-Control": "no-cache",
            }
        )
        self.timeout = cfg["http"]["timeout_seconds"]
        self.delay = cfg["http"]["delay_between_requests_seconds"]
        self.blocked = 0
        self.ok = 0

    def get(self, url: str) -> str:
        try:
            r = self.s.get(url, timeout=self.timeout)
        except requests.exceptions.ProxyError as e:
            self.blocked += 1
            raise Blocked(f"Proxy/Egress blockiert: {url} ({e.__class__.__name__})")
        except requests.exceptions.RequestException as e:
            raise Blocked(f"Netzwerkfehler: {url} ({e.__class__.__name__}: {e})")
        finally:
            time.sleep(self.delay)
        if r.status_code in (403, 429, 503):
            self.blocked += 1
            raise Blocked(f"HTTP {r.status_code} (Bot-Schutz/Sperre?) für {url}")
        r.raise_for_status()
        self.ok += 1
        return r.text


# --------------------------------------------------------------------------- #
# Quellen
# --------------------------------------------------------------------------- #
def scrape_kleinanzeigen(http: Http, cfg: dict) -> list[dict]:
    """Suchergebnisseiten von kleinanzeigen.de (neueste zuerst)."""
    items: list[dict] = []
    if BeautifulSoup is None:
        log("kleinanzeigen: beautifulsoup4 fehlt – pip install -r requirements.txt")
        return items
    for url in cfg["sources"]["kleinanzeigen"]["urls"]:
        try:
            html = http.get(url)
        except Blocked as e:
            log(f"kleinanzeigen: {e}")
            continue
        soup = BeautifulSoup(html, "html.parser")
        ads = soup.select("article.aditem[data-adid]") or soup.select("li.ad-listitem article")
        for ad in ads:
            adid = ad.get("data-adid") or ""
            href = ad.get("data-href") or ""
            a = ad.select_one("a.ellipsis") or ad.select_one("h2 a") or ad.find("a", href=re.compile(r"/s-anzeige/"))
            if a and not href:
                href = a.get("href", "")
            if not adid:
                m = re.search(r"/(\d{6,})-\d+-\d+", href)
                adid = m.group(1) if m else hashlib.md5(href.encode()).hexdigest()[:12]
            if href.startswith("/"):
                href = "https://www.kleinanzeigen.de" + href
            title = (a.get_text(" ", strip=True) if a else "").strip()
            price_el = ad.select_one(".aditem-main--middle--price-shipping--price") or ad.select_one("[class*='price']")
            price_txt = price_el.get_text(" ", strip=True) if price_el else ""
            loc_el = ad.select_one(".aditem-main--top--left")
            loc = loc_el.get_text(" ", strip=True) if loc_el else ""
            desc_el = ad.select_one(".aditem-main--middle--description") or ad.select_one("p")
            desc = desc_el.get_text(" ", strip=True) if desc_el else ""
            tags = " ".join(t.get_text(" ", strip=True) for t in ad.select(".simpletag, .text-light"))
            is_wanted = "gesuch" in tags.lower()
            items.append(
                {
                    "id": item_id("kleinanzeigen", adid),
                    "source": "Kleinanzeigen",
                    "title": title,
                    "url": href,
                    "price_text": price_txt,
                    "price": parse_price(price_txt),
                    "negotiable": "vb" in price_txt.lower(),
                    "location": loc,
                    "text": f"{title} {desc} {tags}",
                    "is_wanted": is_wanted,
                    "kind": "Kleinanzeige",
                }
            )
        log(f"kleinanzeigen: {len(ads)} Inserate auf {url}")
    return items


def scrape_ebay(http: Http, cfg: dict) -> list[dict]:
    """eBay-Suche: erst RSS (robust), sonst HTML. Unterscheidet Auktion / Sofort-Kaufen."""
    items: list[dict] = []
    for q in cfg["sources"]["ebay"]["queries"]:
        base = f"https://www.ebay.de/sch/i.html?_nkw={quote_plus(q)}&_sop=10&LH_PrefLoc=1"
        got = False
        # 1) RSS
        try:
            xml = http.get(base + "&_rss=1")
            root = ET.fromstring(xml.encode("utf-8", "ignore"))
            for it in root.iter("item"):
                link = (it.findtext("link") or "").strip()
                title = (it.findtext("title") or "").strip()
                desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
                m = re.search(r"/itm/(?:[^/]+/)?(\d{9,})", link)
                raw = m.group(1) if m else hashlib.md5(link.encode()).hexdigest()[:12]
                lower = (title + " " + desc).lower()
                kind = "Auktion" if ("gebot" in lower or "auktion" in lower) else ("Sofort-Kaufen" if "sofort" in lower else "eBay (Typ unklar)")
                items.append(
                    {
                        "id": item_id("ebay", raw),
                        "source": "eBay",
                        "title": title,
                        "url": link.split("?")[0],
                        "price_text": price_text_of(desc, title),
                        "price": parse_price(desc) or parse_price(title),
                        "negotiable": "preisvorschlag" in lower,
                        "location": "",
                        "text": f"{title} {desc}",
                        "is_wanted": False,
                        "kind": kind,
                    }
                )
                got = True
        except (Blocked, ET.ParseError) as e:
            log(f"ebay rss: {e}")
        if got:
            log(f"ebay: RSS ok für '{q}'")
            continue
        # 2) HTML
        if BeautifulSoup is None:
            continue
        try:
            html = http.get(base)
        except Blocked as e:
            log(f"ebay html: {e}")
            continue
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select("li.s-item, li.s-card, div.s-item")
        for c in cards:
            a = c.select_one("a.s-item__link, a[href*='/itm/']")
            if not a:
                continue
            link = a.get("href", "")
            m = re.search(r"/itm/(?:[^/]+/)?(\d{9,})", link)
            if not m:
                continue
            title_el = c.select_one(".s-item__title, .s-card__title, [role=heading]")
            title = title_el.get_text(" ", strip=True) if title_el else a.get_text(" ", strip=True)
            if title.lower().startswith("shop on ebay"):
                continue
            price_el = c.select_one(".s-item__price, .s-card__price")
            price_txt = price_el.get_text(" ", strip=True) if price_el else ""
            all_txt = c.get_text(" ", strip=True)
            lower = all_txt.lower()
            if "gebot" in lower:
                kind = "Auktion"
            elif "sofort-kaufen" in lower or "sofort kaufen" in lower:
                kind = "Sofort-Kaufen"
            else:
                kind = "eBay (Typ unklar)"
            items.append(
                {
                    "id": item_id("ebay", m.group(1)),
                    "source": "eBay",
                    "title": title,
                    "url": link.split("?")[0],
                    "price_text": price_txt,
                    "price": parse_price(price_txt),
                    "negotiable": "preisvorschlag" in lower,
                    "location": "",
                    "text": all_txt,
                    "is_wanted": False,
                    "kind": kind,
                }
            )
        log(f"ebay: {len(cards)} Karten (HTML) für '{q}'")
    return items


def watch_pages(http: Http, cfg: dict) -> list[dict]:
    """Best-effort-Beobachtung von Seiten (fanSALE, TicketSwap, Tixel):
    meldet, sobald auf der Seite ein Dortmund-Bezug UND Preise auftauchen bzw.
    sich der gefundene Preisblock ändert."""
    items: list[dict] = []
    for page in cfg["sources"]["page_watch"]["pages"]:
        try:
            html = http.get(page["url"])
        except Blocked as e:
            log(f"page_watch {page['name']}: {e}")
            continue
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        lower = text.lower()
        if page.get("must_contain") and not contains_any(lower, page["must_contain"]):
            log(f"page_watch {page['name']}: kein Dortmund-Bezug auf der Seite")
            continue
        # Preise in der Nähe von "dortmund" einsammeln
        prices: list[float] = []
        for m in re.finditer(r"dortmund", lower):
            window = text[max(0, m.start() - 400): m.end() + 600]
            prices += [p for p in (parse_price(x.group(0)) for x in PRICE_RE.finditer(window)) if p]
        prices = sorted(set(prices))
        sig = hashlib.md5(json.dumps(prices).encode()).hexdigest()[:10]
        items.append(
            {
                "id": item_id("page", re.sub(r"\W+", "-", page["name"].lower())),
                "source": page["name"],
                "title": f"{page['name']}: Dortmund-Angebote sichtbar" + (f", Preise ab {min(prices):.0f} €" if prices else ""),
                "url": page["url"],
                "price_text": ", ".join(f"{p:.0f} €" for p in prices[:8]),
                "price": min(prices) if prices else None,
                "negotiable": False,
                "location": "",
                "text": "dortmund innenraum " + " ".join(f"{p} €" for p in prices),
                "is_wanted": False,
                "kind": "Portal",
                "signature": sig,
            }
        )
        log(f"page_watch {page['name']}: {len(prices)} Preise gefunden")
    return items


# --------------------------------------------------------------------------- #
# Bewertung
# --------------------------------------------------------------------------- #
def evaluate(item: dict, cfg: dict) -> dict:
    kw = cfg["keywords"]
    wanted = cfg["wanted"]
    text = f"{item['title']} {item.get('text','')}".lower()
    reasons: list[str] = []

    relevant = contains_any(text, kw["must_contain_any"]) and contains_any(text, kw["must_contain_any_of_event"])
    if item["source"] not in ("Kleinanzeigen", "eBay"):
        relevant = True  # page_watch hat schon gefiltert
    if not relevant:
        return {**item, "relevant": False, "rating": "IRRELEVANT", "reasons": ["kein Bezug zu Dortmund/27.02."]}
    if item.get("is_wanted") or contains_any(item["title"].lower(), kw["exclude_wanted_ads"]):
        return {**item, "relevant": False, "rating": "GESUCH", "reasons": ["Gesuch, kein Angebot"]}
    if contains_any(text, kw["exclude_other_cities"]) and not contains_any(item["title"].lower(), ["dortmund", "westfalenhalle"]):
        return {**item, "relevant": False, "rating": "ANDERE_STADT", "reasons": ["vermutlich andere Stadt"]}

    section = classify_section(text)
    count = parse_count(text)
    price = item.get("price")
    per_ticket = price
    if price is not None and count and count >= 2 and price >= 1.6 * cfg["event"]["original_prices_eur"]["oberrang"]:
        per_ticket = round(price / count, 2)
        reasons.append(f"{price:.0f} € gesamt ÷ {count} = {per_ticket:.0f} €/Ticket (geschätzt)")

    cap_key = section if section in ("innenraum", "sitzplatz_unten", "oberrang") else None
    cap = wanted["max_price_per_ticket"].get(cap_key) if cap_key else max(wanted["max_price_per_ticket"].values())
    target = wanted["target_price_per_ticket"].get(cap_key or "innenraum", 120)

    if section == "oberrang":
        rating = "OBERRANG"
        reasons.append("Oberrang – nicht gewünscht")
    elif per_ticket is None:
        rating = "PREIS_UNKLAR" if wanted["notify_unknown_price"] else "IGNORIERT"
        reasons.append("kein Preis erkennbar / VB")
    elif per_ticket <= target:
        rating = "TOP"
        reasons.append(f"≤ Zielpreis {target:.0f} €")
    elif per_ticket <= cap:
        rating = "OK"
        reasons.append(f"≤ Limit {cap:.0f} €")
    elif item.get("negotiable") and per_ticket <= cap * 1.25:
        rating = "VERHANDELBAR"
        reasons.append(f"über Limit, aber VB ({per_ticket:.0f} €)")
    else:
        rating = "ZU_TEUER"
        reasons.append(f"{per_ticket:.0f} €/Ticket > Limit {cap:.0f} €")

    if count == 1:
        reasons.append("nur 1 Ticket?")
    elif count and count >= 2:
        reasons.append(f"{count} Tickets")

    return {
        **item,
        "relevant": True,
        "section": section,
        "count": count,
        "per_ticket": per_ticket,
        "rating": rating,
        "reasons": reasons,
    }


NOTIFY_RATINGS = {"TOP", "OK", "PREIS_UNKLAR", "VERHANDELBAR"}
SECTION_LABEL = {"innenraum": "Innenraum", "sitzplatz_unten": "Sitzplatz", "oberrang": "Oberrang", "unbekannt": "Kategorie unklar"}


# --------------------------------------------------------------------------- #
# Push
# --------------------------------------------------------------------------- #
def seller_message(item: dict, cfg: dict) -> str:
    tpl = cfg["notify"]["message_to_seller"]
    price = f"{item['price']:.0f} €" if item.get("price") else "Ihrem Preis"
    count = item.get("count") or cfg["wanted"]["tickets_needed"]
    return tpl.format(count=count, price=price)


def format_item(item: dict, cfg: dict, with_message: bool = True) -> tuple[str, str]:
    sec = SECTION_LABEL.get(item.get("section", "unbekannt"), "?")
    pt = f"{item['per_ticket']:.0f} €/Ticket" if item.get("per_ticket") else (item.get("price_text") or "Preis?")
    title = f"{item['rating']} · {item['source']} · {sec} · {pt}"
    lines = [
        item["title"],
        f"Preis: {item.get('price_text') or '?'}  |  Typ: {item.get('kind','')}  |  {item.get('location','')}".strip(),
        "Hinweise: " + "; ".join(item.get("reasons", [])),
        item["url"],
    ]
    if with_message and item["source"] == "Kleinanzeigen":
        lines += ["", "Nachricht an Verkäufer (kopieren):", seller_message(item, cfg)]
    if item["source"] == "eBay":
        lines.append("eBay: nur Info – " + ("Auktion läuft, ggf. bieten." if item["kind"] == "Auktion" else "Sofort-Kaufen möglich, selbst entscheiden."))
    return title, "\n".join(lines)


def push(cfg: dict, title: str, body: str, url: str | None = None, priority: str = "high") -> bool:
    n = cfg["notify"]
    ok = False
    if n.get("ntfy_topic"):
        try:
            headers = {"Title": title.encode("latin-1", "replace").decode("latin-1"), "Priority": priority, "Tags": "ticket"}
            if url:
                headers["Click"] = url
                headers["Actions"] = f"view, Angebot öffnen, {url}".encode("latin-1", "replace").decode("latin-1")
            r = requests.post(f"{n['ntfy_server'].rstrip('/')}/{n['ntfy_topic']}", data=body.encode("utf-8"), headers=headers, timeout=15)
            ok = r.ok
            if not r.ok:
                log(f"ntfy: HTTP {r.status_code} {r.text[:120]}")
        except requests.exceptions.RequestException as e:
            log(f"ntfy: Fehler {e.__class__.__name__}: {e}")
    if n.get("webhook_url"):
        try:
            r = requests.post(n["webhook_url"], json={"title": title, "body": body, "url": url}, timeout=15)
            ok = ok or r.ok
        except requests.exceptions.RequestException as e:
            log(f"webhook: Fehler {e}")
    return ok


# --------------------------------------------------------------------------- #
# Hauptlogik
# --------------------------------------------------------------------------- #
def run_once(cfg: dict, dry_run: bool, print_all: bool) -> int:
    http = Http(cfg)
    found: list[dict] = []
    if cfg["sources"]["kleinanzeigen"]["enabled"]:
        found += scrape_kleinanzeigen(http, cfg)
    if cfg["sources"]["ebay"]["enabled"]:
        found += scrape_ebay(http, cfg)
    if cfg["sources"]["page_watch"]["enabled"]:
        found += watch_pages(http, cfg)

    if http.ok == 0 and http.blocked > 0:
        log("ALLE Portale blockiert (Egress/Bot-Schutz). Exit 3.")
        return 3

    seen = load_json(STATE_PATH, {})
    now = dt.datetime.now().isoformat(timespec="seconds")
    new_hits: list[dict] = []
    evaluated = [evaluate(i, cfg) for i in found]

    for it in evaluated:
        if print_all:
            print(f"  [{it['rating']:<12}] {it['source']:<14} {it.get('price_text','')!s:<12} {it['title'][:80]}  {it['url']}")
        if not it["relevant"] or it["rating"] not in NOTIFY_RATINGS:
            continue
        key = it["id"]
        prev = seen.get(key)
        sig = it.get("signature") or f"{it.get('price')}|{it['rating']}"
        if prev and prev.get("signature") == sig:
            continue
        if prev and it["source"] not in ("Kleinanzeigen", "eBay"):
            it["reasons"].append("Änderung auf der Seite (Preise/Angebote)")
        elif prev:
            it["reasons"].append(f"Preisänderung (vorher {prev.get('price_text')})")
        new_hits.append(it)
        seen[key] = {
            "first_seen": prev["first_seen"] if prev else now,
            "last_seen": now,
            "signature": sig,
            "title": it["title"],
            "price_text": it.get("price_text"),
            "rating": it["rating"],
            "url": it["url"],
        }

    # Alles Gesehene (auch Irrelevantes) registrieren, damit die Liste nicht wächst wie Unkraut? Nein: nur Treffer.
    log(f"{len(found)} Einträge geladen, {sum(1 for e in evaluated if e['relevant'])} relevant, {len(new_hits)} NEU")

    for it in new_hits:
        title, body = format_item(it, cfg)
        log("NEU: " + title + " – " + it["url"])
        if not dry_run:
            prio = "urgent" if it["rating"] == "TOP" else "high"
            push(cfg, title, body, it["url"], prio)
    if not dry_run:
        save_json(STATE_PATH, seen)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Ticketradar")
    ap.add_argument("--dry-run", action="store_true", help="nichts speichern, keinen Push senden")
    ap.add_argument("--print", action="store_true", help="alle geladenen Einträge mit Bewertung ausgeben")
    ap.add_argument("--loop", type=int, metavar="SEK", help="alle SEK Sekunden erneut prüfen")
    ap.add_argument("--test-push", action="store_true", help="Test-Push senden und beenden")
    ap.add_argument("--config", default=str(CONFIG_PATH))
    args = ap.parse_args()

    cfg = load_json(Path(args.config), None)
    if cfg is None:
        sys.exit(f"config nicht lesbar: {args.config}")

    if args.test_push:
        ok = push(cfg, "Ticketradar Test", f"Push funktioniert. Topic: {cfg['notify']['ntfy_topic']}", cfg["event"]["eventim_url"], "default")
        print("Push gesendet." if ok else "Push FEHLGESCHLAGEN (siehe Log).")
        return 0 if ok else 1

    while True:
        rc = run_once(cfg, args.dry_run, args.print)
        if not args.loop:
            return rc
        time.sleep(max(60, args.loop))


if __name__ == "__main__":
    sys.exit(main())
