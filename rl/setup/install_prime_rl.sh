#!/usr/bin/env bash
set -euo pipefail

# Install PRIME-RL the way upstream expects: its own uv-managed Python 3.12 env.
# Then apply rl/setup/patch_install.py to the installed checkout. The patches
# fix vLLM Qwen3 packed-weight loading, the orchestrator's teacher-logprob path
# (used by the KL anchor), the full-weights inference broadcast, and tolerate
# checkpoints that don't carry `revert_weight_conversion`. The legacy LoRA-
# bootstrap patch lives in the same file and is a no-op when
# PRIME_RL_INIT_ADAPTER is unset (which is the default in the full-FT path).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRIME_RL_DIR="${1:-${PRIME_RL_DIR:-/workspace/prime-rl-src}}"
PRIME_PYTHON_VERSION="${PRIME_PYTHON_VERSION:-3.12}"
WORKSPACE_DIR="${WORKSPACE_DIR:-/workspace}"
DEFAULT_TMP_ROOT="$WORKSPACE_DIR/.tmp"
if [ -d /dev/shm ] && [ -w /dev/shm ] && [ -x /dev/shm ]; then
  DEFAULT_TMP_ROOT="/dev/shm/prime-rl-tmp"
fi
TMP_ROOT="${TMP_ROOT:-$DEFAULT_TMP_ROOT}"
UV_CACHE_DIR="${UV_CACHE_DIR:-$WORKSPACE_DIR/.uv-cache}"

mkdir -p "$TMP_ROOT" "$UV_CACHE_DIR"
if ! (printf '#!/usr/bin/env sh\nexit 0\n' > "$TMP_ROOT/.exec-test" && chmod +x "$TMP_ROOT/.exec-test" && "$TMP_ROOT/.exec-test"); then
  TMP_ROOT="$WORKSPACE_DIR/.tmp"
  mkdir -p "$TMP_ROOT"
fi
rm -f "$TMP_ROOT/.exec-test"
export TMPDIR="$TMP_ROOT"
export TEMP="$TMP_ROOT"
export TMP="$TMP_ROOT"
export UV_CACHE_DIR

init_prime_rl_submodules() {
  git -C "$PRIME_RL_DIR" submodule set-url deps/verifiers https://github.com/PrimeIntellect-ai/verifiers.git
  git -C "$PRIME_RL_DIR" submodule set-url deps/renderers https://github.com/PrimeIntellect-ai/renderers.git
  git -C "$PRIME_RL_DIR" submodule set-url deps/research-environments https://github.com/PrimeIntellect-ai/research-environments.git
  git -C "$PRIME_RL_DIR" submodule set-url deps/pydantic-config https://github.com/PrimeIntellect-ai/pydantic-config
  git -C "$PRIME_RL_DIR" submodule update --init deps/verifiers deps/renderers deps/research-environments deps/pydantic-config
}

install_flash_attn_wheel() {
  local python_bin="$1"
  local torch_version cuda_version py_tag abi_flag wheel_url

  torch_version="$("$python_bin" - <<'PY'
import torch
print(torch.__version__.split("+", 1)[0])
PY
)"
  cuda_version="$("$python_bin" - <<'PY'
import torch
print((torch.version.cuda or "").replace(".", ""))
PY
)"
  py_tag="$("$python_bin" - <<'PY'
import sys
print(f"cp{sys.version_info.major}{sys.version_info.minor}")
PY
)"
  abi_flag="$("$python_bin" - <<'PY'
import torch
print("TRUE" if torch._C._GLIBCXX_USE_CXX11_ABI else "FALSE")
PY
)"

  if [ -n "${FLASH_ATTN_WHEEL_URL:-}" ]; then
    wheel_url="$FLASH_ATTN_WHEEL_URL"
  elif [ "$torch_version" = "2.11.0" ] && [ "$cuda_version" = "128" ] && [ "$py_tag" = "cp312" ] && [ "$abi_flag" = "TRUE" ]; then
    wheel_url="https://github.com/lesj0610/flash-attention/releases/download/v2.8.3-cu12-torch2.11/flash_attn-2.8.3%2Bcu12torch2.11cxx11abiTRUE-cp312-cp312-linux_x86_64.whl"
  else
    echo "No pinned flash-attn wheel for torch=$torch_version cuda=$cuda_version python=$py_tag abi=$abi_flag" >&2
    echo "Set FLASH_ATTN_WHEEL_URL to a matching wheel before rerunning setup/install_prime_rl.sh." >&2
    return 1
  fi

  uv pip install --python "$python_bin" peft
  uv pip install --python "$python_bin" "$wheel_url"
}

install_rust_toolchain() {
  export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
  export RUSTUP_HOME="${RUSTUP_HOME:-$HOME/.rustup}"
  export PATH="$CARGO_HOME/bin:$PATH"

  if ! command -v cargo >/dev/null 2>&1 || ! command -v rustc >/dev/null 2>&1; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y --profile minimal --default-toolchain stable
  fi

  rustup default stable
  cargo --version
  rustc --version
}

if ! command -v uv >/dev/null 2>&1; then
  python3 -m pip install uv
fi

export PATH="$HOME/.local/bin:$PATH"

install_rust_toolchain

uv python install "$PRIME_PYTHON_VERSION"

if [ ! -d "$PRIME_RL_DIR/.git" ]; then
  git clone https://github.com/PrimeIntellect-ai/prime-rl.git "$PRIME_RL_DIR"
fi

cd "$PRIME_RL_DIR"
git pull --ff-only
init_prime_rl_submodules
uv sync --python "$PRIME_PYTHON_VERSION"

install_flash_attn_wheel "$PRIME_RL_DIR/.venv/bin/python"

SITE_PACKAGES_DIR="$("$PRIME_RL_DIR/.venv/bin/python" - <<'PY'
import importlib.util
import pathlib

spec = importlib.util.find_spec("prime_rl")
if spec is None:
    raise RuntimeError("prime_rl is not importable")
if spec.submodule_search_locations:
    print(pathlib.Path(next(iter(spec.submodule_search_locations))).resolve())
elif spec.origin:
    print(pathlib.Path(spec.origin).resolve().parent)
else:
    raise RuntimeError("Could not resolve prime_rl package path")
PY
)"
"$PRIME_RL_DIR/.venv/bin/python" "$ROOT_DIR/setup/patch_install.py" "$SITE_PACKAGES_DIR"

cat <<EOF
PRIME-RL ready at: $PRIME_RL_DIR
Activate with:
  source "$PRIME_RL_DIR/.venv/bin/activate"

Run glyph RL wrappers from:
  cd "$ROOT_DIR"
EOF
