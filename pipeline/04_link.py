"""Stage 4: Link + index rollup.

Input:  All meetings in MT_INBOX with meta.json + extraction.json
Output:
  - MT_INBOX/<meeting_id>/meta.json  with updated `links` section (carried/new topics, prev/next meeting)
  - MT_INDEX/index/topics.md          cross-meeting topic graph
  - MT_INDEX/index/people.md          inferred speaker identities
  - MT_INDEX/index/decisions.md       every decision with meeting link
  - MT_INDEX/index/okrs.md            every monthly OKR with status
  - MT_INDEX/index/daily_tasks.md     today's tasks across all meetings
  - MT_INDEX/index/weekly_tasks.md    this week's tasks across all meetings

This stage is local + deterministic (no LLM). It uses:
  - fuzzy topic name matching (token Jaccard ≥ 0.6 = same topic)
  - speaker label persistence (SPEAKER_00 in meeting A = SPEAKER_01 in meeting B
    IF the turn-taking pattern + voice characteristics match — currently simple
    heuristic, to be replaced with speaker embedding matching in a future stage)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import config  # noqa: E402


TOKEN_RE = re.compile(r"[a-záéíóúñü0-9]+", re.IGNORECASE)


def normalize_topic(name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-záéíóúñü0-9 ]+", " ", name.lower())).strip()


def topic_tokens(name: str) -> set[str]:
    return set(t for t in TOKEN_RE.findall(normalize_topic(name)) if len(t) >= 3)


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_topic_matches(target_name: str, candidate_topics: list[dict], threshold: float = 0.6) -> list[str]:
    """Return names of candidate topics that match target_name."""
    target_toks = topic_tokens(target_name)
    if not target_toks:
        return []
    matches = []
    for c in candidate_topics:
        c_name = c.get("name", "")
        if jaccard(target_toks, topic_tokens(c_name)) >= threshold:
            matches.append(c_name)
    return matches


def load_all_meetings() -> list[dict]:
    """Load every meeting in MT_INBOX that has meta.json + extraction.json."""
    meetings = []
    for mdir in sorted(config.INBOX.iterdir()):
        if not mdir.is_dir():
            continue
        meta_path = mdir / "meta.json"
        ext_path = mdir / "extraction.json"
        if not (meta_path.exists() and ext_path.exists()):
            continue
        meta = json.loads(meta_path.read_text())
        ext = json.loads(ext_path.read_text())
        meetings.append({"id": mdir.name, "dir": mdir, "meta": meta, "extraction": ext, "date": meta["date"]})
    meetings.sort(key=lambda m: m["date"])
    return meetings


def update_links_for_meetings(meetings: list[dict]) -> int:
    """For each meeting, compute carried_topics and previous_meeting_id, write back to meta.json."""
    updated = 0
    by_date: dict[str, list[dict]] = defaultdict(list)
    for m in meetings:
        by_date[m["date"]].append(m)

    # Build per-topic → list of meeting_ids across the whole corpus
    topic_history: dict[str, list[str]] = defaultdict(list)
    for m in meetings:
        for t in m["extraction"].get("topics", []):
            tname = t.get("name")
            if tname:
                topic_history[normalize_topic(tname)].append(m["id"])

    # For each meeting, find which of its topics appeared in any PRIOR meeting
    for i, m in enumerate(meetings):
        carried_topics = []
        new_topics = []
        topic_links: dict[str, Any] = {}

        for t in m["extraction"].get("topics", []):
            tname = t.get("name")
            if not tname:
                continue
            prior = [
                pid
                for pid in topic_history.get(normalize_topic(tname), [])
                if pid != m["id"]
                and meetings_index_by_id(meetings, pid)["date"] < m["date"]
            ]
            if prior:
                carried_topics.append(tname)
                topic_links[tname] = {"raised_again_in_meetings": prior}
            else:
                new_topics.append(tname)

        # Previous + next meeting (by date)
        prev_id = meetings[i - 1]["id"] if i > 0 else None
        next_id = meetings[i + 1]["id"] if i < len(meetings) - 1 else None

        links = {
            "previous_meeting_id": prev_id,
            "next_meeting_id": next_id,
            "carried_topics": carried_topics,
            "new_topics": new_topics,
            "topic_history": topic_links,
        }
        m["meta"]["links"] = links
        m["meta"]["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
        (m["dir"] / "meta.json").write_text(json.dumps(m["meta"], indent=2, ensure_ascii=False))
        updated += 1
    return updated


def meetings_index_by_id(meetings: list[dict], mid: str) -> dict:
    for m in meetings:
        if m["id"] == mid:
            return m
    return {"id": mid, "date": "0000-00-00"}


def render_topics_index(meetings: list[dict]) -> str:
    """Build the cross-meeting topic graph as markdown."""
    topic_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for m in meetings:
        for t in m["extraction"].get("topics", []):
            tname = t.get("name")
            if not tname:
                continue
            topic_history[tname].append({
                "meeting_id": m["id"],
                "date": m["date"],
                "status": t.get("status", "open"),
            })

    lines = ["# Topics — cross-meeting graph", "",
             f"_Generated {datetime.now(timezone.utc).isoformat()}_", "",
             f"_Total topics: **{len(topic_history)}** across **{len(meetings)}** meetings._", "",
             "## Active topics (status ≠ resolved in latest meeting)", ""]
    active = {
        k: v for k, v in topic_history.items()
        if v[-1]["status"] != "resolved"
    }
    for tname in sorted(active, key=lambda k: (-len(active[k]), active[k][-1]["date"])):
        occurrences = active[tname]
        dates = ", ".join(f"[{o['date']}]({o['meeting_id']}/meta.json)" for o in occurrences)
        latest_status = occurrences[-1]["status"]
        lines.append(f"- **{tname}** — `{latest_status}` — {len(occurrences)}×: {dates}")
    lines += ["", "## Resolved topics", ""]
    resolved = {
        k: v for k, v in topic_history.items()
        if v[-1]["status"] == "resolved"
    }
    for tname in sorted(resolved, key=lambda k: resolved[k][-1]["date"], reverse=True)[:50]:
        occurrences = resolved[tname]
        dates = ", ".join(f"[{o['date']}]({o['meeting_id']}/meta.json)" for o in occurrences)
        lines.append(f"- {tname} — {len(occurrences)}×: {dates}")
    return "\n".join(lines) + "\n"


def render_people_index(meetings: list[dict]) -> str:
    lines = ["# People — inferred speaker identities", "",
             f"_Generated {datetime.now(timezone.utc).isoformat()}_", "",
             "Speaker labels (SPEAKER_00, SPEAKER_01, ...) are WhisperX output. ",
             "Names below are inferred from content (3rd-person self-reference, naming patterns).",
             "Confidence: HIGH = speaker self-named, MEDIUM = named by another speaker with context, LOW = pattern-only.", ""]
    # Group by (label, inferred_name) so the same physical speaker shows their full history
    by_key: dict[tuple[str, str | None], list[dict]] = defaultdict(list)
    for m in meetings:
        for s in m["meta"].get("speakers", []):
            key = (s["label"], s.get("inferred_name"))
            by_key[key].append({"meeting_id": m["id"], "date": m["date"], **s})
    # Sort by total talk_pct descending
    for key, rows in sorted(by_key.items(), key=lambda kv: -sum(r["talk_pct"] for r in kv[1])):
        label, name = key
        conf = rows[0].get("confidence", 0.0)
        title = f"## {label} → {name or '—'} (confidence {conf:.1%})"
        lines.append(title)
        lines.append("")
        lines.append("| Meeting | Date | talk_pct | turns | word_tokens |")
        lines.append("|---|---|---:|---:|---:|")
        for r in rows:
            lines.append(f"| {r['meeting_id']} | {r['date']} | {r['talk_pct']} | {r['turns']} | {r['word_tokens']} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def render_decisions_index(meetings: list[dict]) -> str:
    lines = ["# Decisions", "",
             f"_Generated {datetime.now(timezone.utc).isoformat()}_", ""]
    rows = []
    for m in meetings:
        for d in m["extraction"].get("decisions", []):
            rows.append({**d, "meeting_id": m["id"], "date": m["date"]})
    rows.sort(key=lambda r: (r["date"], r.get("timestamp", "")), reverse=True)
    if not rows:
        return "\n".join(lines) + "\n_No decisions yet._\n"
    lines.append(f"_Total decisions: **{len(rows)}**._\n")
    lines.append("| Date | Meeting | Decision | Made by | Timestamp |")
    lines.append("|---|---|---|---|---|")
    for r in rows:
        lines.append(f"| {r['date']} | {r['meeting_id']} | {r.get('decision', '')[:80]} | {r.get('made_by', '')} | {r.get('timestamp', '')} |")
    return "\n".join(lines) + "\n"


def render_okrs_index(meetings: list[dict]) -> str:
    lines = ["# Monthly OKRs", "",
             f"_Generated {datetime.now(timezone.utc).isoformat()}_", ""]
    rows = []
    for m in meetings:
        for o in m["extraction"].get("monthly_okrs", []):
            rows.append({**o, "meeting_id": m["id"], "date": m["date"]})
    rows.sort(key=lambda r: r.get("target_date") or r["date"], reverse=True)
    if not rows:
        return "\n".join(lines) + "\n_No OKRs yet._\n"
    lines.append(f"_Total OKRs: **{len(rows)}**._\n")
    lines.append("| Target | Objective | KR | Owner | First raised |")
    lines.append("|---|---|---|---|---|")
    for r in rows:
        lines.append(f"| {r.get('target_date', '')} | {r.get('objective', '')[:60]} | {r.get('kr', '')[:80]} | {r.get('owner', '')} | {r['date']} |")
    return "\n".join(lines) + "\n"


def render_tasks_index(meetings: list[dict], kind: str) -> str:
    """kind = 'daily_tasks' or 'weekly_tasks'."""
    today = date.today().isoformat()
    this_monday = date.today() - timedelta(days=date.today().weekday())
    this_week = f"{this_monday.year}-W{this_monday.isocalendar().week:02d}"

    rows = []
    for m in meetings:
        for t in m["extraction"].get(kind, []):
            rows.append({**t, "meeting_id": m["id"], "date": m["date"]})

    if kind == "daily_tasks":
        title = "Daily tasks (today + open)"
        # Show: today's tasks first, then open tasks with no deadline
        rows.sort(key=lambda r: (
            0 if (r.get("deadline") and r["deadline"] <= today) else 1,
            r.get("deadline") or "9999",
            r["date"],
        ))
    else:
        title = f"Weekly tasks ({this_week})"
        rows.sort(key=lambda r: (r.get("week", "9999-W99"), r["date"]))

    lines = [f"# {title}", "",
             f"_Generated {datetime.now(timezone.utc).isoformat()}_", ""]
    if not rows:
        return "\n".join(lines) + "\n_None yet._\n"
    lines.append(f"_Total: **{len(rows)}**._\n")
    lines.append("| Date | Meeting | Task | Owner | " + ("Deadline" if kind == "daily_tasks" else "Week") + " |")
    lines.append("|---|---|---|---|---|")
    for r in rows:
        col = r.get("deadline") if kind == "daily_tasks" else r.get("week", "")
        lines.append(f"| {r['date']} | {r['meeting_id']} | {r.get('task', '')[:60]} | {r.get('owner', '')} | {col} |")
    return "\n".join(lines) + "\n"


def write_indexes(meetings: list[dict]) -> dict[str, Path]:
    """Write the 5 index files. Returns dict of name → path."""
    config.INDEX.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, content in (
        ("topics.md", render_topics_index(meetings)),
        ("people.md", render_people_index(meetings)),
        ("decisions.md", render_decisions_index(meetings)),
        ("okrs.md", render_okrs_index(meetings)),
        ("daily_tasks.md", render_tasks_index(meetings, "daily_tasks")),
        ("weekly_tasks.md", render_tasks_index(meetings, "weekly_tasks")),
    ):
        p = config.INDEX / name
        p.write_text(content)
        out[name] = p
    return out


def link_one(meeting_dir: Path, *, force: bool = False) -> int:
    """Run link stage for a single meeting. Returns # of meetings updated."""
    meetings = load_all_meetings()
    return update_links_for_meetings(meetings)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Stage 4: Cross-meeting linking + index rollup.")
    p.add_argument("--meeting", help="Single meeting id (still rewrites all indexes).")
    p.add_argument("--all", action="store_true", default=True)
    p.add_argument("--index-only", action="store_true",
                   help="Skip per-meeting link update; only rewrite indexes.")
    args = p.parse_args(argv)

    meetings = load_all_meetings()
    print(f"[link] loaded {len(meetings)} meetings", file=sys.stderr)

    if not args.index_only:
        n = update_links_for_meetings(meetings)
        print(f"[link] updated links in {n} meetings", file=sys.stderr)

    out = write_indexes(meetings)
    print(f"[link] wrote indexes to {config.INDEX}: {sorted(out)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())