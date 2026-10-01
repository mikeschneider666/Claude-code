#!/bin/bash
# Ticketradar – Installer für macOS/Linux
# Aufruf: curl -fsSL https://raw.githubusercontent.com/mikeschneider666/Claude-code/refs/heads/claude/electric-call-boy-ticket-radar-hze1ul/ticketradar/install-mac.sh | bash
set -e
BRANCH="claude/electric-call-boy-ticket-radar-hze1ul"
ZIP="https://github.com/mikeschneider666/Claude-code/archive/refs/heads/$BRANCH.zip"
DIR="$HOME/Ticketradar"
INTERVAL_SECONDS=900   # 15 Minuten

echo "[1/5] Python prüfen ..."
command -v python3 >/dev/null || { echo "python3 fehlt. Bitte von https://www.python.org/downloads/ installieren."; exit 1; }
python3 --version

echo "[2/5] Radar herunterladen ..."
TMP=$(mktemp -d)
curl -fsSL "$ZIP" -o "$TMP/radar.zip"
unzip -q "$TMP/radar.zip" -d "$TMP/src"
SRC=$(find "$TMP/src" -maxdepth 2 -type d -name ticketradar | head -1)
mkdir -p "$DIR"
rsync -a --exclude state "$SRC/" "$DIR/"
[ -f "$DIR/state/seen.json" ] || cp -R "$SRC/state" "$DIR/state"
echo "Installiert nach $DIR"

echo "[3/5] Abhängigkeiten ..."
python3 -m pip install -q -r "$DIR/requirements.txt" --user 2>/dev/null || python3 -m pip install -q -r "$DIR/requirements.txt" --break-system-packages

echo "[4/5] Test: Push aufs Handy und erster Suchlauf ..."
python3 "$DIR/ticketradar.py" --test-push
python3 "$DIR/ticketradar.py" --dry-run --print | tail -25

echo "[5/5] Automatischen Lauf einrichten ..."
if [ "$(uname)" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/de.mikeschneider.ticketradar.plist"
  sed -e "s#__RADAR_DIR__#$DIR#g" -e "s#/usr/bin/python3#$(command -v python3)#" -e "s#<integer>900</integer>#<integer>$INTERVAL_SECONDS</integer>#" "$DIR/de.mikeschneider.ticketradar.plist" > "$PLIST"
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "Fertig. Läuft alle $((INTERVAL_SECONDS/60)) Minuten (launchd). Stoppen: launchctl unload $PLIST"
else
  ( crontab -l 2>/dev/null | grep -v ticketradar.py ; echo "*/$((INTERVAL_SECONDS/60)) * * * * cd $DIR && $(command -v python3) ticketradar.py >> $DIR/state/cron.log 2>&1" ) | crontab -
  echo "Fertig. Läuft alle $((INTERVAL_SECONDS/60)) Minuten (cron). Stoppen: crontab -e, Zeile entfernen."
fi
echo "Protokoll: $DIR/state/radar.log"
