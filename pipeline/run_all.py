#!/usr/bin/env python3
"""Run the full pipeline for every meeting in MT_INBOX.

Stages run sequentially per meeting:
  1. ingest (skipped — files already in inbox)
  2. transcribe (skip if transcript.json exists)
  3. extract (skip if extraction.json exists)
  4. link (always re-runs, computes cross-meeting graph)

Then it rebuilds the indexes.

Usage:
  ./run_all.sh             # process everything in /opt/data/inbox/meetings
  python -m pipeline.run_all --meeting <id>   # single meeting

Reads:  /opt/data/inbox/meetings/<id>/audio.<ext>
Writes: /opt/data/inbox/meetings/<id>/{transcript,extraction}.{json,txt,vtt}
        /opt/data/indexed/meetings/{topics,people,decisions,okrs,daily_tasks,weekly_tasks}.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import config  # noqa: E402

import importlib  # noqa: E402

stage2 = importlib.import_module("pipeline.02_transcribe")
stage3 = importlib.import_module("pipeline.03_extract")
stage4 = importlib.import_module("pipeline.04_link")


def run_one(meeting_dir: Path, *, force: bool = False) -> dict:
    summary = {"meeting_id": meeting_dir.name, "stages": {}}
    try:
        summary["stages"]["transcribe"] = "ok"
        stage2.transcribe_one(meeting_dir, force=force)
    except Exception as e:
        summary["stages"]["transcribe"] = f"error: {e}"
        return summary
    try:
        summary["stages"]["extract"] = "ok"
        stage3.extract_one(meeting_dir, force=force)
    except Exception as e:
        summary["stages"]["extract"] = f"error: {e}"
        return summary
    return summary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run full pipeline for all/new meetings.")
    p.add_argument("--meeting", help="Single meeting id.")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.meeting:
        meeting_dir = config.INBOX / args.meeting
        if not meeting_dir.exists():
            print(f"[error] {meeting_dir} not found", file=sys.stderr)
            return 1
        run_one(meeting_dir, force=args.force)
    else:
        for mdir in sorted(config.INBOX.iterdir()):
            if not mdir.is_dir() or not (mdir / "audio.mp3").exists() and not any(mdir.glob("audio.*")):
                continue
            run_one(mdir, force=args.force)

    # Always rebuild indexes
    meetings = stage4.load_all_meetings()
    stage4.update_links_for_meetings(meetings)
    out = stage4.write_indexes(meetings)
    print(f"[run_all] wrote {len(out)} indexes to {config.INDEX}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())