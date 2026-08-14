#!/usr/bin/env bash
# La Cucaracha v5 Daemon Wrapper — perpetually hungry
# Runs the killchain in an infinite loop with clean restart
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
mkdir -p "$LOG_DIR"
PIDFILE="/tmp/la_cucaracha_v5.pid"

cleanup() {
    echo "[daemon] Caught signal — shutting down"
    rm -f "$PIDFILE"
    exit 0
}
trap cleanup SIGTERM SIGINT SIGHUP

echo "[daemon] La Cucaracha v5 daemon starting — PID $$"
echo "$$" > "$PIDFILE"

EPOCHS_PER_RUN=50
SLEEP_BETWEEN_RUNS=30

while true; do
    TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
    echo "[daemon] === RUN ${TIMESTAMP} — launching ${EPOCHS_PER_RUN} epochs ==="
    
    cd "$SCRIPT_DIR"
    python3 -u la_cucaracha_v5.py \
        --epochs "$EPOCHS_PER_RUN" \
        --rate 5000 \
        2>&1 | stdbuf -oL tee -a "${LOG_DIR}/daemon_${TIMESTAMP}.log" || true
    
    EXIT_CODE=$?
    echo "[daemon] Run completed (exit=${EXIT_CODE}) — sleeping ${SLEEP_BETWEEN_RUNS}s before next cycle"
    sleep "$SLEEP_BETWEEN_RUNS"
done
