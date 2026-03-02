#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/huigu/论文/论文工具/论文筛选工具"
RUNNER="$ROOT/src/new_prompt_screen_batch.py"
OUTPUT_BASE="$ROOT/output/new_prompt_full_rerun_gemini3_flash_preview_highthinking_20260301"
CONFERENCES="ICLR_2026,ICML,NeurIPS,ICLR"
LOG_FILE="$OUTPUT_BASE/run_until_done.log"
LOCK_FILE="$OUTPUT_BASE/run_until_done.lock"
SLEEP_SECONDS="${SLEEP_SECONDS:-15}"

mkdir -p "$OUTPUT_BASE"

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  echo "[$(timestamp)] $*" >> "$LOG_FILE"
}

all_done() {
  for conf in ICLR_2026 ICML NeurIPS ICLR; do
    if [[ ! -f "$OUTPUT_BASE/$conf/summary.json" ]]; then
      return 1
    fi
  done
  return 0
}

cleanup() {
  rm -f "$LOCK_FILE"
}
trap cleanup EXIT

if [[ -f "$LOCK_FILE" ]]; then
  old_pid="$(cat "$LOCK_FILE" 2>/dev/null || true)"
  if [[ -n "${old_pid}" ]] && ps -p "$old_pid" >/dev/null 2>&1; then
    echo "run_until_done 已在运行 (pid=$old_pid)"
    exit 0
  fi
fi
echo "$$" > "$LOCK_FILE"

if [[ -z "${API_KEYS:-}" ]]; then
  echo "API_KEYS 未设置，无法启动。"
  exit 1
fi

log "run_until_done 启动。"

while true; do
  if all_done; then
    log "四个会议均已完成，退出。"
    break
  fi

  log "启动批处理主进程..."
  set +e
  env API_KEYS="$API_KEYS" \
    python "$RUNNER" \
      --output-base "$OUTPUT_BASE" \
      --conferences "$CONFERENCES" \
      --concurrency-per-key 6 \
      --max-retries 5 >> "$LOG_FILE" 2>&1
  code=$?
  set -e

  log "主进程退出，code=$code；${SLEEP_SECONDS}s 后检查续跑。"
  sleep "$SLEEP_SECONDS"
done

