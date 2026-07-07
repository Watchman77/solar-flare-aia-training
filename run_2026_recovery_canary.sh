#!/usr/bin/env bash

set -u

PROJECT_ROOT="$HOME/solar_flare_aia"
VENV="$PROJECT_ROOT/venv"
NOTEBOOK="$PROJECT_ROOT/notebooks/07_AIA_JSOC_2026_MISSING_ONLY_RECOVERY.ipynb"
LOG_DIR="$PROJECT_ROOT/logs"

mkdir -p "$LOG_DIR"

source "$VENV/bin/activate"
cd "$PROJECT_ROOT"

export JSOC_EMAIL="worky4work@gmail.com"
export WORKER_ID="aia2026-recovery"
export RECOVERY_MODE="CANARY"

echo "===== 2026 RECOVERY CANARY STARTED: $(date -u) =====" \
    >> "$LOG_DIR/aia2026_recovery_launcher.log"

jupyter nbconvert \
    --to notebook \
    --execute "$NOTEBOOK" \
    --ExecutePreprocessor.timeout=-1 \
    --output "$LOG_DIR/aia2026_recovery_canary_executed.ipynb" \
    >> "$LOG_DIR/aia2026_recovery_canary_console.log" 2>&1

STATUS=$?

echo "===== 2026 RECOVERY CANARY ENDED: $(date -u), STATUS=$STATUS =====" \
    >> "$LOG_DIR/aia2026_recovery_launcher.log"

exit "$STATUS"
