#!/usr/bin/env bash
# Run the full pipeline for everything in MT_INBOX.
# Designed to be called from cron, GitHub Actions, or manually.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# Ensure required Python deps. Lightweight check — fail fast if missing.
python3 -c "import whisperx" 2>/dev/null || {
  echo "[run_all] whisperx not installed. Install: uv pip install whisperx==3.1.5" >&2
}
python3 -c "import litellm" 2>/dev/null || {
  echo "[run_all] litellm not installed. Install: uv pip install litellm" >&2
}

# Ensure dirs exist
mkdir -p /opt/data/inbox/meetings /opt/data/indexed/meetings

# Run the pipeline. --all is the default.
exec python3 -m pipeline.run_all "$@"