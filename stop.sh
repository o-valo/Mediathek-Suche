#!/usr/bin/env bash
# Beendet den Mediathek-Suchserver — egal ob in tmux oder in screen gestartet.
set -euo pipefail

SESSION="mediathek"
stopped=0

# tmux-Variante
if tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux kill-session -t "$SESSION"
  echo "Server beendet (tmux)."
  stopped=1
fi

# screen-Variante (falls tmux nicht zuständig war)
if [ "$stopped" -eq 0 ] && screen -ls 2>/dev/null | grep -q "\.${SESSION}"; then
  screen -S "$SESSION" -X quit
  echo "Server beendet (screen)."
  stopped=1
fi

if [ "$stopped" -eq 0 ]; then
  echo "Kein laufender Server gefunden (Session '$SESSION')."
fi