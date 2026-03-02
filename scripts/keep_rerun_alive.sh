#!/usr/bin/env bash
set -euo pipefail

ROOT="/Users/huigu/论文/论文工具/论文筛选工具"
RUNNER="$ROOT/src/new_prompt_screen_batch.py"
OUTPUT_BASE="$ROOT/output/new_prompt_full_rerun_gemini3_flash_preview_highthinking_20260301"
CONFERENCES="ICLR_2026,ICML,NeurIPS,ICLR"
CHECK_INTERVAL="${CHECK_INTERVAL:-20}"

WATCHDOG_LOG="$OUTPUT_BASE/watchdog.log"
RUNNER_LOG="$OUTPUT_BASE/runner.log"
WATCHDOG_PID_FILE="$OUTPUT_BASE/watchdog.pid"
RUNNER_PID_FILE="$OUTPUT_BASE/runner.pid"

mkdir -p "$OUTPUT_BASE"
echo "$$" > "$WATCHDOG_PID_FILE"

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

log() {
  echo "[$(timestamp)] $*" | tee -a "$WATCHDOG_LOG"
}

all_done() {
  local done_count
  done_count=0
  for conf in ICLR_2026 ICML NeurIPS ICLR; do
    if [[ -f "$OUTPUT_BASE/$conf/summary.json" ]]; then
      done_count=$((done_count + 1))
    fi
  done
  [[ "$done_count" -eq 4 ]]
}

find_runner_pid() {
  ps -ax -o pid=,command= | awk -v out="$OUTPUT_BASE" '
    /new_prompt_screen_batch\.py/ && index($0, out) > 0 { print $1; exit }
  '
}

start_runner() {
  if [[ -z "${API_KEYS:-}" ]]; then
    log "API_KEYS 未设置，无法启动评分进程。"
    return
  fi

  log "检测到评分进程不存在，启动断点续跑..."
  nohup env API_KEYS="$API_KEYS" \
    python "$RUNNER" \
      --output-base "$OUTPUT_BASE" \
      --conferences "$CONFERENCES" \
      --concurrency-per-key 6 \
      --max-retries 5 \
      >> "$RUNNER_LOG" 2>&1 &
  echo "$!" > "$RUNNER_PID_FILE"
  log "已启动评分进程 PID=$!"
}

log "watchdog 启动。输出目录: $OUTPUT_BASE"

while true; do
  if all_done; then
    log "四个会议均已完成，watchdog 退出。"
    break
  fi

  runner_pid="$(find_runner_pid || true)"
  if [[ -n "$runner_pid" ]]; then
    log "评分进程运行中 PID=$runner_pid"
  else
    start_runner
  fi

  sleep "$CHECK_INTERVAL"
done

