# Cloud-Routine „Ticketradar Electric Callboy Dortmund 27.02.2027“

Routine-ID: `trig_01F1pjy5hTE5t1RMUru2AiJb` · Zeitplan: stündlich `0 4-21 * * *` UTC (06–23 Uhr Berlin im Sommer,
05–22 Uhr im Winter) · frische Claude-Code-Session je Lauf · Benachrichtigung Push + E-Mail über Claude,
sobald die Abschlussnachricht mit „🎫 NEUES TICKET-ANGEBOT“ beginnt.

Anhalten/ändern: claude.ai/code → Routines, oder Claude bitten („Ticketradar-Routine pausieren“).

## Gedächtnis: Datenbank der Übersichtsseite

Frische Routine-Sessions dürfen nicht in dieses Repo pushen (Git-Proxy: Repo nicht in den Session-Quellen).
Deshalb liegt der Zustand in der Datenbank des Artifacts
https://claude.ai/code/artifact/659fda24-43ab-4fed-bd4c-495beca0298a – die Seite zeigt ihn live an.

| Collection / Dokument | Inhalt |
|---|---|
| `hits/<id>` | ein gefundenes Inserat: `url, source, title, price, price_text, per_ticket, section, count, rating, kind, reasons[], first_seen, reported` |
| `runs/<YYYYMMDD-HHMM>` | ein Lauf: `at, mode (script\|websearch), exit_code, searched, new_hits, note` |
| `meta/status` | `last_run_at, mode, runs, last_new_hits` |

`id` = `ka-<Anzeigen-ID>` (Kleinanzeigen), `ebay-<Artikelnummer>`, sonst `web-<sha1(url)[:12]>`.
`rating` ∈ TOP · OK · PREIS_UNKLAR · ZU_TEUER · OBERRANG; gemeldet (Push) wird nur `reported = true`.

## Prompt der Routine

```
Du bist der Ticketradar für Mike. Ziel: 2 Tickets für Electric Callboy, Westfalenhalle Dortmund, Sa. 27.02.2027
(Tanzneid World Tour), bevorzugt Innenraum, max. 130 €/Ticket (Ziel 100–120 €); Sitzplatz unten
(Unter-/Mittelrang) max. 125 €/Ticket; Oberrang uninteressant. Gesuche ("Suche", "gesucht") ignorieren.
Antworte auf Deutsch. Arbeite ohne Rückfragen. Nie kaufen, bieten oder Verkäufer anschreiben – nur informieren.

Gedächtnis ist die Datenbank des Artifacts https://claude.ai/code/artifact/659fda24-43ab-4fed-bd4c-495beca0298a
(Artifact-Tool, action read_db / write_db). Collections: "hits" (gefundene Angebote), "runs" (Lauf-Protokoll),
Dokument "meta/status". Kein Git-Push (nicht erlaubt), kein Pull Request.

Schritte:
1. Skript holen (nur lesen): falls /home/user/Claude-code fehlt: git clone
   https://github.com/mikeschneider666/Claude-code.git /home/user/Claude-code ; dann cd /home/user/Claude-code &&
   git fetch origin claude/electric-call-boy-ticket-radar-hze1ul &&
   git checkout -B radar origin/claude/electric-call-boy-ticket-radar-hze1ul
2. cd ticketradar && pip install -q -r requirements.txt ; python3 ticketradar.py --dry-run --print ; Exit-Code merken.
   - Exit 0: Portale direkt erreichbar, Modus "script". Alle Zeilen mit Bewertung TOP, OK, PREIS_UNKLAR,
     VERHANDELBAR sind Kandidaten (URL, Quelle, Preis, Titel stehen in der Zeile). Schritt 3 überspringen.
   - Exit 3: Portale gesperrt, Modus "websearch" → Schritt 3.
3. WebSearch-Fallback, genau eine Suche je Zeile:
   - site:kleinanzeigen.de electric callboy dortmund
   - site:kleinanzeigen.de electric callboy westfalenhalle
   - site:kleinanzeigen.de "electric callboy" 27.02.2027
   - site:ebay.de electric callboy dortmund ticket
   - electric callboy dortmund 27.02.2027 ticket innenraum verkaufe
   Kandidaten sind nur Ergebnisse, deren URL ein einzelnes Inserat ist (kleinanzeigen.de/s-anzeige/…,
   ebay.de/itm/…, Angebotsseiten von fansale.de, ticketswap.de, tixel.com) und deren Titel/Snippet Dortmund,
   Westfalenhalle oder 27.02.2027 nennt und kein Gesuch ist. Kategorie- und Suchseiten (…/k0…,
   /s-eintrittskarten-tickets/…, /s-konzerte/…, /b/…) zählen nie.
4. Datenbank lesen: read_db, db_op "list", collection "hits", query {"limit": 1000}. Ein Kandidat ist NEU,
   wenn seine URL in keinem vorhandenen Dokument (Feld url) steht.
5. Bewertung je neuem Kandidaten: Preis (bei "2 Tickets 240 €" gilt per_ticket 120), Kategorie section:
   "innenraum" | "sitzplatz_unten" | "oberrang" | "unbekannt", Anzahl count, rating: "TOP" (per_ticket ≤ 120
   bzw. ≤ 115 Sitzplatz), "OK" (≤ 130 bzw. ≤ 125), "PREIS_UNKLAR" (kein Preis erkennbar), "ZU_TEUER"
   (darüber), "OBERRANG". reported = true für TOP/OK/PREIS_UNKLAR, sonst false. Bei eBay kind: "Auktion"
   oder "Sofort-Kaufen" (oder "eBay").
6. Datenbank schreiben mit EINEM write_db db_op "batch":
   - je neuem Kandidaten: op "set", collection "hits", doc_id = "ka-<Anzeigen-ID>" für Kleinanzeigen,
     "ebay-<Artikelnummer>" für eBay, sonst "web-<12 Hex-Zeichen von sha1(url)>"; data {url, source
     ("Kleinanzeigen"|"eBay"|"fanSALE"|"TicketSwap"|"Tixel"), title, price (Zahl oder null), price_text,
     per_ticket (Zahl oder null), section, count (Zahl oder null), rating, kind, reasons (Liste kurzer Strings),
     first_seen (ISO-UTC jetzt), reported (bool)}.
   - op "set", collection "runs", doc_id = "<YYYYMMDD-HHMM UTC>", data {at (ISO-UTC), mode
     ("script"|"websearch"), exit_code, searched (Anzahl Kandidaten insgesamt), new_hits (Anzahl neue mit
     reported=true), note (ein Satz)}.
   - op "update", collection "meta", doc_id "status", data {last_run_at (ISO-UTC), mode, runs: <bisheriger Wert
     aus read_db get meta/status + 1>, last_new_hits}.
7. Abschlussnachricht:
   - Bei mindestens einem neuen Kandidaten mit reported=true beginnt sie mit "🎫 NEUES TICKET-ANGEBOT" und
     enthält pro Treffer: rating, Quelle, Kategorie, Preis/Ticket, Anzahl, Link und für Kleinanzeigen die fertige
     Nachricht an den Verkäufer aus ticketradar/config.json (notify.message_to_seller, {count} und {price}
     ausfüllen); bei eBay "Auktion" oder "Sofort-Kaufen" nennen. Nur dann soll Mike eine Push-Benachrichtigung
     bekommen.
   - Sonst lautet sie exakt: "Ticketradar: nichts Neues." Wenn Schritt 4 oder 6 gescheitert ist, stattdessen
     "Ticketradar: Fehler – <Fehlertext>".
```
