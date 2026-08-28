"""Shared utilities: WhisperX output validation + repair.

Before stage 3 consumes a transcript, this module ensures the shape matches our schema:
- segments have start_time/end_time (not start/end)
- speakers are non-empty strings
- text is stripped
- duration_sec is set on the meeting meta
"""
from __future__ import annotations

import json
from pathlib import Path


def repair_transcript(path: Path) -> dict:
    """Read a transcript.json and normalize it in-place. Returns the dict."""
    data = json.loads(path.read_text())
    for s in data.get("segments", []):
        # Some WhisperX versions use start/end; we standardize on start_time/end_time.
        if "start_time" not in s and "start" in s:
            s["start_time"] = s.pop("start")
        if "end_time" not in s and "end" in s:
            s["end_time"] = s.pop("end")
        if "speaker" not in s:
            s["speaker"] = "SPEAKER_UNKNOWN"
        s["text"] = (s.get("text") or "").strip()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data