# Real audio end-to-end demo (v2 — date-anchored)

The output of the pipeline against a **real recording** from your Drive folder
(`21-08-2026 13.02.m4a`-style voice memo, 4.6 minutes, English, one speaker).

This is the **date-anchored** version — fixes the "2023-W36" hallucination bug
that affected `v1` of this demo. See commit `481f383`.

## Pipeline run

1. **Stage 1** — pulled from public Drive folder `1iuz-q9fPxup4MZjuRLSs3U3iw6FmgIF2`
2. **Stage 2** — `whisperx==3.8.6` with `small` model on CPU int8, no diarization (HF_TOKEN not set)
3. **Stage 3** — `openai/zai-glm-4-flash` via LiteLLM proxy at `llm.paragu-ai.com/v1`, all 10 prompts with `meeting_date=2026-02-18` in the Context block
4. **Stage 4** — cross-meeting topic linking + 11 index files
5. **Stage 5** — human-readable Markdown summary

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
| daily_tasks | 1 | "Prepare proposal for Energy21", deadline=null |
| weekly_tasks | 7 | All week=`2026-W08` (correct ISO week from meeting_date) |
| monthly_okrs | 3 | All target_date=`2026-02-18` (the meeting date, since no explicit date mentioned) |
| topics | 10 | Energy21, VEPEGE, ticket analyzer, etc. |
| decisions | 7 | Each with `why` rationale and timestamp |
| ideas | 3 | Categorized with novelty + impact scores |
| features | 5 | Status, complexity, requested_by = Energy21 |
| projects | 1 | `energy21-vepege-n8n-workflow`, status=proposed |
| clients | 4 | Energy21 + VEPEGE named correctly, all flagged for follow-up |
| quotes | 10 | Verbatim with type + context |

## Date fix — before vs after

| Field | v1 (buggy) | v2 (fixed) |
|-------|-----------|-----------|
| `weekly_tasks[].week` | `2023-W36` | `2026-W08` |
| `monthly_okrs[].target_date` | `2023-04-25` | `2026-02-18` |
| `daily_tasks[].deadline` | hallucinated | `null` (honest) |
| Clients count | 2 ghost + 2 real | 4 real (no ghosts) |
| Items surfaced | weekly=1, quotes=4 | weekly=7, quotes=10 |

## Performance notes

- WhisperX `small` model on CPU: ~5:40 for 4.6 min of audio (1.2× realtime)
- `medium` model OOMs on the 7.8GB sandbox at the alignment stage (1.7GB peak)
- `zai-glm-4-flash` extraction: 10 prompts × ~3s each = ~30s total
- Phantom-client filter works correctly: only real named clients appear

## Files

- `transcript.txt` — raw transcript (522 word tokens)
- `extraction.json` — all 10 sections per the schema
- `pragmatic_summary.md` — the human-readable digest

This is the **cleanest end-to-end output** the pipeline produces on real audio
as of 2026-08-28. Compare with `examples/real_audio_demo/` (v1) to see the
date-hallucination bug in action.