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
BLACKWELL_FLASH_ATTN_WHEEL_URL="${BLACKWELL_FLASH_ATTN_WHEEL_URL:-https://github.com/lesj0610/flash-attention/releases/download/v2.8.3-cu12-torch2.11/flash_attn-2.8.3%2Bcu12torch2.11cxx11abiTRUE-cp312-cp312-linux_x86_64.whl}"
NVIDIA_PYPI_INDEX="${NVIDIA_PYPI_INDEX:-https://pypi.nvidia.com}"

detect_gpu_name() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    return 1
  fi
  nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n 1
}

is_blackwell_gpu() {
  local gpu_name
  gpu_name="$(detect_gpu_name || true)"
  case "$gpu_name" in
    *"RTX PRO 6000"*|*"RTX 6000 Pro"*|*"B200"*|*"GB200"*|*"Blackwell"*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

using_default_sft_stack() {
  [ "${TORCH_VERSION}" = "2.5.1" ] \
    && [ "${CUDA_WHL_TAG}" = "cu124" ] \
    && [ "${TORCH_INDEX_URL}" = "https://download.pytorch.org/whl/cu124" ] \
    && [ -z "${FLASH_ATTN_WHEEL_URL:-}" ] \
    && [ -z "${PYTHON_BIN:-}" ]
}

if using_default_sft_stack && is_blackwell_gpu; then
  TORCH_VERSION="2.11.0"
  CUDA_WHL_TAG="cu128"
  TORCH_INDEX_URL="https://download.pytorch.org/whl/${CUDA_WHL_TAG}"
  FLASH_ATTN_WHEEL_URL="$BLACKWELL_FLASH_ATTN_WHEEL_URL"
  SFT_PYTHON_TARGET="3.12"
  echo "Detected Blackwell-class GPU; using fallback stack: python=${SFT_PYTHON_TARGET}, torch=${TORCH_VERSION}, cuda=${CUDA_WHL_TAG}" >&2
else
  SFT_PYTHON_TARGET="3.11"
fi

retry_uv_pip_install() {
  local attempts="$1"
  shift
  local try=1
  while true; do
    if uv pip install --system-certs "$@"; then
      return 0
    fi
    if [ "$try" -ge "$attempts" ]; then
      return 1
    fi
    sleep $((try * 5))
    try=$((try + 1))
  done
}

if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install --user uv
fi

export PATH="$HOME/.local/bin:$PATH"

if [ -n "${PYTHON_BIN:-}" ]; then
  SELECTED_PYTHON="$PYTHON_BIN"
elif [ "$SFT_PYTHON_TARGET" = "3.12" ] && command -v python3.12 >/dev/null 2>&1; then
  SELECTED_PYTHON="$(command -v python3.12)"
elif [ "$SFT_PYTHON_TARGET" = "3.11" ] && command -v python3.11 >/dev/null 2>&1; then
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

if [ "$SFT_PYTHON_TARGET" = "3.12" ]; then
  case "$PY_MINOR" in
    3.12) ;;
    *)
      uv python install "$SFT_PYTHON_TARGET"
      SELECTED_PYTHON="$(uv python find --managed-python "$SFT_PYTHON_TARGET")"
      PY_MINOR="$("$SELECTED_PYTHON" - <<'PYINFO'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PYINFO
)"
      case "$PY_MINOR" in
        "$SFT_PYTHON_TARGET") ;;
        *)
          cat >&2 <<EOF
Failed to provision a managed Python ${SFT_PYTHON_TARGET} with uv.
Set PYTHON_BIN explicitly and rerun:
  PYTHON_BIN=/path/to/python${SFT_PYTHON_TARGET} bash sft/setup/install_sft_env.sh
EOF
          exit 1
          ;;
      esac
      ;;
  esac
else
  case "$PY_MINOR" in
    3.9|3.10|3.11) ;;
    *)
      uv python install "$SFT_PYTHON_TARGET"
      SELECTED_PYTHON="$(uv python find --managed-python "$SFT_PYTHON_TARGET")"
      PY_MINOR="$("$SELECTED_PYTHON" - <<'PYINFO'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
PYINFO
)"
      case "$PY_MINOR" in
        "$SFT_PYTHON_TARGET") ;;
        *)
          cat >&2 <<EOF
Failed to provision a managed Python ${SFT_PYTHON_TARGET} with uv.
Set PYTHON_BIN explicitly and rerun:
  PYTHON_BIN=/path/to/python${SFT_PYTHON_TARGET} bash sft/setup/install_sft_env.sh
EOF
          exit 1
          ;;
      esac
      ;;
  esac
fi

uv venv --clear --python "$SELECTED_PYTHON" "$VENV_DIR"

VENV_PY="$VENV_DIR/bin/python"

retry_uv_pip_install 4 \
  --python "$VENV_PY" \
  --index-url "$TORCH_INDEX_URL" \
  --extra-index-url "$NVIDIA_PYPI_INDEX" \
  "torch==${TORCH_VERSION}"

retry_uv_pip_install 3 \
  --python "$VENV_PY" \
  -r "$ROOT_DIR/requirements-train.txt"

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
  uv pip install --system-certs --python "$VENV_PY" "$wheel_file"
  rm -rf "$wheel_dir"
}

if [ -n "${FLASH_ATTN_WHEEL_URL:-}" ]; then
  install_flash_wheel "$FLASH_ATTN_WHEEL_URL"
elif install_flash_wheel "$AUTO_WHEEL_URL"; then
  :
elif install_flash_wheel "$MIRROR_WHEEL_URL"; then
  :
elif uv pip install --system-certs --python "$VENV_PY" --only-binary=:all: "flash-attn==${FLASH_ATTN_VERSION}"; then
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
