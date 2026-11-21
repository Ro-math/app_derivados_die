#!/usr/bin/env bash
# =============================================================================
# Lanzador para macOS y Linux
# Uso:
#   ./run.sh web
#   ./run.sh consola
#   ./run.sh comand
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if command -v python3 &>/dev/null; then
    PY_CMD="python3"
elif command -v python &>/dev/null; then
    PY_CMD="python"
else
    echo "[Error] No se encontro Python en el sistema. Por favor instale Python 3."
    exit 1
fi

"$PY_CMD" run.py "$@"
