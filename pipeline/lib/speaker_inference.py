"""Shared utilities: speaker identity inference helpers.

Used by stage 4 in a future iteration. Currently kept here for cross-stage reuse.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Iterable


SELF_REF_RE = re.compile(
    r"\b(yo|mi|mis|mí|conmigo)\b",
    re.IGNORECASE,
)


def first_person_ratio(segments: Iterable[dict], speaker_label: str) -> float:
    """Returns first-person tokens per 1000 words for a speaker.

    The speaker with the highest ratio is most likely the main discloser.
    Validated as a strong signal in voice-notes-transcription skill.
    """
    words_total = 0
    fp_total = 0
    for s in segments:
        if s.get("speaker") != speaker_label:
            continue
        text = (s.get("text") or "").lower()
        words = text.split()
        words_total += len(words)
        fp_total += sum(1 for w in words if SELF_REF_RE.fullmatch(w))
    if words_total == 0:
        return 0.0
    return fp_total / words_total * 1000


def label_distribution(segments: Iterable[dict]) -> Counter:
    return Counter(s.get("speaker", "?") for s in segments)