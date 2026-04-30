#!/usr/bin/env bash
set -euo pipefail

REMOTE_URL="${REMOTE_URL:-git@github.com:JayZenith/synthetic_data.git}"
REPO_DIR="${REPO_DIR:-/root/work/synthetic_data}"
SOURCE_FILE="${SOURCE_FILE:-/root/work/TASK/data/traces_qwen32b_fp8_5k.jsonl}"
TARGET_FILE="${TARGET_FILE:-data/traces_qwen32b_fp8_5k.jsonl}"
BRANCH="${BRANCH:-main}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-300}"
COMMIT_NAME="${COMMIT_NAME:-Codex Bot}"
COMMIT_EMAIL="${COMMIT_EMAIL:-codex@openai.com}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/synthetic_data_push}"

export GIT_SSH_COMMAND="ssh -i ${SSH_KEY} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"

if ! git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  rm -rf "$REPO_DIR"
  git clone "$REMOTE_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"
git config user.name "$COMMIT_NAME"
git config user.email "$COMMIT_EMAIL"

while true; do
  if [[ ! -f "$SOURCE_FILE" ]]; then
    echo "source file missing: $SOURCE_FILE"
    sleep "$INTERVAL_SECONDS"
    continue
  fi

  mkdir -p "$(dirname "$TARGET_FILE")"
  cp "$SOURCE_FILE" "$TARGET_FILE"

  if [[ -z "$(git status --porcelain -- "$TARGET_FILE")" ]]; then
    echo "no changes"
    sleep "$INTERVAL_SECONDS"
    continue
  fi

  git add "$TARGET_FILE"
  lines="$(wc -l < "$TARGET_FILE" | tr -d ' ')"
  bytes="$(wc -c < "$TARGET_FILE" | tr -d ' ')"
  git commit -m "sync traces: ${lines} lines (${bytes} bytes)"
  git push origin "$BRANCH"
  sleep "$INTERVAL_SECONDS"
done
