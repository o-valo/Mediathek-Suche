#!/usr/bin/env bash
# Einmalige Einrichtung der Mediathek-Suche.
#
# Prüft zunächst die System-Voraussetzungen (Python, venv-Modul, tmux/screen,
# curl) und zeigt bei fehlenden Paketen konkret die nötigen apt-Befehle an.
# Erst dann wird die virtuelle Umgebung (.venv) angelegt und Abhängigkeiten
# aus requirements.txt installiert.
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
echo "====================================================="
echo "  Mediathek-Suche — Einrichtung"
echo "====================================================="
echo

# -------------------------------------------------------------
# 1) System-Voraussetzungen prüfen
# -------------------------------------------------------------
missing_apt=()
warn_hint=""

have_cmd() { command -v "$1" >/dev/null 2>&1; }

echo "[1/4] Prüfe System-Voraussetzungen …"
echo

# Python
if have_cmd "$PYTHON"; then
  echo "  ✔ Python gefunden: $("$PYTHON" --version 2>&1)"
else
  echo "  ✗ Python ($PYTHON) fehlt."
  missing_apt+=("python3")
fi

# venv-Modul (bei Debian/Ubuntu eigenes Paket python3-venv / python3.12-venv)
if have_cmd "$PYTHON"; then
  if "$PYTHON" -c "import venv" >/dev/null 2>&1; then
    echo "  ✔ venv-Modul verfügbar"
  else
    echo "  ✗ venv-Modul fehlt (kein 'import venv' möglich)."
    missing_apt+=("python3-venv")
  fi
fi

# tmux ODER screen für Hintergrund-Betrieb
if have_cmd tmux; then
  echo "  ✔ tmux verfügbar"
elif have_cmd screen; then
  echo "  ✔ screen verfügbar (tmux fehlt — screen reicht)"
else
  echo "  ★ Hinweis: weder tmux noch screen gefunden."
  warn_hint="du kannst den Server auch direkt mit 'python3 server.py' starten,"
  warn_hint="$warn_hint beenden muss dann aber dieselbe Terminal-Sitzung."
  missing_apt+=("tmux")
fi

# curl (optional, für API-Tests)
if have_cmd curl; then
  echo "  ✔ curl verfügbar"
fi

echo
if [ ${#missing_apt[@]} -gt 0 ]; then
  echo "✗ Es fehlen System-Pakete. Bitte einmalig über apt installieren:"
  echo
  sudo_="" ; [ "$(id -u)" -eq 0 ] || sudo_="sudo "
  echo "  ${sudo_}apt update"
  echo "  ${sudo_}apt install -y ${missing_apt[*]}"
  echo
  echo "Danach dieses Skript erneut ausführen:  ./setup.sh"
  if [ -n "$warn_hint" ]; then
    echo
    echo "Hinweis: $warn_hint"
  fi
  exit 1
else
  echo "  ✔ Alle System-Voraussetzungen erfüllt."
fi

# -------------------------------------------------------------
# 2) Skripte ausführbar machen
# -------------------------------------------------------------
echo
echo "[2/4] Mache Hilfsskripte ausführbar …"
chmod +x setup.sh start.sh stop.sh 2>/dev/null || true
echo "  ✔ done (setup.sh, start.sh, stop.sh)"

# -------------------------------------------------------------
# 3) Virtuelle Umgebung anlegen
# -------------------------------------------------------------
echo
echo "[3/4] Erstelle virtuelle Umgebung mit $PYTHON …"
if [ -d .venv ]; then
  echo "  ✔ .venv existiert bereits — wird nicht neu erzeugt."
else
  "$PYTHON" -m venv .venv
  echo "  ✔ virtuelle Umgebung .venv angelegt."
fi

# -------------------------------------------------------------
# 4) Abhängigkeiten installieren
# -------------------------------------------------------------
echo
echo "[4/4] Installiere Abhängigkeiten …"
# pipefail + set -e: grep mit 0 Treffern liefert Exit 1, was das Skript bei
# "set -e" sonst abbräche — daher "|| true" zum Absichern.
REQ_COUNT=$(grep -E '^[[:space:]]*[^#[:space:]]' requirements.txt 2>/dev/null || true | wc -l)
if [ "$REQ_COUNT" -gt 0 ]; then
  echo "  ✔ Installiere Pakete aus requirements.txt …"
  ./.venv/bin/python3 -m pip install -r requirements.txt
else
  echo "  ✔ requirements.txt enthält keine Pakete — nichts zu installieren"
  echo "     (das Projekt nutzt nur die Python-Standardbibliothek)."
fi

# -------------------------------------------------------------
# Fertig
# -------------------------------------------------------------
echo
echo "====================================================="
echo "  Einrichtung abgeschlossen ✔"
echo "====================================================="
echo
echo "Nächste Schritte:"
echo "  1) Server starten:      ./start.sh"
echo "  2) Webclient öffnen:    http://localhost:8080"
echo "     (von anderen Geräten: http://<IP-dieses-Rechners>:8080)"
echo "  3) Beenden:             ./stop.sh"
echo
echo "Der Start nutzt automatisch das venv (falls .venv existiert)."
echo "Logs ansehen:  ./start.sh ausführen und der Session-Info folgen."