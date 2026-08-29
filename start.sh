#!/usr/bin/env bash
# Startet den Mediathek-Suchserver in einer tmux- ODER screen-Session,
# damit er auch nach Schließen des Terminals weiterläuft.
#
#   ./start.sh          → tmux (Standard, falls vorhanden)
#   ./start.sh screen   → screen
#   SESSION_BACKEND=screen ./start.sh   (alte Variable)
set -euo pipefail

cd "$(dirname "$0")"

PORT="${PORT:-8080}"
BACKEND="${1:-${SESSION_BACKEND:-tmux}}"

# Python wählen: bevorzugt das venv (falls vorhanden), sonst System-Python.
if [ -x ".venv/bin/python3" ]; then
  PY=".venv/bin/python3"
elif [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

case "$BACKEND" in
  tmux)
    SESSION="mediathek"
    if tmux has-session -t "$SESSION" 2>/dev/null; then
      echo "Server läuft bereits (tmux-Session '$SESSION')."
    else
      tmux new-session -d -s "$SESSION" "cd $(pwd) && $PY -u server.py"
      echo "Server in tmux gestartet."
    fi
    HOW="tmux attach -t $SESSION"
    ;;
  screen)
    SESSION="mediathek"
    if screen -ls | grep -q "\.${SESSION}\b"; then
      echo "Server läuft bereits (screen-Session '$SESSION')."
    else
      screen -dmS "$SESSION" bash -c "cd $(pwd) && exec $PY -u server.py"
      echo "Server in screen gestartet."
    fi
    HOW="screen -r $SESSION"
    ;;
  *)
    echo "Unbekannter Backend '$BACKEND'. Nutze 'tmux' oder 'screen'." >&2
    exit 1
    ;;
esac

echo
echo "Webclient:  http://localhost:$PORT   (oder über die IP dieses Rechners)"
echo "Beenden:    ./stop.sh"
echo "Logs ansehen:  $HOW"
echo "  verlassen: tmux → Strg+B dann d   |   screen → Strg+A dann d"