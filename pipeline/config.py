"""Pipeline constants. Edit here, not at call sites.

Paths assume the standard AIW layout under /opt/data. Override via env vars:
  MT_INBOX        default /opt/data/inbox/meetings
  MT_PRODUCED     default /opt/data/produced/meetings  (after stage 2)
  MT_EXTRACTED    default /opt/data/extracted/meetings (after stage 3)
  MT_INDEX        default /opt/data/indexed/meetings   (after stage 4)
  MT_PROMPTS      default <repo>/prompts
  MT_SCHEMAS      default <repo>/schema
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

INBOX = Path(os.environ.get("MT_INBOX", "/opt/data/inbox/meetings"))
PRODUCED = Path(os.environ.get("MT_PRODUCED", "/opt/data/produced/meetings"))
EXTRACTED = Path(os.environ.get("MT_EXTRACTED", "/opt/data/extracted/meetings"))
INDEX = Path(os.environ.get("MT_INDEX", "/opt/data/indexed/meetings"))

PROMPTS_DIR = Path(os.environ.get("MT_PROMPTS", REPO_ROOT / "prompts"))
SCHEMAS_DIR = Path(os.environ.get("MT_SCHEMAS", REPO_ROOT / "schema"))

# Stage 1: Drive folder ID. Override at runtime via --drive-folder or env MT_DRIVE_FOLDER.
DRIVE_FOLDER_ID = os.environ.get("MT_DRIVE_FOLDER", "1iuz-q9fPxup4MZjuRLSs3U3iw6FmgIF2")

# Stage 2: WhisperX model choice.
#   medium = 769M, ~2x realtime, very good Spanish (validated 2026-08-26 in voice-notes-transcription skill)
#   large-v3 = 1.5B, ~1x realtime, best quality but ~3x slower
#   small = 244M, ~6x realtime, good for triage but less accurate on names/jargon
WHISPER_MODEL = os.environ.get("MT_WHISPER_MODEL", "medium")
WHISPER_COMPUTE_TYPE = os.environ.get("MT_WHISPER_COMPUTE", "int8")  # int8 for CPU, float16 for GPU
WHISPER_BATCH_SIZE = int(os.environ.get("MT_WHISPER_BATCH", "8"))

# Stage 3: LiteLLM model for extraction. Use whatever your LiteLLM gateway routes.
# User runs LiteLLM on Cerebras/Mistral/Anthropic — set MT_LITELLM_MODEL accordingly.
# Default to a Claude Sonnet-class model since extraction needs JSON discipline.
LITELLM_MODEL = os.environ.get("MT_LITELLM_MODEL", "claude-sonnet-4-5")
LITELLM_BASE_URL = os.environ.get("MT_LITELLM_BASE_URL", "http://localhost:4000")  # LiteLLM gateway default
LITELLM_API_KEY = os.environ.get("MT_LITELLM_API_KEY", "")  # set via env, never inline

# Stage 4: cross-meeting linking window (how far back to look for related topics).
LINK_WINDOW_DAYS = int(os.environ.get("MT_LINK_WINDOW_DAYS", "30"))

SCHEMA_VERSION = "1.0.0"