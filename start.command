#!/bin/zsh
set -eu
cd "$(dirname "$0")"
if /usr/bin/curl -fsS http://127.0.0.1:7860/api/health 2>/dev/null | /usr/bin/grep -q 'VibeVoice-ASR-BitNet'; then
  /usr/bin/open http://127.0.0.1:7860
  exit 0
fi
(
  for attempt in {1..30}; do
    if /usr/bin/curl -fsS http://127.0.0.1:7860/api/health >/dev/null 2>&1; then
      /usr/bin/open http://127.0.0.1:7860
      exit 0
    fi
    sleep 1
  done
) &
exec .venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 7860
