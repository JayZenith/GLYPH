#!/usr/bin/env bash
set -euo pipefail

INSTANCE_ID="${INSTANCE_ID:-35880402}"
SSH_HOST="${SSH_HOST:-146.115.17.161}"
SSH_PORT="${SSH_PORT:-31215}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519}"
REMOTE_ROOT="${REMOTE_ROOT:-/root/TASK}"
RUN_NAME="${RUN_NAME:-qwen3_4b_base_sft_lora_r32_a64_ctx6144}"
REMOTE_RUN_DIR="${REMOTE_RUN_DIR:-$REMOTE_ROOT/checkpoints/$RUN_NAME}"
LOCAL_OUT_DIR="${LOCAL_OUT_DIR:-$(pwd)/artifacts/$RUN_NAME}"
POLL_SECONDS="${POLL_SECONDS:-60}"
STATUS_FILE="$LOCAL_OUT_DIR/watch_status.txt"
LOG_FILE="$LOCAL_OUT_DIR/watch.log"
PID_FILE="$LOCAL_OUT_DIR/watch.pid"
HEARTBEAT_FILE="$LOCAL_OUT_DIR/watch.heartbeat"

mkdir -p "$LOCAL_OUT_DIR"
echo "$$" > "$PID_FILE"

remote() {
  ssh -o StrictHostKeyChecking=no -i "$SSH_KEY" -p "$SSH_PORT" "root@$SSH_HOST" "$@"
}

copy_from_remote() {
  local remote_path="$1"
  local local_path="$2"
  mkdir -p "$(dirname "$local_path")"
  scp -o StrictHostKeyChecking=no -i "$SSH_KEY" -P "$SSH_PORT" -r "root@$SSH_HOST:$remote_path" "$local_path"
}

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG_FILE"
}

destroy_instance() {
  log "Destroying Vast instance $INSTANCE_ID"
  vastai destroy instance "$INSTANCE_ID" | tee -a "$LOG_FILE"
}

collect_success() {
  log "Collecting successful SFT artifacts from $REMOTE_RUN_DIR"
  copy_from_remote "$REMOTE_ROOT/sft_a100.log" "$LOCAL_OUT_DIR/"
  copy_from_remote "$REMOTE_RUN_DIR/final" "$LOCAL_OUT_DIR/"
  copy_from_remote "$REMOTE_RUN_DIR/merged" "$LOCAL_OUT_DIR/"
  if remote "test -d '$REMOTE_RUN_DIR/checkpoint-60'"; then
    copy_from_remote "$REMOTE_RUN_DIR/checkpoint-60/trainer_state.json" "$LOCAL_OUT_DIR/trainer_state.json"
  fi
  printf 'SUCCESS\n' > "$STATUS_FILE"
  destroy_instance
}

collect_failure() {
  log "Training exited without merged checkpoint; collecting logs before destroying instance"
  remote "cd '$REMOTE_ROOT' && tail -n 120 sft_a100.log" | tee "$LOCAL_OUT_DIR/remote_tail.log" >> "$LOG_FILE" || true
  copy_from_remote "$REMOTE_ROOT/sft_a100.log" "$LOCAL_OUT_DIR/" || true
  printf 'FAILED\n' > "$STATUS_FILE"
  destroy_instance
}

log "Watcher started for instance $INSTANCE_ID, run $RUN_NAME"
printf 'RUNNING\n' > "$STATUS_FILE"

while true; do
  date -Is > "$HEARTBEAT_FILE"
  if remote "test -d '$REMOTE_RUN_DIR/merged'"; then
    collect_success
    exit 0
  fi

  if remote "pgrep -f 'python -u train.py --model Qwen/Qwen3-4B-Base' >/dev/null"; then
    progress="$(remote "cd '$REMOTE_ROOT' && tail -n 5 sft_a100.log" | tr '\n' ' ' | sed 's/[[:space:]]\\+/ /g')" || progress="log unavailable"
    log "Training still running. Tail: $progress"
    sleep "$POLL_SECONDS"
    continue
  fi

  collect_failure
  exit 1
done
