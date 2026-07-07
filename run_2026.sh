#!/usr/bin/env bash

set -u

PROJECT_ROOT="$HOME/solar_flare_aia"
VENV="$PROJECT_ROOT/venv"
NOTEBOOK="$PROJECT_ROOT/notebooks/05_AIA_JSOC_HARP_BLOCK_MINER_VM_READY_v2_CADENCE_FIXED.ipynb"
LOG_DIR="$PROJECT_ROOT/logs"

mkdir -p "$LOG_DIR"

source "$VENV/bin/activate"
cd "$PROJECT_ROOT"

export TARGET_YEAR=2026
export JSOC_EMAIL="worky4work@gmail.com"
export WORKER_ID="aia2026"
export RUN_MODE="PRODUCTION"

START_TIME="$(date -u '+%a %b %d %H:%M:%S UTC %Y')"

echo "===== 2026 RETRY STARTED: $START_TIME =====" \
    >> "$LOG_DIR/aia2026_launcher.log"

jupyter nbconvert \
    --to notebook \
    --execute "$NOTEBOOK" \
    --ExecutePreprocessor.timeout=-1 \
    --output "$LOG_DIR/aia2026_retry_executed.ipynb" \
    >> "$LOG_DIR/aia2026_retry_console.log" 2>&1

STATUS=$?

END_TIME="$(date -u '+%a %b %d %H:%M:%S UTC %Y')"

echo "===== 2026 RETRY ENDED: $END_TIME, STATUS=$STATUS =====" \
    >> "$LOG_DIR/aia2026_launcher.log"

exit "$STATUS"
