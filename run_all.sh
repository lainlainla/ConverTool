#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

PYTHON="${PYTHON:-python3}"
PRESET="all"
OUTPUT_ROOT="./datasets"
LEROBOT_SRC=""
DOWNLOAD_BACKEND="auto"
HF_ENDPOINT="https://huggingface.co"
MIRROR_ENDPOINT="https://hf-mirror.com"
WORKERS="4"
FORCE=0
AUTO_CLONE_LEROBOT=0
SKIP_DOWNLOAD=0
SKIP_CONVERT=0
SKIP_VALIDATE=0
SKIP_ORACLE_VALIDATE=0
SKIP_VIDEO_VALIDATE=0
DRY_RUN=0

usage() {
    cat <<'EOF'
Usage: ./run_all.sh [options]

Options:
  --python PATH                Python executable. Default: python3
  --preset NAME                Built-in preset name or all. Default: all
  --output-root PATH           Output dataset directory. Default: ./datasets
  --lerobot-src PATH           Path to LeRobot src directory
  --download-backend MODE      auto, hub, or curl. Default: auto
  --hf-endpoint URL            Hugging Face endpoint. Default: https://huggingface.co
  --mirror-endpoint URL        Curl fallback endpoint. Default: https://hf-mirror.com
  --workers N                  Download workers. Default: 4
  --force                      Remove existing outputs for selected datasets
  --auto-clone-lerobot         Clone LeRobot if src cannot be located
  --skip-download              Reuse existing v2.1 local dataset
  --skip-convert               Reuse existing v3.0 local dataset
  --skip-validate              Skip all validation
  --skip-oracle-validate       Only run basic LeRobotDataset load validation
  --skip-video-validate        Skip decoded video frame oracle
  --dry-run                    Print plan only
  -h, --help                   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --python) PYTHON="$2"; shift 2 ;;
        --preset) PRESET="$2"; shift 2 ;;
        --output-root) OUTPUT_ROOT="$2"; shift 2 ;;
        --lerobot-src) LEROBOT_SRC="$2"; shift 2 ;;
        --download-backend) DOWNLOAD_BACKEND="$2"; shift 2 ;;
        --hf-endpoint) HF_ENDPOINT="$2"; shift 2 ;;
        --mirror-endpoint) MIRROR_ENDPOINT="$2"; shift 2 ;;
        --workers) WORKERS="$2"; shift 2 ;;
        --force) FORCE=1; shift ;;
        --auto-clone-lerobot) AUTO_CLONE_LEROBOT=1; shift ;;
        --skip-download) SKIP_DOWNLOAD=1; shift ;;
        --skip-convert) SKIP_CONVERT=1; shift ;;
        --skip-validate) SKIP_VALIDATE=1; shift ;;
        --skip-oracle-validate) SKIP_ORACLE_VALIDATE=1; shift ;;
        --skip-video-validate) SKIP_VIDEO_VALIDATE=1; shift ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done

args=(
    "robocoin_hotel_convert.py"
    "--preset" "$PRESET"
    "--output-root" "$OUTPUT_ROOT"
    "--download-backend" "$DOWNLOAD_BACKEND"
    "--hf-endpoint" "$HF_ENDPOINT"
    "--mirror-endpoint" "$MIRROR_ENDPOINT"
    "--workers" "$WORKERS"
)

if [[ -n "$LEROBOT_SRC" ]]; then args+=("--lerobot-src" "$LEROBOT_SRC"); fi
if [[ "$FORCE" -eq 1 ]]; then args+=("--force"); fi
if [[ "$AUTO_CLONE_LEROBOT" -eq 1 ]]; then args+=("--auto-clone-lerobot"); fi
if [[ "$SKIP_DOWNLOAD" -eq 1 ]]; then args+=("--skip-download"); fi
if [[ "$SKIP_CONVERT" -eq 1 ]]; then args+=("--skip-convert"); fi
if [[ "$SKIP_VALIDATE" -eq 1 ]]; then args+=("--skip-validate"); fi
if [[ "$SKIP_ORACLE_VALIDATE" -eq 1 ]]; then args+=("--skip-oracle-validate"); fi
if [[ "$SKIP_VIDEO_VALIDATE" -eq 1 ]]; then args+=("--skip-video-validate"); fi
if [[ "$DRY_RUN" -eq 1 ]]; then args+=("--dry-run"); fi

"$PYTHON" "${args[@]}"
