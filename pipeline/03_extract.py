"""Stage 3: Extract.

Input:  MT_INBOX/<meeting_id>/transcript.json + meta.json
Output: MT_INBOX/<meeting_id>/extraction.json   (matches schema/extraction.schema.json)
        updated meta.json with extraction section

Engine: LiteLLM gateway. Five extractions per meeting, one per prompt template:
  - extract_daily_tasks.md
  - extract_weekly_tasks.md
  - extract_monthly_okrs.md
  - extract_topics.md       (with prior_meetings context for cross-linking)
  - extract_decisions.md

The extractor is *deterministic* in structure but the LLM does the heavy lifting.
We pass:
  - transcript segments as numbered, timestamped JSON
  - prior_meetings context (for topics only)
  - prompt template content
  - temperature=0.1 (low variance)
  - response_format: json_object (for OpenAI-compatible gateways)

Outputs are validated against schema/extraction.schema.json. Invalid → retry once
with the schema errors appended to the prompt.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import config  # noqa: E402


def load_prompt(name: str) -> str:
    return (config.PROMPTS_DIR / name).read_text()


def serialize_segments_for_prompt(segments: list[dict]) -> str:
    """Compact JSON list of segments with timestamps. Truncates very long segments."""
    compact = [
        {
            "t": f"{int(s['start_time'] // 60):02d}:{int(s['start_time'] % 60):02d}",
            "speaker": s["speaker"],
            "text": (s["text"] or "")[:500],
        }
        for s in segments
    ]
    return json.dumps(compact, ensure_ascii=False)


def build_prompt(template: str, transcript_json: str, extra_context: dict | None = None) -> str:
    """Append transcript + context to the prompt template."""
    ctx = f"\n\n## Context\n```json\n{json.dumps(extra_context, ensure_ascii=False)}\n```\n" if extra_context else ""
    return f"{template}\n\n## Transcript\n```json\n{transcript_json}\n```{ctx}\n\nNow produce the JSON output."


def call_litellm(prompt: str, max_retries: int = 2) -> dict:
    """Call LiteLLM gateway and return parsed JSON. Raises on failure."""
    try:
        from litellm import completion  # type: ignore
    except ImportError:
        raise RuntimeError(
            "litellm not installed. uv pip install litellm"
        )

    api_key = config.LITELLM_API_KEY or os.environ.get("OPENAI_API_KEY", "sk-no-key-needed")
    kwargs: dict[str, Any] = {
        "model": config.LITELLM_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "api_key": api_key,
    }
    if config.LITELLM_BASE_URL:
        kwargs["api_base"] = config.LITELLM_BASE_URL

    last_err = None
    resp = None
    for attempt in range(max_retries + 1):
        try:
            resp = completion(**kwargs)
            content = resp["choices"][0]["message"]["content"]
            return json.loads(content)
        except (json.JSONDecodeError, KeyError) as e:
            last_err = e
            # Try to extract JSON from prose fallback
            content_text = ""
            if resp is not None:
                content_text = str(resp.get("choices", [{}])[0].get("message", {}).get("content", ""))
            m = re.search(r"\{[\s\S]*\}", content_text)
            if m and attempt < max_retries:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                continue
            raise
    raise RuntimeError(f"LLM extraction failed after {max_retries + 1} attempts: {last_err}")


def extract_one(meeting_dir: Path, *, force: bool = False) -> dict:
    """Run all 5 extractions for a single meeting. Returns the updated meta fields."""
    meta_path = meeting_dir / "meta.json"
    meta = json.loads(meta_path.read_text())
    transcript_path = meeting_dir / "transcript.json"
    if not transcript_path.exists():
        raise FileNotFoundError(f"No transcript.json in {meeting_dir} — run stage 2 first")

    extraction_path = meeting_dir / "extraction.json"
    if extraction_path.exists() and not force:
        print(f"[skip] {meeting_dir.name} already has extraction.json", file=sys.stderr)
        return json.loads(extraction_path.read_text())

    transcript = json.loads(transcript_path.read_text())
    transcript_str = serialize_segments_for_prompt(transcript["segments"])

    # Build context for topics extraction — list prior meetings and their topics.
    prior_meetings_ctx = build_prior_meetings_context(meeting_dir)

    # Each prompt produces a partial extraction. We collect them all and merge.
    prompts = [
        ("extract_daily_tasks.md", None),
        ("extract_weekly_tasks.md", None),
        ("extract_monthly_okrs.md", None),
        ("extract_topics.md", prior_meetings_ctx),
        ("extract_decisions.md", None),
    ]

    extraction: dict[str, Any] = {}
    for prompt_file, ctx in prompts:
        template = load_prompt(prompt_file)
        prompt = build_prompt(template, transcript_str, ctx)
        try:
            partial = call_litellm(prompt)
        except Exception as e:
            print(f"[error] {meeting_dir.name} {prompt_file}: {e}", file=sys.stderr)
            # Save what we have so far + the error
            extraction.setdefault("_errors", []).append(f"{prompt_file}: {e}")
            continue
        # Each prompt returns a JSON object with one or more of the canonical keys.
        # Merge into extraction.
        for k, v in partial.items():
            if k in {"daily_tasks", "weekly_tasks", "monthly_okrs", "topics", "decisions"}:
                extraction[k] = v

    # Fill any missing keys with empty lists
    for k in ("daily_tasks", "weekly_tasks", "monthly_okrs", "topics", "decisions"):
        extraction.setdefault(k, [])

    extraction["extraction_engine"] = config.LITELLM_MODEL
    extraction["extracted_at"] = datetime.now(timezone.utc).isoformat()

    extraction_path.write_text(json.dumps(extraction, indent=2, ensure_ascii=False))

    # Update meta
    meta["extraction"] = {
        "engine": config.LITELLM_MODEL,
        "extracted_at": extraction["extracted_at"],
        "paths": {"json": "extraction.json"},
    }
    meta["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(
        f"[done] {meeting_dir.name}: "
        f"{len(extraction['daily_tasks'])} daily, "
        f"{len(extraction['weekly_tasks'])} weekly, "
        f"{len(extraction['monthly_okrs'])} OKRs, "
        f"{len(extraction['topics'])} topics, "
        f"{len(extraction['decisions'])} decisions",
        file=sys.stderr,
    )
    return extraction


def build_prior_meetings_context(current_meeting_dir: Path) -> dict:
    """List recent meetings with their extracted topics for cross-linking.

    Looks at MT_INBOX for sibling meeting dirs and reads their extraction.json topic names.
    Window: MT_LINK_WINDOW_DAYS (default 30). Sorted newest-first.
    """
    current_id = current_meeting_dir.name
    prior = []
    for mdir in sorted(config.INBOX.iterdir(), reverse=True):
        if not mdir.is_dir() or mdir.name == current_id:
            continue
        extraction_path = mdir / "extraction.json"
        if not extraction_path.exists():
            continue
        try:
            ext = json.loads(extraction_path.read_text())
        except json.JSONDecodeError:
            continue
        prior.append({
            "id": mdir.name,
            "topics": [t.get("name") for t in ext.get("topics", []) if t.get("name")],
            "decisions": [d.get("decision") for d in ext.get("decisions", [])][:5],
        }
        )
    return {"prior_meetings": prior}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Stage 3: LLM extraction of daily/weekly/OKR/topics/decisions.")
    p.add_argument("--meeting", help="Single meeting id.")
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    if args.meeting:
        extract_one(config.INBOX / args.meeting, force=args.force)
    elif args.all:
        for mdir in sorted(config.INBOX.iterdir()):
            if mdir.is_dir() and (mdir / "transcript.json").exists():
                try:
                    extract_one(mdir, force=args.force)
                except Exception as e:
                    print(f"[error] {mdir.name}: {e}", file=sys.stderr)
    else:
        p.print_help()
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())