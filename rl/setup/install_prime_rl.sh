#!/usr/bin/env bash
set -euo pipefail

# Install the pinned PRIME-RL stack used by the current RLVR wrapper.
# This intentionally stays on the pre teacher-pool refactor commit because
# rl/train.py launches an external frozen teacher vLLM. A future migration to
# native PRIME-RL num_teacher_gpus should be done on an instance and tested
# end-to-end before removing this pin/patcher.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PRIME_RL_DIR="${1:-${PRIME_RL_DIR:-/workspace/prime-rl-src}}"
PRIME_PYTHON_VERSION="${PRIME_PYTHON_VERSION:-3.12}"
# Last commit before the student/teacher inference-pool refactor (d25184e06).
# Our patcher targets the older flat `inference_pool` layout.
PRIME_RL_COMMIT="${PRIME_RL_COMMIT:-97872d3e0}"
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
  # Only init submodules that exist at the pinned commit. pydantic-config
  # became a workspace submodule after our pin; pre-pin it's pulled directly
  # from samsja/pydantic_config via tool.uv.sources git.
  # Force HTTPS directly in .gitmodules before init. `git submodule set-url`
  # is not reliable before a submodule has been initialized.
  git -C "$PRIME_RL_DIR" config -f .gitmodules submodule.verifiers.url https://github.com/PrimeIntellect-ai/verifiers.git 2>/dev/null || true
  git -C "$PRIME_RL_DIR" config -f .gitmodules submodule.renderers.url https://github.com/PrimeIntellect-ai/renderers.git 2>/dev/null || true
  git -C "$PRIME_RL_DIR" config -f .gitmodules submodule.research-environments.url https://github.com/PrimeIntellect-ai/research-environments.git 2>/dev/null || true
  git -C "$PRIME_RL_DIR" config -f .gitmodules submodule.pydantic-config.url https://github.com/PrimeIntellect-ai/pydantic-config 2>/dev/null || true
  git -C "$PRIME_RL_DIR" config -f .gitmodules --remove-section submodule.configs/private 2>/dev/null || true
  git -C "$PRIME_RL_DIR" submodule sync --recursive

  local declared
  declared="$(git -C "$PRIME_RL_DIR" config -f .gitmodules --name-only --get-regexp 'submodule\..*\.path' | sed 's/^submodule\.\(.*\)\.path$/\1/')"
  for name in $declared; do
    local path
    path="$(git -C "$PRIME_RL_DIR" config -f .gitmodules --get "submodule.${name}.path")"
    case "$path" in
      deps/verifiers|deps/renderers|deps/research-environments|deps/pydantic-config)
        git -C "$PRIME_RL_DIR" submodule update --init "$path"
        ;;
    esac
  done
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

  # Detect GPU compute capability so we can pick a wheel that supports it.
  # Hopper = 9.0, Blackwell server = 10.0 / 12.0.
  local sm_cap
  sm_cap="$("$python_bin" - <<'PY'
try:
    import torch
    if torch.cuda.is_available():
        major, minor = torch.cuda.get_device_capability(0)
        print(f"{major}.{minor}")
    else:
        print("none")
except Exception:
    print("none")
PY
)"

  # Build a candidate list — first match wins. Each candidate is a URL.
  # Pinned wheels by (torch, cuda, py, abi, optional sm-cap requirement).
  local -a candidates=()
  if [ -n "${FLASH_ATTN_WHEEL_URL:-}" ]; then
    candidates+=("$FLASH_ATTN_WHEEL_URL")
  fi
  if [ "$torch_version" = "2.11.0" ] && [ "$cuda_version" = "128" ] && [ "$py_tag" = "cp312" ] && [ "$abi_flag" = "TRUE" ]; then
    # Single known-good wheel for our pinned stack. CUDA wheels carry PTX
    # for forward-arch JIT (often loads on Blackwell sm_10/12 even though
    # the wheel was built for Hopper). If import test fails on Blackwell,
    # we skip flash-attn entirely — trainer.toml uses attn=sdpa.
    candidates+=("https://github.com/lesj0610/flash-attention/releases/download/v2.8.3-cu12-torch2.11/flash_attn-2.8.3%2Bcu12torch2.11cxx11abiTRUE-cp312-cp312-linux_x86_64.whl")
  fi

  if [ "${#candidates[@]}" -eq 0 ]; then
    echo "No pinned flash-attn wheel for torch=$torch_version cuda=$cuda_version python=$py_tag abi=$abi_flag sm=$sm_cap" >&2
    echo "Trainer config defaults to attn=sdpa, so this is non-fatal. Skipping flash-attn." >&2
    return 0
  fi

  for wheel_url in "${candidates[@]}"; do
    echo "[flash-attn] trying wheel: $wheel_url (sm_cap=$sm_cap)"
    if uv pip install --python "$python_bin" "$wheel_url"; then
      # Verify import + arch match. If load fails, uninstall and try next.
      if "$python_bin" -c "import flash_attn" 2>/dev/null; then
        echo "[flash-attn] installed and imports OK"
        return 0
      else
        echo "[flash-attn] wheel installed but failed to import on sm_$sm_cap; trying next candidate"
        uv pip uninstall --python "$python_bin" flash-attn 2>/dev/null || true
      fi
    fi
  done

  echo "[flash-attn] no compatible wheel — trainer.toml uses attn=sdpa, so this is non-fatal." >&2
  return 0
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
git fetch --quiet
git checkout --quiet "$PRIME_RL_COMMIT"
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
"$PRIME_RL_DIR/.venv/bin/python" "$ROOT_DIR/rl/setup/patch_install.py" "$SITE_PACKAGES_DIR"

cat <<EOF
PRIME-RL ready at: $PRIME_RL_DIR
Activate with:
  source "$PRIME_RL_DIR/.venv/bin/activate"

Run glyph RL wrappers from the repo root:
  cd "$ROOT_DIR" && bash rl/setup/run_task_trace_2xa100.sh
EOF
