# Real audio end-to-end demo

The output of the pipeline against a **real recording** from your Drive folder
(`21-08-2026 13.02.m4a`-style voice memo, 4.6 minutes, English, one speaker).

This is the first end-to-end run on actual production data, not synthetic.

## Pipeline run

1. **Stage 1** — pulled from public Drive folder `1iuz-q9fPxup4MZjuRLSs3U3iw6FmgIF2`
2. **Stage 2** — `whisperx==3.8.6` with `small` model on CPU int8, no diarization (HF_TOKEN not set yet)
3. **Stage 3** — `openai/zai-glm-4-flash` via LiteLLM proxy at `llm.paragu-ai.com/v1`, all 10 prompts
4. **Stage 4** — cross-meeting topic linking + 11 index files
5. **Stage 5** — human-readable Markdown summary (this folder)

## What the source audio was about

A voice memo where Ivan outlines a task:
- Boss assigned: make a proposal for **Energy21** (Netherlands) ↔ **VEPEGE** (Paraguay waste poll group)
- They want an N8N workflow — actually a **ticket analyzer AI** that:
  - Answers client tickets
  - Auto-fixes bugs where possible
  - Auto-creates stories/tickets for things it can't fix
  - Only escalates the hard stuff to humans
- Pricing target: "put us in positive numbers"
- Marketing angle: AI Whispers are "magicians of AI" — use our own use as proof
- Bonus: Energy21 will need courses / training on how the workflows work

## What the pipeline extracted

| Section | Count | Notes |
|---------|-------|-------|
| daily_tasks | 0 | None for "today" — this is a brainstorm, not a standup |
| weekly_tasks | 1 | "Create proposal for Energy21" |
| monthly_okrs | 3 | N8N workflow + proposal prep + marketing positioning |
| topics | 11 | Energy21, VEPEGE, ticket analyzer, etc. |
| decisions | 5 | Each with `why` rationale and timestamp |
| ideas | 5 | 4 process + 1 marketing, novelty + impact scored |
| features | 4 | All status=planned, requested_by=Energy21 |
| projects | 1 | `energy21-vepege-n8n-workflow`, status=proposed |
| clients | 5 | Energy21 + VEPEGE named, all flagged for follow-up |
| quotes | 4 | Real verbatim lines with type + context |

## Performance notes

- WhisperX `small` model on CPU: ~7 minutes for 4.6 min of audio (1.5× realtime)
- `medium` model OOMs on the 7.8GB sandbox at the alignment stage
- `zai-glm-4-flash` hallucinates some dates (said `2023-W36` for a 2026 meeting) — fixable with prompt grounding or upgrade to Sonnet when credits available
- Phantom-client filter works correctly: this meeting has 2 named clients (Energy21, VEPEGE), all insights are real

## Files

- `meta.json` — the meeting record after stage 2 (transcript, speakers, duration)
- `transcript.txt` — the raw transcript (522 word tokens)
- `extraction.json` — all 10 sections per the schema
- `pragmatic_summary.md` — the human-readable digest (what stage 5 generates)

This is the **first real-world validation** that the pipeline produces useful output,
not just test fixtures.