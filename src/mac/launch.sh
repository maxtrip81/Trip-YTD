#!/bin/sh
# Avvia il server di Trip YTD con il Python incluso nell'app, per l'architettura di questo Mac.
RES=$(cd "$(dirname "$0")" && pwd)
if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = 1 ]; then
  PY="$RES/python-arm64/bin/python3"
else
  PY="$RES/python-x86_64/bin/python3"
fi
# -B: non scrive file .pyc dentro l'app (ne altererebbe la firma)
exec "$PY" -B "$RES/trip_ytd.py" "$@"
