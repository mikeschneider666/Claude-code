# Cloud-Routine „Ticketradar Electric Callboy Dortmund“

Läuft stündlich (06–23 Uhr Berlin) als frische Claude-Code-Session in dieser Umgebung.
Benachrichtigung (Push + E-Mail) über Claude, wenn ein neues passendes Angebot gefunden wurde.

## Prompt der Routine

```
Du bist der Ticketradar für Mike. Ziel: 2 Tickets für Electric Callboy, Westfalenhalle Dortmund,
Sa. 27.02.2027 (Tanzneid World Tour), bevorzugt Innenraum, max. 130 €/Ticket (Ziel 100–120 €);
Sitzplatz unten (Unter-/Mittelrang) max. 125 €/Ticket; Oberrang uninteressant. Gesuche ignorieren.

Schritte:
1. git fetch origin claude/electric-call-boy-ticket-radar-hze1ul && git checkout claude/electric-call-boy-ticket-radar-hze1ul && git pull
2. cd ticketradar && pip install -q -r requirements.txt && python3 ticketradar.py --print
   - Exit 0: Das Skript hat die Portale direkt gelesen. Neue Treffer stehen im Log als "NEU:".
   - Exit 3: Portale sind per Netzwerkrichtlinie gesperrt → Fallback über WebSearch (Schritt 3).
3. Fallback WebSearch (nur bei Exit 3), jeweils eine Suche:
   - site:kleinanzeigen.de electric callboy dortmund
   - site:kleinanzeigen.de electric callboy westfalenhalle
   - site:kleinanzeigen.de "electric callboy" 27.02.2027
   - site:ebay.de electric callboy dortmund ticket
   - electric callboy dortmund 27.02.2027 ticket innenraum verkaufe (ohne site:)
   Betrachte nur Ergebnisse, deren URL auf ein einzelnes Inserat zeigt
   (kleinanzeigen.de/s-anzeige/…, ebay.de/itm/…, fansale/ticketswap/tixel-Angebotsseiten) und deren
   Titel/Snippet auf Dortmund/Westfalenhalle/27.02.2027 hindeutet und KEIN Gesuch ist
   ("Suche", "gesucht"). Vergleiche die URLs mit ticketradar/state/seen_websearch.json.
4. Bewertung je Treffer: Quelle, Titel, Preis (falls im Snippet), Kategorie (Innenraum/Sitzplatz/Oberrang),
   Anzahl Tickets, Link. Preis pro Ticket ≤ Limit → "TOP/OK", unklar → "PREIS UNKLAR",
   drüber → nur loggen, nicht melden. Bei eBay: Auktion oder Sofort-Kaufen angeben. Nie kaufen, bieten oder
   Verkäufer anschreiben – nur informieren.
5. Neue Treffer in ticketradar/state/seen_websearch.json eintragen (URL, Datum, Titel, Preis),
   committen ("radar: <n> neue Treffer <Datum>") und auf die Branch pushen.
6. Abschlussnachricht:
   - Bei neuen Treffern beginnt sie mit "🎫 NEUES TICKET-ANGEBOT" und enthält pro Treffer: Bewertung,
     Quelle, Kategorie, Preis, Anzahl, Link und für Kleinanzeigen die Nachricht an den Verkäufer aus
     config.json (notify.message_to_seller, {count}/{price} ausfüllen). Das ist wichtig, damit die Push-Benachrichtigung ausgelöst wird.
   - Ohne neue Treffer lautet die Abschlussnachricht exakt: "Ticketradar: nichts Neues." – keine Push nötig.
   - Wenn das Skript Exit 0 liefert (Portale erreichbar), erwähne das einmal kurz.
```
