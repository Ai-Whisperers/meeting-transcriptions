"""Meeting transcription pipeline package.

Stage order:
  01_ingest      → Drive/local → /opt/data/inbox/meetings/<YYYY-MM-DD_slug>/audio.<ext>
  02_transcribe  → WhisperX + pyannote diarization → transcript/JSON
  03_extract     → LiteLLM → daily/weekly/monthly/topics/decisions
  04_link        → cross-meeting topic graph + index rollup
"""
__version__ = "0.1.0"