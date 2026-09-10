# 🎫 Ticketradar – Electric Callboy, Westfalenhalle Dortmund, Sa. 27.02.2027

Sucht regelmäßig auf **Kleinanzeigen**, **eBay**, **Eventim fanSALE**, **TicketSwap** und **Tixel**
nach Ticket-Angeboten für das ausverkaufte Konzert und schickt bei jedem neuen, passenden
Angebot eine **Push-Nachricht aufs Handy** – inklusive Link und einer fertigen Nachricht an
den Verkäufer zum Kopieren.

**Das Radar kauft nichts, bietet nicht und schreibt niemanden an.** Es informiert nur.

## Suchkriterien (config.json)

| Kriterium | Wert |
|---|---|
| Konzert | Electric Callboy, Tanzneid World Tour, Westfalenhalle Dortmund, 27.02.2027, 19:00 |
| Originalpreise (Eventim) | Innenraum 99,99 € · Mittelrang 95,60 € · Oberrang 90,10 € |
| Gesucht | 2 Tickets, bevorzugt Innenraum |
| Innenraum | Ziel ≤ 120 €/Ticket, Limit **130 €** |
| Sitzplatz unten (Unter-/Mittelrang) | Ziel ≤ 115 €/Ticket, Limit **125 €** |
| Oberrang | nicht interessant (wird geloggt, kein Push) |
| Preis „VB“ / unklar | Push mit Hinweis „Preis unklar“ |
| Gesuche („Suche 2 Tickets…“) | werden ausgefiltert |

Bewertung in der Push-Nachricht: `TOP` (≤ Zielpreis) · `OK` (≤ Limit) · `VERHANDELBAR` (VB, bis 25 % über Limit) ·
`PREIS_UNKLAR`. Bei eBay steht zusätzlich **Auktion** oder **Sofort-Kaufen** dabei – du entscheidest selbst.

## Warum ein Skript auf deinem Rechner und nicht nur in der Cloud?

Die Cloud-Umgebung von Claude Code darf per Netzwerkrichtlinie **keine** Verbindung zu
kleinanzeigen.de, ebay.de, fansale.de, ticketswap.de oder tixel.com aufbauen (alle Anfragen
werden vom Egress-Proxy mit 403 abgewiesen). Deshalb gibt es zwei Betriebsarten:

1. **Lokal (empfohlen, Echtzeit):** Dieses Skript läuft auf deinem Mac/PC alle 10 Minuten
   und liest die Portale direkt. Push kommt per ntfy-App.
2. **Cloud-Zeitplan (Fallback, schon aktiv):** Eine Claude-Routine läuft stündlich (6–23 Uhr),
   sucht über die Websuche nach neuen Inseraten (Suchindex, also mit Verzögerung) und schickt
   bei Treffern eine Push-/E-Mail-Benachrichtigung über Claude. Sobald du in der Umgebung
   die Netzwerkrichtlinie auf „unrestricted“ stellst (claude.ai/code → Environment →
   Network access), führt die Routine automatisch das Skript aus und arbeitet in Echtzeit.

## Einrichtung lokal (5 Minuten)

### 1. Push-App
* **ntfy** installieren (iOS/Android, kostenlos): https://ntfy.sh
* In der App **„Subscribe to topic“** → Topic eingeben: **`ecb-dortmund-2027-08582309`**
  (steht in `config.json` unter `notify.ntfy_topic`; du kannst es jederzeit ändern – das Topic
  ist dein „Passwort“, also nicht weitergeben).

### 2. Skript
```bash
git clone https://github.com/mikeschneider666/Claude-code.git
cd Claude-code/ticketradar
pip3 install -r requirements.txt
python3 ticketradar.py --test-push      # Test-Push aufs Handy
python3 ticketradar.py --dry-run --print   # zeigt alle aktuellen Inserate mit Bewertung
python3 ticketradar.py                  # scharfer Lauf: Push bei neuen Treffern
```

### 3. Automatisch alle 10 Minuten

**Mac (launchd):**
```bash
sed "s#__RADAR_DIR__#$(pwd)#g" de.mikeschneider.ticketradar.plist > ~/Library/LaunchAgents/de.mikeschneider.ticketradar.plist
launchctl load ~/Library/LaunchAgents/de.mikeschneider.ticketradar.plist
# Stoppen: launchctl unload ~/Library/LaunchAgents/de.mikeschneider.ticketradar.plist
```

**Linux / Mac (cron):**
```bash
crontab -e
*/10 * * * * cd /PFAD/ZU/Claude-code/ticketradar && /usr/bin/python3 ticketradar.py >> state/cron.log 2>&1
```

**Windows (PowerShell als Admin):**
```powershell
$a = New-ScheduledTaskAction -Execute "python" -Argument "ticketradar.py" -WorkingDirectory "C:\Pfad\zu\Claude-code\ticketradar"
$t = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName "Ticketradar" -Action $a -Trigger $t
```

**Oder einfach im Vordergrund laufen lassen:** `python3 ticketradar.py --loop 600`

## Was passiert bei einem Treffer?

Push-Nachricht, z. B.:

```
TOP · Kleinanzeigen · Innenraum · 120 €/Ticket
Electric Callboy 2 Tickets Innenraum Dortmund 27.02.2027
Preis: 240 € VB  |  Typ: Kleinanzeige  |  44137 Dortmund
Hinweise: 240 € gesamt ÷ 2 = 120 €/Ticket (geschätzt); ≤ Zielpreis 120 €; 2 Tickets
https://www.kleinanzeigen.de/s-anzeige/...

Nachricht an Verkäufer (kopieren):
Hallo! Ich habe großes Interesse an den 2 Tickets für Electric Callboy am 27.02.2027 ...
```

Tippen auf die Nachricht öffnet das Inserat direkt. Nachricht kopieren, bei Kleinanzeigen
„Nachricht schreiben“, einfügen, senden – unter 30 Sekunden.

### Warum schreibt das Radar den Verkäufer nicht selbst an?
* Dafür müsste dein Kleinanzeigen-Login im Klartext auf dem Rechner bzw. in der Cloud liegen.
* Automatisierte Zugriffe/Nachrichten verstoßen gegen die Kleinanzeigen-Nutzungsbedingungen;
  das Konto kann gesperrt werden – dann ist der Kauf weg.
* Die vorformulierte Nachricht macht dich fast genauso schnell, ohne dieses Risiko.

## Sicherheit beim Kauf (kurz)
* Nur **PayPal „Waren & Dienstleistungen“** oder Abholung/Übergabe; nie „Freunde & Familie“, nie Überweisung vorab.
* Bei Eventim-Tickets auf Ticketübertragung via Eventim-App (fanSALE/„Ticket weitergeben“) bestehen – dann ist das Ticket auf dich personalisiert.
* Screenshots von Tickets sind kein Nachweis; Barcodes können mehrfach verkauft werden.

## Dateien
| Datei | Zweck |
|---|---|
| `ticketradar.py` | das Radar |
| `config.json` | Suchkriterien, Preislimits, Quellen, Push-Topic, Verkäufer-Nachricht |
| `state/seen.json` | bereits gemeldete Angebote (damit nichts doppelt kommt) |
| `state/radar.log` | Protokoll |
| `ROUTINE.md` | Prompt der stündlichen Cloud-Routine |
| `de.mikeschneider.ticketradar.plist` | launchd-Vorlage für den Mac |

## Bekannte Grenzen
* Die HTML-Parser für Kleinanzeigen und eBay sind gegen nachgebaute Seiten getestet, nicht gegen
  die Live-Seiten (aus der Cloud nicht erreichbar). Wenn `--dry-run --print` lokal **0 Inserate**
  zeigt, obwohl es welche gibt, hat sich das Seitenlayout geändert → Selektoren in
  `scrape_kleinanzeigen` / `scrape_ebay` anpassen (oder mir Bescheid geben).
* fanSALE, TicketSwap und Tixel laden viel per JavaScript; dort meldet das Radar nur, **dass** sich
  bei Dortmund-Angeboten/Preisen etwas geändert hat (Best-Effort), nicht jedes einzelne Ticket.
* Preis pro Ticket wird geschätzt: Steht „2 Tickets … 240 €“, wird 120 €/Ticket angenommen.
