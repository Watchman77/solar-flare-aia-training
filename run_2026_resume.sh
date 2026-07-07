#!/usr/bin/env bash
set -uo pipefail

mkdir -p "$HOME/solar_flare_aia/logs"
source "$HOME/solar_flare_aia/venv/bin/activate"

export TARGET_YEAR=2026
export JSOC_EMAIL=worky4work@gmail.com
export WORKER_ID=aia2026
export RUN_MODE=PRODUCTION
unset MAX_BLOCKS_THIS_RUN

LOG="$HOME/solar_flare_aia/logs/aia2026_production_console.log"

echo "===== 2026 RESUME STARTED: $(date -u) =====" | tee -a "$LOG"

jupyter nbconvert \
  --to notebook \
  --execute \
  "$HOME/solar_flare_aia/notebooks/05_AIA_JSOC_HARP_BLOCK_MINER_VM_READY_v2_CADENCE_FIXED.ipynb" \
  --ExecutePreprocessor.timeout=-1 \
  --output "$HOME/solar_flare_aia/logs/aia2026_production_resume_executed.ipynb" \
  2>&1 | tee -a "$LOG"

status=${PIPESTATUS[0]}
echo "===== 2026 WORKER ENDED: $(date -u), STATUS=$status =====" | tee -a "$LOG"
exit "$status"
