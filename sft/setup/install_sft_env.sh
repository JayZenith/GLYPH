#!/usr/bin/env bash
set -euo pipefail

# Creates a local .venv for SFT, installs a pinned torch build into it, then
# installs the pinned Python deps from requirements-train.txt. flash-attn is
# installed wheel-only so setup never falls back to a source build.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
TORCH_VERSION="${TORCH_VERSION:-2.5.1}"
CUDA_WHL_TAG="${CUDA_WHL_TAG:-cu124}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/${CUDA_WHL_TAG}}"
FLASH_ATTN_VERSION="${FLASH_ATTN_VERSION:-2.8.3}"

if [ -n "${PYTHON_BIN:-}" ]; then
  SELECTED_PYTHON="$PYTHON_BIN"
elif command -v python3.11 >/dev/null 2>&1; then
  SELECTED_PYTHON="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1; then
  SELECTED_PYTHON="$(command -v python3)"
else
  echo "No python3 interpreter found." >&2
  exit 1
fi

PY_MINOR="$($SELECTED_PYTHON - <<'PYINFO'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PYINFO
)"

case "$PY_MINOR" in
  3.9|3.10|3.11) ;;
  *)
    cat >&2 <<EOF
Unsupported Python for the default flash-attn wheel flow: $PY_MINOR
Install Python 3.11 and rerun:
  apt-get update
  apt-get install -y python3.11 python3.11-venv
  PYTHON_BIN=$(command -v python3.11) bash sft/setup/install_sft_env.sh
EOF
    exit 1
    ;;
esac

if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install --user uv
fi

export PATH="$HOME/.local/bin:$PATH"

uv venv --python "$SELECTED_PYTHON" "$VENV_DIR"

VENV_PY="$VENV_DIR/bin/python"

uv pip install --python "$VENV_PY" --index-url "$TORCH_INDEX_URL" "torch==${TORCH_VERSION}"
uv pip install --python "$VENV_PY" -r "$ROOT_DIR/requirements-train.txt"

if [ -n "${FLASH_ATTN_WHEEL_URL:-}" ]; then
  uv pip install --python "$VENV_PY" "$FLASH_ATTN_WHEEL_URL"
else
  uv pip install --python "$VENV_PY" --only-binary=:all: "flash-attn==${FLASH_ATTN_VERSION}" || {
    "$VENV_PY" - <<'PYINFO'
import sys
import torch
print("No compatible prebuilt flash-attn wheel was resolved automatically.", file=sys.stderr)
print(f"torch={torch.__version__.split('+', 1)[0]}", file=sys.stderr)
print(f"cuda={(torch.version.cuda or '').replace('.', '')}", file=sys.stderr)
print(f"python=cp{sys.version_info.major}{sys.version_info.minor}", file=sys.stderr)
print(f"abi={'TRUE' if torch._C._GLIBCXX_USE_CXX11_ABI else 'FALSE'}", file=sys.stderr)
print("Set FLASH_ATTN_WHEEL_URL to a matching wheel and rerun sft/setup/install_sft_env.sh.", file=sys.stderr)
PYINFO
    exit 1
  }
fi

cat <<EOF
SFT env ready.
Activate with:
  source "$VENV_DIR/bin/activate"

Installed:
  python=$SELECTED_PYTHON
  torch==$TORCH_VERSION from $TORCH_INDEX_URL
  flash-attn wheel only
  pinned SFT deps from requirements-train.txt
EOF
