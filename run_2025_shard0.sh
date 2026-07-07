#!/usr/bin/env bash
set -uo pipefail

source "$HOME/solar_flare_aia/venv/bin/activate"
mkdir -p "$HOME/solar_flare_aia/logs"

export TARGET_YEAR=2025
export JSOC_EMAIL=abmoses2000@gmail.com
export WORKER_ID=aia2025-s0
export RUN_MODE=PRODUCTION
export NUM_SHARDS=4
export SHARD_INDEX=0
unset MAX_BLOCKS_THIS_RUN

LOG="$HOME/solar_flare_aia/logs/aia2025_shard0_console.log"

echo "===== 2025 SHARD 0 STARTED: $(date -u) =====" | tee -a "$LOG"

jupyter nbconvert \
  --to notebook \
  --execute \
  "$HOME/solar_flare_aia/notebooks/06_AIA_JSOC_HARP_BLOCK_MINER_v3_SHARDED_PRODUCTION.ipynb" \
  --ExecutePreprocessor.timeout=-1 \
  --output "$HOME/solar_flare_aia/logs/aia2025_shard0_executed.ipynb" \
  2>&1 | tee -a "$LOG"

status=${PIPESTATUS[0]}
echo "===== 2025 SHARD 0 ENDED: $(date -u), STATUS=$status =====" | tee -a "$LOG"
exit "$status"
