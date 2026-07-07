#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON="${PYTHON:-python3}"
VENV="./.venv"
CLONE_LEROBOT=0
LEROBOT_DIR="./_deps/lerobot"
LEROBOT_REPO="https://github.com/huggingface/lerobot.git"
LEROBOT_REF=""
INSTALL_VIZ=0

usage() {
    cat <<'EOF'
Usage: ./setup_env.sh [options]

Options:
  --python PATH          Python executable. Default: python3
  --venv PATH            Virtual environment path. Default: ./.venv
  --clone-lerobot        Clone Hugging Face LeRobot into ./_deps/lerobot
  --lerobot-dir PATH     LeRobot checkout path. Default: ./_deps/lerobot
  --lerobot-repo URL     LeRobot git URL
  --lerobot-ref REF      Optional branch, tag, or commit to checkout
  --install-viz          Install LeRobot dataset visualization dependencies
  -h, --help             Show this help
EOF
}

require_command() {
    local name="$1"
    local hint="$2"
    if ! command -v "$name" >/dev/null 2>&1; then
        echo "Missing command '$name'. $hint" >&2
        exit 1
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --python) PYTHON="$2"; shift 2 ;;
        --venv) VENV="$2"; shift 2 ;;
        --clone-lerobot) CLONE_LEROBOT=1; shift ;;
        --lerobot-dir) LEROBOT_DIR="$2"; shift 2 ;;
        --lerobot-repo) LEROBOT_REPO="$2"; shift 2 ;;
        --lerobot-ref) LEROBOT_REF="$2"; shift 2 ;;
        --install-viz) INSTALL_VIZ=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

require_command "$PYTHON" "Install Python 3.12 or 3.13."
require_command "curl" "Install curl with your system package manager."
if [[ "$CLONE_LEROBOT" -eq 1 ]]; then
    require_command "git" "Install Git with your system package manager."
fi

"$PYTHON" --version
"$PYTHON" - <<'PY'
import sys
if sys.version_info < (3, 12):
    raise SystemExit("Python 3.12 or newer is required.")
PY

if [[ ! -d "$VENV" ]]; then
    "$PYTHON" -m venv "$VENV"
fi

VENV_PYTHON="$VENV/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Virtual environment Python not found: $VENV_PYTHON" >&2
    exit 1
fi

"$VENV_PYTHON" -m pip install --upgrade pip setuptools wheel
"$VENV_PYTHON" -m pip install -r requirements.txt

if [[ "$CLONE_LEROBOT" -eq 1 ]]; then
    if [[ ! -d "$LEROBOT_DIR" ]]; then
        mkdir -p "$(dirname "$LEROBOT_DIR")"
        git clone "$LEROBOT_REPO" "$LEROBOT_DIR"
    fi

    if [[ -n "$LEROBOT_REF" ]]; then
        git -C "$LEROBOT_DIR" fetch --all --tags
        git -C "$LEROBOT_DIR" checkout "$LEROBOT_REF"
    fi

    "$VENV_PYTHON" -m pip install -e "$LEROBOT_DIR[dataset]"
    if [[ "$INSTALL_VIZ" -eq 1 ]]; then
        "$VENV_PYTHON" -m pip install -e "$LEROBOT_DIR[dataset_viz]"
    fi
elif [[ "$INSTALL_VIZ" -eq 1 ]]; then
    "$VENV_PYTHON" -m pip install -r requirements-viz.txt
fi

echo
echo "[OK] Environment is ready."
echo "Activate it with:"
echo "  source .venv/bin/activate"
if [[ -d "$LEROBOT_DIR/src" ]]; then
    echo "LeRobot src:"
    echo "  $LEROBOT_DIR/src"
fi
echo "Next dry-run:"
echo "  ./run_all.sh --preset all --output-root ./datasets --dry-run"
