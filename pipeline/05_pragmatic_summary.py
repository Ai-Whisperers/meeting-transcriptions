"""Stage 5: Pragmatic summary.

For every meeting in MT_INBOX that has an extraction.json, generate a
Markdown summary that follows the format from
`saved-transcriptions/structured-text/.../Pragmatic Summary.md`.

This is the human-readable digest — what you actually want to read.

Sections produced (all conditional on whether the meeting contains items):
  - Context              (always)
  - Core Themes          (from topics)
  - Decisions / Positions (from decisions)
  - What the MVP Must Do (from daily_tasks + weekly_tasks + OKRs)
  - Ideas                (from ideas)
  - Features             (from features)
  - Projects             (from projects)
  - Client Insights      (from clients)
  - Key Quotes           (from quotes)
  - Risks / Constraints  (from clients with severity=high|critical)
  - Open Questions       (from OKRs without metric, or low-confidence tasks)
  - People               (from speakers in meta.json)

The summary is written to:
  ${MT_INDEX}/summaries/<meeting_id>.md
And a roll-up index at:
  ${MT_INDEX}/pragmatic_index.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline import config  # noqa: E402


def load_meeting(meeting_dir: Path) -> tuple[dict | None, dict | None]:
    meta_path = meeting_dir / "meta.json"
    if not meta_path.exists():
        return None, None
    meta = json.loads(meta_path.read_text())
    extraction_path = meeting_dir / "extraction.json"
    ext = json.loads(extraction_path.read_text()) if extraction_path.exists() else None
    return meta, ext


def fmt_date(iso_date: str | None) -> str:
    if not iso_date:
        return "(no date)"
    try:
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return iso_date


def render_summary(meeting_id: str, meta: dict, ext: dict | None) -> str:
    """Render a single meeting's pragmatic summary."""
    lines: list[str] = []
    title = meta.get("title") or meeting_id
    date = fmt_date(meta.get("date"))
    source = meta.get("source", {})
    subfolder = source.get("drive_subfolder", "")
    duration = meta.get("duration_sec")
    language = meta.get("language") or "?"

    # --- Header ---
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"_Date: **{date}** | Duration: {duration}s | Language: {language}"
                 + (f" | Subfolder: **{subfolder}**" if subfolder else ""))
    lines.append(f"_Meeting id: `{meeting_id}`_")
    lines.append("")

    if ext is None:
        lines.append("_No extraction available — run stage 3 first._")
        return "\n".join(lines) + "\n"

    # Apply the same confidence filter as stage 4 — keeps summaries consistent
    # with indexes.
    import importlib
    stage4 = importlib.import_module("pipeline.04_link")
    ext = stage4.filter_low_confidence(ext)

    # --- Context ---
    daily = ext.get("daily_tasks", [])
    weekly = ext.get("weekly_tasks", [])
    okrs = ext.get("monthly_okrs", [])
    decisions = ext.get("decisions", [])
    topics = ext.get("topics", [])
    ideas = ext.get("ideas", [])
    features = ext.get("features", [])
    projects = ext.get("projects", [])
    clients = ext.get("clients", [])
    quotes = ext.get("quotes", [])

    total_actionable = len(daily) + len(weekly) + len(okrs)
    lines.append("## Context")
    lines.append("")
    lines.append(
        f"* **Participants:** inferred from speakers in transcript"
    )
    if subfolder:
        lines.append(f"* **Cadence:** {subfolder} meeting (from Drive subfolder)")
    lines.append(
        f"* **Volume:** {len(daily)} daily + {len(weekly)} weekly + {len(okrs)} OKR "
        f"= **{total_actionable} actionable items**, "
        f"{len(decisions)} decisions, {len(topics)} topics"
    )
    lines.append(f"* **Ideas/Features/Projects:** {len(ideas)} / {len(features)} / {len(projects)}")
    if clients:
        high_sev = sum(1 for c in clients if c.get("severity") in ("high", "critical"))
        lines.append(f"* **Client insights:** {len(clients)} ({high_sev} high-severity)")
    lines.append("")

    # --- Core Themes (topics) ---
    if topics:
        lines.append("## Core Themes")
        lines.append("")
        for t in topics:
            name = t.get("name", "?")
            status = t.get("status", "open")
            summary = t.get("summary", "")
            t_line = f"* **{name}** — `{status}`"
            if summary:
                t_line += f": {summary}"
            lines.append(t_line)
        lines.append("")

    # --- Decisions / Positions ---
    if decisions:
        lines.append("## Decisions / Positions")
        lines.append("")
        for d in decisions:
            txt = d.get("decision", "?")
            who = d.get("made_by", "?")
            ts = d.get("timestamp", "")
            rationale = d.get("rationale", "")
            line = f"* {txt} _(by {who}"
            if ts:
                line += f" at {ts}"
            line += ")_"
            if rationale:
                line += f"\n  - _Why:_ {rationale}"
            lines.append(line)
        lines.append("")

    # --- What needs to happen (daily + weekly + OKRs) ---
    if daily or weekly or okrs:
        lines.append("## What Needs To Happen")
        lines.append("")
        if daily:
            lines.append("**Today / Tomorrow:**")
            for t in daily:
                owner = t.get("owner") or "?"
                deadline = t.get("deadline", "")
                conf = t.get("confidence")
                conf_str = f" _(confidence {conf:.1f})_" if conf is not None else ""
                dl = f" — deadline: {deadline}" if deadline else ""
                lines.append(f"  - [{owner}] {t.get('task', '?')}{dl}{conf_str}")
            lines.append("")
        if weekly:
            lines.append("**This Week / Next Week:**")
            for t in weekly:
                owner = t.get("owner") or "?"
                week = t.get("week", "")
                conf = t.get("confidence")
                conf_str = f" _(confidence {conf:.1f})_" if conf is not None else ""
                w = f" — week {week}" if week else ""
                lines.append(f"  - [{owner}] {t.get('task', '?')}{w}{conf_str}")
            lines.append("")
        if okrs:
            lines.append("**Monthly Objectives (OKRs):**")
            for o in okrs:
                owner = o.get("owner") or "?"
                target = o.get("target_date", "")
                metric = o.get("metric", "")
                t = f" — target: {target}" if target else ""
                m = f" — metric: {metric}" if metric else ""
                lines.append(f"  - [{owner}] **{o.get('objective', '?')}** → KR: {o.get('kr', '?')}{t}{m}")
            lines.append("")

    # --- Ideas ---
    if ideas:
        lines.append("## Ideas Raised")
        lines.append("")
        # Group by category
        by_cat: dict[str, list[dict]] = {}
        for i in ideas:
            by_cat.setdefault(i.get("category", "other"), []).append(i)
        for cat, items in by_cat.items():
            lines.append(f"**{cat}:**")
            for i in items:
                by = i.get("raised_by") or "?"
                novelty = i.get("novelty", "")
                impact = i.get("estimated_impact", "")
                meta_str = []
                if novelty: meta_str.append(f"novelty={novelty}")
                if impact: meta_str.append(f"impact={impact}")
                ms = f" ({', '.join(meta_str)})" if meta_str else ""
                lines.append(f"  - _{by}_: {i.get('idea', '?')}{ms}")
            lines.append("")

    # --- Features ---
    if features:
        lines.append("## Features Discussed")
        lines.append("")
        for f in features:
            feature = f.get("feature", "?")
            product = f.get("product") or ""
            status = f.get("status", "?")
            req_by = f.get("requested_by") or ""
            complexity = f.get("complexity", "")
            line = f"* [{status}] **{feature}**"
            if product: line += f" _({product})_"
            if req_by: line += f" _(requested by {req_by})_"
            if complexity: line += f" — {complexity}"
            lines.append(line)
        lines.append("")

    # --- Projects ---
    if projects:
        lines.append("## Projects")
        lines.append("")
        for p in projects:
            name = p.get("name", "?")
            status = p.get("status", "?")
            owner = p.get("owner") or "?"
            desc = p.get("description", "")
            milestone = p.get("next_milestone") or ""
            blockers = p.get("blockers", [])
            line = f"* **{name}** — `{status}` _(owner: {owner})_"
            if desc: line += f"\n  - {desc}"
            if milestone: line += f"\n  - Next milestone: {milestone}"
            if blockers: line += f"\n  - Blockers: {', '.join(blockers)}"
            lines.append(line)
        lines.append("")

    # --- Client Insights ---
    if clients:
        lines.append("## Client Insights")
        lines.append("")
        # Sort by severity descending
        sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_clients = sorted(clients, key=lambda c: sev_order.get(c.get("severity", "medium"), 2))
        for c in sorted_clients:
            insight = c.get("insight", "?")
            cat = c.get("category", "?")
            client = c.get("client", "?")
            sev = c.get("severity", "")
            fu = c.get("follow_up_needed")
            line = f"* **{client}** _({cat}, {sev})_: {insight}"
            if fu: line += f" — ⚠️ follow-up needed"
            if c.get("follow_up_owner"): line += f" (owner: {c['follow_up_owner']})"
            lines.append(line)
        lines.append("")

    # --- Key Quotes ---
    if quotes:
        lines.append("## Key Quotes")
        lines.append("")
        # Sort: commitments first, then strategic, then pivotal, then rest
        type_order = {"commitment": 0, "client-promise": 1, "strategic": 2,
                      "pivotal": 3, "accountability": 4, "opinion": 5}
        sorted_quotes = sorted(quotes, key=lambda q: type_order.get(q.get("type", "opinion"), 6))
        for q in sorted_quotes:
            quote = q.get("quote", "?")
            speaker = q.get("speaker") or "?"
            qtype = q.get("type", "?")
            context = q.get("context", "")
            ts = q.get("timestamp", "")
            line = f"> _{speaker} ({qtype}"
            if ts: line += f" @ {ts}"
            line += f"):_ \"{quote}\""
            lines.append(line)
            if context:
                lines.append(f"> _(context: {context})_")
            lines.append("")

    # --- Risks / Constraints (high/critical client insights) ---
    risks = [c for c in clients if c.get("severity") in ("high", "critical")]
    if risks:
        lines.append("## Risks / Constraints")
        lines.append("")
        for c in risks:
            lines.append(f"* {c.get('insight', '?')} _(severity: {c.get('severity', '?')})_")
        lines.append("")

    # --- Open Questions ---
    open_questions = [o for o in okrs if not o.get("metric")]
    open_questions += [t for t in daily + weekly if t.get("confidence", 1.0) < 0.5]
    if open_questions:
        lines.append("## Open Questions")
        lines.append("")
        for o in open_questions[:10]:
            if "objective" in o:  # OKR without metric
                lines.append(f"* {o.get('objective', '?')} — _no metric yet_")
            else:  # low-confidence task
                lines.append(f"* {o.get('task', '?')} _(low confidence — clarify)_")
        lines.append("")

    # --- People (from speakers in meta.json) ---
    speakers = meta.get("speakers", [])
    if speakers:
        lines.append("## People")
        lines.append("")
        for s in speakers:
            label = s.get("label", "?")
            name = s.get("inferred_name") or "—"
            conf = s.get("confidence")
            pct = s.get("talk_pct")
            turns = s.get("turns")
            extras = []
            if pct is not None: extras.append(f"{pct}% talk time")
            if turns: extras.append(f"{turns} turns")
            if conf is not None: extras.append(f"name confidence {conf:.0%}")
            ex = f" ({', '.join(extras)})" if extras else ""
            lines.append(f"* **{label}** → {name}{ex}")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"_Generated {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")

    return "\n".join(lines)


def render_index(summaries: list[dict]) -> str:
    """Roll-up index of all meeting summaries, newest first."""
    lines: list[str] = ["# Meeting Pragmatic Summaries — Index", ""]
    lines.append(f"_Generated {datetime.now(timezone.utc).isoformat()}_")
    lines.append("")
    lines.append(f"_Total: **{len(summaries)}** meeting(s)_")
    lines.append("")

    # Group by month
    by_month: dict[str, list[dict]] = {}
    for s in summaries:
        month = s["date"][:7] if s["date"] else "unknown"
        by_month.setdefault(month, []).append(s)

    for month in sorted(by_month.keys(), reverse=True):
        lines.append(f"## {month}")
        lines.append("")
        for s in by_month[month]:
            mid = s["meeting_id"]
            date = s["date"]
            title = s["title"]
            counts = s["counts"]
            extras = []
            for k in ("decisions", "daily_tasks", "weekly_tasks", "monthly_okrs",
                      "ideas", "features", "projects", "clients", "quotes"):
                if counts.get(k):
                    extras.append(f"{counts[k]} {k.split('_')[0]}")
            counts_str = ", ".join(extras) if extras else "(empty)"
            lines.append(f"* **{date}** [{title}](summaries/{mid}.md) — {counts_str}")
        lines.append("")

    return "\n".join(lines) + "\n"


def summarize_one(meeting_dir: Path, *, force: bool = False) -> dict | None:
    meta, ext = load_meeting(meeting_dir)
    if meta is None:
        print(f"[skip] {meeting_dir.name}: no meta.json", file=sys.stderr)
        return None
    meeting_id = meeting_dir.name
    out_dir = config.INDEX / "summaries"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{meeting_id}.md"
    if out_path.exists() and not force:
        return None
    content = render_summary(meeting_id, meta, ext)
    out_path.write_text(content, encoding="utf-8")
    print(f"[done] summary {meeting_id} -> {out_path}", file=sys.stderr)
    if ext:
        counts = {k: len(ext.get(k, [])) for k in
                  ("daily_tasks", "weekly_tasks", "monthly_okrs", "decisions",
                   "ideas", "features", "projects", "clients", "quotes", "topics")}
    else:
        counts = {}
    return {
        "meeting_id": meeting_id,
        "date": meta.get("date", ""),
        "title": meta.get("title", meeting_id),
        "counts": counts,
    }


def write_index(summaries: list[dict]) -> Path:
    out_path = config.INDEX / "pragmatic_index.md"
    out_path.write_text(render_index(summaries), encoding="utf-8")
    print(f"[done] index -> {out_path} ({len(summaries)} meetings)", file=sys.stderr)
    return out_path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Stage 5: Generate human-readable pragmatic summaries.")
    p.add_argument("--meeting", help="Single meeting id.")
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    summaries: list[dict] = []

    if args.meeting:
        mdir = config.INBOX / args.meeting
        s = summarize_one(mdir, force=args.force)
        if s: summaries.append(s)
    elif args.all:
        for mdir in sorted(config.INBOX.iterdir()):
            if not mdir.is_dir():
                continue
            s = summarize_one(mdir, force=args.force)
            if s: summaries.append(s)
    else:
        p.print_help()
        return 1

    if summaries:
        write_index(summaries)
    else:
        # Always rebuild the index even if no new summaries, in case meta changed
        all_summaries = []
        if config.INDEX.exists():
            for spath in (config.INDEX / "summaries").glob("*.md"):
                mid = spath.stem
                mdir = config.INBOX / mid
                if not mdir.exists():
                    continue
                meta, ext = load_meeting(mdir)
                if not meta:
                    continue
                all_summaries.append({
                    "meeting_id": mid,
                    "date": meta.get("date", ""),
                    "title": meta.get("title", mid),
                    "counts": {k: len(ext.get(k, [])) if ext else 0 for k in
                               ("daily_tasks", "weekly_tasks", "monthly_okrs", "decisions",
                                "ideas", "features", "projects", "clients", "quotes", "topics")},
                })
            if all_summaries:
                write_index(all_summaries)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())