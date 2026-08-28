"""Stage 2: Transcribe + diarize.

Input:  MT_INBOX/<meeting_id>/audio.<ext>  + meta.json
Output: MT_INBOX/<meeting_id>/transcript.json  (WhisperX diarized JSON shape)
        MT_INBOX/<meeting_id>/transcript.txt   (per-speaker human-readable)
        MT_INBOX/<meeting_id>/transcript.vtt   (webvtt with speaker tags)
        updated meta.json with duration_sec, language, transcript paths

Engine: WhisperX (Whisper + wav2vec2 alignment + pyannote diarization).
Self-hosted on CPU; quality validated for Spanish/Portuguese.

Run modes:
  - Single meeting:  python -m pipeline.02_transcribe --meeting <id>
  - All pending:     python -m pipeline.02_transcribe --all
  - One-shot retry:  python -m pipeline.02_transcribe --meeting <id> --force

The WhisperX pipeline has 3 sub-stages:
  1. Whisper transcription (with FP16 off on CPU)
  2. wav2vec2 forced alignment (gives word-level timestamps)
  3. pyannote speaker diarization (gives SPEAKER_00, SPEAKER_01, ...)
  4. WhisperX assign_word_speakers (joins them)

All 4 happen in one call. We pass `language=None` to let Whisper auto-detect.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import config  # noqa: E402


# WhisperX outputs segments with `start`, `end`, `text`, `speaker` (after assign_word_speakers).
# Older WhisperX outputs `start_time`/`end_time`. Normalize to start_time/end_time for the schema.


def normalize_whisperx_segments(result: dict) -> list[dict]:
    """Coerce any WhisperX JSON shape into {start_time, end_time, speaker, text, words?}."""
    segs = result.get("segments", [])
    out = []
    for s in segs:
        seg = {
            "start_time": float(s.get("start", s.get("start_time", 0.0))),
            "end_time": float(s.get("end", s.get("end_time", 0.0))),
            "speaker": s.get("speaker", "SPEAKER_UNKNOWN"),
            "text": (s.get("text") or "").strip(),
        }
        if "words" in s:
            seg["words"] = [
                {
                    "word": w.get("word", w.get("text", "")),
                    "start": float(w.get("start", w.get("start_time", 0.0))),
                    "end": float(w.get("end", w.get("end_time", 0.0))),
                    "score": float(w.get("score", 1.0)),
                }
                for w in s["words"]
            ]
        out.append(seg)
    return out


def compute_speaker_stats(segments: list[dict]) -> list[dict]:
    """Per-speaker talk_pct, turns, word_tokens. Used by stage 3 for identity inference."""
    by_speaker: dict[str, dict] = {}
    total_dur = sum(s["end_time"] - s["start_time"] for s in segments) or 1.0
    for s in segments:
        sp = s["speaker"]
        if sp not in by_speaker:
            by_speaker[sp] = {"label": sp, "talk_sec": 0.0, "turns": 0, "word_tokens": 0}
        by_speaker[sp]["talk_sec"] += s["end_time"] - s["start_time"]
        by_speaker[sp]["turns"] += 1
        by_speaker[sp]["word_tokens"] += len(s.get("text", "").split())

    out = []
    for sp, d in by_speaker.items():
        out.append(
            {
                "label": d["label"],
                "inferred_name": None,  # stage 3 / 4 fills
                "talk_pct": round(d["talk_sec"] / total_dur * 100, 1),
                "turns": d["turns"],
                "word_tokens": d["word_tokens"],
                "confidence": 0.0,
            }
        )
    out.sort(key=lambda x: x["talk_pct"], reverse=True)
    return out


def write_transcript_outputs(meeting_dir: Path, result: dict, speakers: list[dict]) -> dict:
    """Write transcript.json, transcript.txt, transcript.vtt. Returns updated meta fields."""
    segments = normalize_whisperx_segments(result)
    duration = max((s["end_time"] for s in segments), default=0.0)
    language = result.get("language", "es")

    # transcript.json — full WhisperX shape + our schema fields
    transcript_json = {
        "engine": "whisperx",
        "model": config.WHISPER_MODEL,
        "language": language,
        "segments": segments,
    }
    (meeting_dir / "transcript.json").write_text(
        json.dumps(transcript_json, indent=2, ensure_ascii=False)
    )

    # transcript.txt — human-readable, one paragraph per speaker turn
    txt_lines = ["# Transcript\n"]
    current_sp = None
    for s in segments:
        if s["speaker"] != current_sp:
            txt_lines.append(f"\n[{format_ts(s['start_time'])}] {s['speaker']}\n")
            current_sp = s["speaker"]
        txt_lines.append(s["text"] + " ")
    (meeting_dir / "transcript.txt").write_text("".join(txt_lines))

    # transcript.vtt — webvtt with speaker tags
    vtt_lines = ["WEBVTT\n"]
    for s in segments:
        vtt_lines.append(f"\n{format_ts(s['start_time'])} --> {format_ts(s['end_time'])}\n")
        vtt_lines.append(f"<v {s['speaker']}>{s['text']}\n")
    (meeting_dir / "transcript.vtt").write_text("".join(vtt_lines))

    return {
        "duration_sec": round(duration, 1),
        "language": language,
        "speakers": speakers,
        "transcript_paths": {
            "json": "transcript.json",
            "txt": "transcript.txt",
            "vtt": "transcript.vtt",
        },
    }


def format_ts(sec: float) -> str:
    """HH:MM:SS.mmm for vtt/txt."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def transcribe_one(meeting_dir: Path, *, force: bool = False) -> dict:
    """Transcribe a single meeting folder. Returns the updated meta fields."""
    meta_path = meeting_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"No meta.json in {meeting_dir}")
    meta = json.loads(meta_path.read_text())

    transcript_json = meeting_dir / "transcript.json"
    if transcript_json.exists() and not force:
        print(f"[skip] {meeting_dir.name} already has transcript.json", file=sys.stderr)
        existing = json.loads(transcript_json.read_text())
        speakers = compute_speaker_stats(existing["segments"])
        return write_transcript_outputs(meeting_dir, existing, speakers)

    # Find the audio file (any extension)
    audio = None
    for ext in {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".flac", ".webm", ".mp4", ".mov"}:
        cand = meeting_dir / f"audio{ext}"
        if cand.exists():
            audio = cand
            break
    if audio is None:
        raise FileNotFoundError(f"No audio file found in {meeting_dir}")

    # Lazy import — whisperx is heavy. If not installed, fall back to a clear error.
    try:
        import whisperx  # type: ignore
    except ImportError:
        print(
            "[error] whisperx not installed.\n"
            "  uv venv --python 3.11 /tmp/whisperx-env && \\\n"
            "  source /tmp/whisperx-env/bin/activate && \\\n"
            "  uv pip install whisperx==3.1.5",
            file=sys.stderr,
        )
        raise

    # Load model + diarization pipeline. CPU mode (no fp16) to match voice-notes-transcription recipe.
    device = "cuda" if os.environ.get("MT_USE_CUDA") == "1" else "cpu"
    compute_type = "float16" if device == "cuda" else config.WHISPER_COMPUTE_TYPE

    print(f"[transcribe] {meeting_dir.name} model={config.WHISPER_MODEL} device={device}", file=sys.stderr)
    model = whisperx.load_model(config.WHISPER_MODEL, device, compute_type=compute_type)

    audio_data = whisperx.load_audio(str(audio))
    result = model.transcribe(audio_data, batch_size=config.WHISPER_BATCH_SIZE, language=None)

    # Align (gives word-level timestamps)
    align_model, align_metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], align_model, align_metadata, audio_data, device)

    # Diarize (pyannote). Requires HF_TOKEN env var with pyannote access.
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        diarize_model = whisperx.diarize.DiarizationPipeline(
            use_auth_token=hf_token, device=device
        )
        diarize_segments = diarize_model(audio_data)
        result = whisperx.assign_word_speakers(diarize_segments, result)
    else:
        print("[warn] HF_TOKEN not set; skipping diarization. Speakers will all be SPEAKER_UNKNOWN.", file=sys.stderr)

    # Build outputs and update meta
    segments = normalize_whisperx_segments(result)
    speakers = compute_speaker_stats(segments)
    fields = write_transcript_outputs(meeting_dir, result, speakers)

    meta.update({
        "duration_sec": fields["duration_sec"],
        "language": fields["language"],
        "speakers": fields["speakers"],
        "transcript": fields["transcript_paths"],
        "meta": {**meta["meta"], "updated_at": datetime.now(timezone.utc).isoformat()},
    })
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"[done] {meeting_dir.name} {len(segments)} segments, {len(speakers)} speakers", file=sys.stderr)
    return meta


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Stage 2: WhisperX transcribe + diarize.")
    p.add_argument("--meeting", help="Single meeting id (YYYY-MM-DD_slug).")
    p.add_argument("--all", action="store_true", help="Process every meeting in MT_INBOX.")
    p.add_argument("--force", action="store_true", help="Re-transcribe even if transcript.json exists.")
    args = p.parse_args(argv)

    if args.meeting:
        transcribe_one(config.INBOX / args.meeting, force=args.force)
    elif args.all:
        for mdir in sorted(config.INBOX.iterdir()):
            if mdir.is_dir() and (mdir / "meta.json").exists():
                try:
                    transcribe_one(mdir, force=args.force)
                except Exception as e:
                    print(f"[error] {mdir.name}: {e}", file=sys.stderr)
    else:
        p.print_help()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())