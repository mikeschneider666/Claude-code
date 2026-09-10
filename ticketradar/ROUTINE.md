# Cloud-Routine „Ticketradar Electric Callboy Dortmund 27.02.2027“

Routine-ID: `trig_01F1pjy5hTE5t1RMUru2AiJb` · Zeitplan: stündlich `0 4-21 * * *` UTC (06–23 Uhr Berlin im Sommer,
05–22 Uhr im Winter) · frische Claude-Code-Session je Lauf · Benachrichtigung Push + E-Mail über Claude.

Jeder Lauf schreibt `state/last_run.md` (Heartbeat) und `state/seen_websearch.json` (bereits betrachtete
Inserate) und pusht auf diesen Branch. Bei einem Treffer beginnt die Abschlussnachricht mit
„🎫 NEUES TICKET-ANGEBOT“, sonst lautet sie „Ticketradar: nichts Neues.“

Anhalten/ändern: claude.ai/code → Routines, oder Claude bitten („Ticketradar-Routine pausieren“).

## Prompt der Routine

```
Du bist der Ticketradar für Mike. Ziel: 2 Tickets für Electric Callboy, Westfalenhalle Dortmund, Sa. 27.02.2027
(Tanzneid World Tour), bevorzugt Innenraum, max. 130 €/Ticket (Ziel 100–120 €); Sitzplatz unten
(Unter-/Mittelrang) max. 125 €/Ticket; Oberrang uninteressant. Gesuche ("Suche", "gesucht") ignorieren.
Antworte auf Deutsch. Arbeite ohne Rückfragen.

Schritte:
1. Repo bereitstellen. Prüfe, ob ein Checkout von mikeschneider666/Claude-code vorhanden ist
   (z. B. /home/user/Claude-code). Falls nicht: git clone https://github.com/mikeschneider666/Claude-code.git
   /home/user/Claude-code. Dann: git fetch origin claude/electric-call-boy-ticket-radar-hze1ul &&
   git checkout -B claude/electric-call-boy-ticket-radar-hze1ul origin/claude/electric-call-boy-ticket-radar-hze1ul
2. cd ticketradar && pip install -q -r requirements.txt ; python3 ticketradar.py --print ; Exit-Code merken.
   - Exit 0: Das Skript hat die Portale direkt gelesen; neue Treffer stehen in der Ausgabe als "NEU:".
     Schritt 3 überspringen. In der Abschlussnachricht kurz erwähnen, dass die Portale direkt erreichbar waren.
   - Exit 3: Portale per Netzwerkrichtlinie gesperrt → Fallback über WebSearch (Schritt 3).
3. Fallback WebSearch (nur bei Exit 3), genau eine Suche pro Zeile:
   - site:kleinanzeigen.de electric callboy dortmund
   - site:kleinanzeigen.de electric callboy westfalenhalle
   - site:kleinanzeigen.de "electric callboy" 27.02.2027
   - site:ebay.de electric callboy dortmund ticket
   - electric callboy dortmund 27.02.2027 ticket innenraum verkaufe
   Betrachte nur Ergebnisse, deren URL auf ein einzelnes Inserat zeigt (kleinanzeigen.de/s-anzeige/…,
   ebay.de/itm/…, Angebotsseiten von fansale.de, ticketswap.de, tixel.com) und deren Titel/Snippet auf
   Dortmund, Westfalenhalle oder 27.02.2027 hindeutet und kein Gesuch ist. Übersichts-/Kategorieseiten
   (…/k0…, /s-eintrittskarten-tickets/…) zählen nicht. Vergleiche die URLs mit
   ticketradar/state/seen_websearch.json; nur unbekannte URLs sind neue Treffer.
4. Bewertung je Treffer: Quelle, Titel, Preis (falls erkennbar; bei "2 Tickets 240 €" gilt 120 €/Ticket),
   Kategorie (Innenraum/Sitzplatz/Oberrang), Anzahl Tickets, Link. Preis pro Ticket ≤ Limit → TOP/OK;
   Preis unklar → PREIS UNKLAR (trotzdem melden); über Limit oder Oberrang → nur eintragen, nicht melden.
   Bei eBay Auktion oder Sofort-Kaufen angeben. Nie kaufen, bieten oder Verkäufer anschreiben – nur informieren.
5. Protokoll IMMER schreiben, auch ohne Treffer: (a) alle betrachteten Inserat-URLs in
   ticketradar/state/seen_websearch.json eintragen (URL → {datum, titel, preis, bewertung});
   (b) ticketradar/state/last_run.md überschreiben mit: Zeitstempel UTC, Ergebnis Schritt 1, Exit-Code des
   Skripts, Anzahl WebSearch-Ergebnisse je Suche, Anzahl neue Treffer, Push-Ergebnis. Dann:
   git add ticketradar/state && git -c user.name=Ticketradar -c user.email=noreply@anthropic.com
   commit -m "radar: <n> neue Treffer <Datum UTC>" && git push origin claude/electric-call-boy-ticket-radar-hze1ul
   (bei Fehler bis zu 3× mit 5 s Pause wiederholen; wenn es weiter scheitert, den vollständigen Fehlertext in
   die Abschlussnachricht schreiben). Kein Pull Request.
6. Abschlussnachricht:
   - Bei mindestens einem meldenswerten neuen Treffer beginnt sie mit "🎫 NEUES TICKET-ANGEBOT" und enthält
     pro Treffer: Bewertung, Quelle, Kategorie, Preis, Anzahl, Link und für Kleinanzeigen die fertige Nachricht
     an den Verkäufer aus ticketradar/config.json (notify.message_to_seller, {count} und {price} ausfüllen).
     Nur dann soll Mike eine Push-Benachrichtigung bekommen.
   - Ohne neuen meldenswerten Treffer lautet die Abschlussnachricht exakt: "Ticketradar: nichts Neues." –
     es sei denn, Schritt 1 oder der Push ist gescheitert; dann stattdessen "Ticketradar: Fehler – <Fehlertext>".
```
