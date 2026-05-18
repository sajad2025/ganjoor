#!/usr/bin/env bash
# Create the Python venv for the ganjoor mirror scripts and install deps.
#
# Why this script exists:
#   `python3 -m venv .venv` on macOS often produces a venv whose pip can't
#   talk to PyPI:
#
#     WARNING: pip is configured with locations that require TLS/SSL, however
#     the ssl module in Python is not available.
#     ERROR: Could not find a version that satisfies the requirement requests
#
#   On this Mac the root cause is RTI Connext DDS: ~/.zshrc sources
#   `rtisetenv_*.zsh`, which prepends RTI's bundled OpenSSL 3.0.12 to
#   DYLD_LIBRARY_PATH. dyld searches that *before* rpath, so brew Python's
#   `_ssl.cpython-*.so` ends up linked against RTI's libcrypto.3.dylib (which
#   is missing symbols newer Pythons need, e.g. `_X509_STORE_get1_objects`),
#   and `import ssl` raises ImportError. Pip then can't reach PyPI.
#
#   Same problem, same fix as faction-cpp/tools/setup_venv_macos.sh and
#   simworld/tools/setup_venv.sh:
#     1. Scrub DYLD_LIBRARY_PATH while building the venv.
#     2. Patch the venv's `activate` so RTI's libs move to
#        DYLD_FALLBACK_LIBRARY_PATH (searched *after* rpath) on every
#        `source .venv/bin/activate`.
#
# Auto-detects the OS:
#   - macOS:  prefers Homebrew's python3.12 (then 3.13 / 3.11 as fallbacks).
#             Apple's /usr/bin/python3 is explicitly avoided.
#   - Linux:  uses python3.12 if present (matches our GitHub Actions runner),
#             falls back to python3. No DYLD scrubbing needed — RTI's lib
#             shadowing only bites macOS dyld.
#
# Usage:  ./scripts/setup_venv.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

VENV_DIR=".venv"
REQUIREMENTS="scripts/requirements.txt"

OS="$(uname -s)"

# -----------------------------------------------------------------------------
# Locate a Python whose `ssl` module imports cleanly. On macOS we have to
# scrub DYLD_LIBRARY_PATH *before* the import-check, otherwise brew Python's
# _ssl.so picks up RTI's libcrypto and the check fails for the same reason
# the real venv would.
# -----------------------------------------------------------------------------
if [[ "$OS" == "Darwin" ]]; then
    unset DYLD_LIBRARY_PATH
fi

candidates=()
case "$OS" in
    Darwin)
        # macOS: must be Homebrew. Apple's Xcode-bundled /usr/bin/python3
        # ships without a working `ssl` module, so we explicitly avoid it.
        for ver in 3.12 3.13 3.11; do
            for prefix in /opt/homebrew/bin /usr/local/bin; do
                candidates+=("$prefix/python$ver")
            done
        done
        ;;
    Linux)
        # Linux: prefer python3.12 (matches the GitHub Actions runner), fall
        # back to python3 if 3.12 isn't installed.
        for name in python3.12 python3; do
            if command -v "$name" >/dev/null 2>&1; then
                candidates+=("$(command -v "$name")")
            fi
        done
        ;;
    *)
        echo "Unsupported OS: $OS (this script handles Darwin and Linux)." >&2
        exit 1
        ;;
esac

PY=""
for candidate in "${candidates[@]}"; do
    [[ -x "$candidate" ]] || continue
    if "$candidate" -c "import ssl" >/dev/null 2>&1; then
        PY="$candidate"
        break
    else
        echo "  - $candidate exists but has no working ssl module, skipping"
    fi
done

if [[ -z "$PY" ]]; then
    echo "No Python with a working ssl module found." >&2
    case "$OS" in
        Darwin)
            echo "Install one with:  brew install python@3.12" >&2
            ;;
        Linux)
            echo "On Ubuntu 24.04:  sudo apt install python3.12 python3.12-venv" >&2
            ;;
    esac
    exit 1
fi

echo "Detected OS: $OS"
echo "Using Python: $PY ($("$PY" --version 2>&1))"

# -----------------------------------------------------------------------------
# Build the venv. Any prior one was probably built from a broken interpreter,
# so wipe it.
# -----------------------------------------------------------------------------
rm -rf "$VENV_DIR"
"$PY" -m venv "$VENV_DIR"
echo "Created $VENV_DIR"

# -----------------------------------------------------------------------------
# macOS-only: patch activate so subsequent `source .venv/bin/activate` calls
# also move RTI's libs out of dyld's search path. See header comment.
# -----------------------------------------------------------------------------
if [[ "$OS" == "Darwin" ]]; then
    cat >> "$VENV_DIR/bin/activate" <<'ACTIVATE_HOOK'

# --- ganjoor DYLD scrub (macOS) -----------------------------------------------
# Move RTI's lib paths from DYLD_LIBRARY_PATH (searched before rpath) to
# DYLD_FALLBACK_LIBRARY_PATH (searched after) so brew Python's _ssl.so loads
# its own libcrypto. See scripts/setup_venv.sh.
if [ -n "${DYLD_LIBRARY_PATH:-}" ]; then
    export DYLD_FALLBACK_LIBRARY_PATH="${DYLD_LIBRARY_PATH}${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
    unset DYLD_LIBRARY_PATH
fi
# --- end ganjoor DYLD scrub ---------------------------------------------------
ACTIVATE_HOOK
    echo "Patched $VENV_DIR/bin/activate with DYLD scrub hook"
fi

# -----------------------------------------------------------------------------
# Activate, verify SSL works inside the venv too, install deps.
# -----------------------------------------------------------------------------
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -c "import ssl; print('OpenSSL:', ssl.OPENSSL_VERSION)"

pip install --upgrade pip
pip install -r "$REQUIREMENTS"

echo
echo "Done. Activate later with:  source $VENV_DIR/bin/activate"
echo "Then run, e.g.:             python scripts/fetch_ganjoor.py --help"
