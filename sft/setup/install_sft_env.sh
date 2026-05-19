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

if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install --user uv
fi

export PATH="$HOME/.local/bin:$PATH"

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
    uv python install 3.11
    SELECTED_PYTHON="$(uv python find --managed-python 3.11)"
    PY_MINOR="$("$SELECTED_PYTHON" - <<'PYINFO'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PYINFO
)"
    case "$PY_MINOR" in
      3.11) ;;
      *)
        cat >&2 <<EOF
Failed to provision a managed Python 3.11 with uv.
Set PYTHON_BIN explicitly and rerun:
  PYTHON_BIN=/path/to/python3.11 bash sft/setup/install_sft_env.sh
EOF
        exit 1
        ;;
    esac
    ;;
esac

uv venv --clear --python "$SELECTED_PYTHON" "$VENV_DIR"

VENV_PY="$VENV_DIR/bin/python"

uv pip install --python "$VENV_PY" --index-url "$TORCH_INDEX_URL" "torch==${TORCH_VERSION}"
uv pip install --python "$VENV_PY" -r "$ROOT_DIR/requirements-train.txt"

read -r FLASH_TORCH_TAG FLASH_CUDA_TAG FLASH_PY_TAG FLASH_ABI_TAG <<EOF
$("$VENV_PY" - <<'PYINFO'
import sys
import torch
torch_tag = ".".join(torch.__version__.split("+", 1)[0].split(".")[:2])
cuda_tag = f"cu{(torch.version.cuda or '12').split('.', 1)[0]}"
py_tag = f"cp{sys.version_info.major}{sys.version_info.minor}"
abi_tag = "TRUE" if torch._C._GLIBCXX_USE_CXX11_ABI else "FALSE"
print(torch_tag, cuda_tag, py_tag, abi_tag)
PYINFO
)
EOF

AUTO_WHEEL_NAME="flash_attn-${FLASH_ATTN_VERSION}+${FLASH_CUDA_TAG}torch${FLASH_TORCH_TAG}cxx11abi${FLASH_ABI_TAG}-${FLASH_PY_TAG}-${FLASH_PY_TAG}-linux_x86_64.whl"
AUTO_WHEEL_URL="https://github.com/Dao-AILab/flash-attention/releases/download/v${FLASH_ATTN_VERSION}/${AUTO_WHEEL_NAME//+/%2B}"
MIRROR_WHEEL_URL="https://huggingface.co/strangertoolshf/flash_attention_2_wheelhouse/resolve/main/wheelhouse-flash_attn-${FLASH_ATTN_VERSION}/linux_x86_64/torch${FLASH_TORCH_TAG}/${FLASH_CUDA_TAG}/abi${FLASH_ABI_TAG}/${FLASH_PY_TAG}/${AUTO_WHEEL_NAME//+/%2B}"

install_flash_wheel() {
  local wheel_url="$1"
  local wheel_name wheel_dir wheel_file
  wheel_name="${wheel_url##*/}"
  wheel_name="${wheel_name//%2B/+}"
  wheel_dir="$(mktemp -d /tmp/flash-attn.XXXXXX)"
  wheel_file="$wheel_dir/$wheel_name"
  curl -fL --retry 3 --retry-delay 2 -o "$wheel_file" "$wheel_url"
  uv pip install --python "$VENV_PY" "$wheel_file"
  rm -rf "$wheel_dir"
}

if [ -n "${FLASH_ATTN_WHEEL_URL:-}" ]; then
  install_flash_wheel "$FLASH_ATTN_WHEEL_URL"
elif install_flash_wheel "$AUTO_WHEEL_URL"; then
  :
elif install_flash_wheel "$MIRROR_WHEEL_URL"; then
  :
elif uv pip install --python "$VENV_PY" --only-binary=:all: "flash-attn==${FLASH_ATTN_VERSION}"; then
  :
else
  "$VENV_PY" - <<'PYINFO'
import sys
import torch
print("No compatible prebuilt flash-attn wheel was resolved automatically.", file=sys.stderr)
print(f"torch={'.'.join(torch.__version__.split('+', 1)[0].split('.')[:2])}", file=sys.stderr)
print(f"cuda=cu{(torch.version.cuda or '12').split('.', 1)[0]}", file=sys.stderr)
print(f"python=cp{sys.version_info.major}{sys.version_info.minor}", file=sys.stderr)
print(f"abi={'TRUE' if torch._C._GLIBCXX_USE_CXX11_ABI else 'FALSE'}", file=sys.stderr)
print("Set FLASH_ATTN_WHEEL_URL to a matching wheel and rerun sft/setup/install_sft_env.sh.", file=sys.stderr)
PYINFO
  exit 1
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
