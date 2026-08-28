#!/usr/bin/env bash
# Run the full pipeline for everything in MT_INBOX.
# Designed to be called from cron, GitHub Actions, or manually.
#
# Modes:
#   bash run_all.sh                          # local-only (no Drive ingest)
#   bash run_all.sh --source drive-public    # pull from public Drive folder, then process
#   bash run_all.sh --source drive           # pull from service-account Drive folder, then process
#
# Setup (one-time):
#   uv venv --python 3.11 .venv
#   source .venv/bin/activate
#   uv pip install -r requirements.txt
#   cp .env.example .env  # then edit .env with your keys

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# Auto-activate the local venv if it exists and we aren't already in one.
if [ -d ".venv" ] && [ -z "${VIRTUAL_ENV:-}" ]; then
  echo "[run_all] activating .venv" >&2
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Load .env if python-dotenv is available (best-effort; ignored if missing).
if [ -f ".env" ] && python3 -c "import dotenv" 2>/dev/null; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

# Ensure required Python deps. Lightweight check — fail fast if missing.
python3 -c "import whisperx" 2>/dev/null || {
  echo "[run_all] whisperx not installed. Run: uv pip install -r requirements.txt" >&2
}
python3 -c "import litellm" 2>/dev/null || {
  echo "[run_all] litellm not installed. Run: uv pip install -r requirements.txt" >&2
}

# Ensure dirs exist
mkdir -p "${MT_INBOX:-/opt/data/inbox/meetings}" "${MT_INDEX:-/opt/data/indexed/meetings}"

# Run the pipeline. --all is the default.
exec python3 -m pipeline.run_all "$@"