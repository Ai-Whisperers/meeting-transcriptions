# Reuse Opportunities from Existing AIW Repos

**Search date:** 2026-08-28
**Searched:** All 100 repos in `Ai-Whisperers` GitHub org

---

## TL;DR

There is **no existing production-ready transcription pipeline** to merge with. But I found:

1. **`Ai-Whisperers/team-tasks/ivan-tasks.md`** — your own 9-page spec doc from Nov 2025 for the **exact system we're building**. The names match: daily/weekly extraction categories, action items, decisions, OKRs. We can adopt its category taxonomy verbatim.

2. **`Ai-Whisperers/saved-transcriptions`** — 79 manual Whisper transcripts + a polished **"Pragmatic Summary"** template that's basically a hand-written example of what our extraction should produce. Use it as a few-shot example in the prompts.

3. **`Ai-Whisperers/transcriptor-agent`** — a TDD Whisper wrapper using OpenAI/Groq APIs. Useful patterns but no diarization. Code we could borrow: cascade fallback (OpenAI → Groq → local).

4. **`Ai-Whisperers/analysis-engine`** — has a `schema_extract.py` module for inferring dataset schemas. Could borrow the regex/levenshtein patterns for filename parsing (we already do similar in `01_ingest.py`).

5. **`Ai-Whisperers/jira-meta-parser`** — weak-labeling + hybrid semantic/metadata features. Pattern is reusable for our cross-meeting topic linking if we move beyond Jaccard.

6. **`Ai-Whisperers/meeting-ai-agent`** — TypeScript OpenAI Realtime API browser app. Different use case (real-time) — not directly reusable.

---

## Detailed findings

### 🟢 High value: `team-tasks/ivan-tasks.md` (the spec we should align with)

**Default branch:** `master` (not `main` — gotcha)
**Pushed:** 2025-11-24 (9 months ago)
**Path:** `team-assignments/ivan-tasks.md` → "PROJECT 2: Meeting Recording Analysis System"

The spec matches our current plan almost 1:1. The **extraction category taxonomy** is more granular than ours:

| Our prompt | Their checklist |
|---|---|
| `extract_daily_tasks.md` | "Action Items → Tasks assigned, Deadlines, Follow-ups" |
| `extract_weekly_tasks.md` | (not explicit — they conflate with action items) |
| `extract_monthly_okrs.md` | (not explicit — they call it "Projects") |
| `extract_topics.md` | "Ideas, Features, Research Topics, Client Insights" |
| `extract_decisions.md` | "Decisions Made" |

**They include categories we don't yet have:**

- **Ideas** (product, business model, marketing, partnership, content, improvement)
- **Features** (requested from clients, for products, integrations)
- **Projects** (proposals, status updates, pivots, dependencies, resources)
- **Research Topics** (techs to research, competitors, market trends)
- **Client Insights** (pain points, requirements, feedback, objections, success stories, upsell)
- **Key Quotes** (commitments, promises, strategic directions)

**Action items:** Add 4 more prompt files (`extract_ideas.md`, `extract_features.md`, `extract_projects.md`, `extract_clients.md`) — these are concrete and reusable, not YAGNI.

**The spec also defines an "Immediate Actions" output:** list outstanding action items with owners, priorities, follow-ups. Our `daily_tasks.md` already does this.

---

### 🟢 High value: `saved-transcriptions/structured-text/.../Pragmatic Summary.md`

**Default branch:** `main`
**Pushed:** 2026-03-04
**Path:** `structured-text/20 august john tips (dinner with john & family)/Pragmatic Summary.md`

This is a **hand-written example of the output we want** — same structure we should generate:

```
## Context
## Core Themes       (← topics)
## Decisions / Positions   (← decisions)
## What the MVP Must Do    (← action items)
## Heuristics
## Risks / Constraints
## Open Questions    (← could become weekly tasks)
## People/Notes      (← speakers)
```

**Action items:**
1. Commit this file as `examples/reference-extraction.md` in our repo
2. Update `prompts/*.md` to include a few-shot example from this output
3. Add an extraction prompt for **"Pragmatic Summary"** — this is what the user actually wants at the end of the day, not the structured JSON. Generate the structured JSON internally, then summarize as Markdown.

---

### 🟢 Medium value: `transcriptor-agent/transcriptor/engine.py`

**Default branch:** `main`
**Pushed:** 2026-03-04
**Stack:** Python 3.10+, FastAPI, React/Vite frontend

**Reusable:** the **cascade fallback pattern** for STT providers:

```python
# Priority list
# 1. openai API, 2. groq API, 3. local large-v3, 4. local large, 5. local medium, 6. local base
```

Their `TranscriptorEngine.transcribe()` tries OpenAI Whisper API → Groq API → local. This is more sophisticated than our single WhisperX approach.

**Borrow for Phase 2 task 2.5:** Add a `--stt-backend` flag with options `whisperx | openai | groq | auto`. If OpenAI/Groq keys are set, prefer them (faster, no local GPU). Local WhisperX as fallback.

**Limitation:** their engine has NO diarization. It returns `{text, metadata}` — no speaker labels. So it doesn't replace our pyannote integration.

---

### 🟡 Medium value: `analysis-engine` (`schema_extract.py`)

**Default branch:** `main`
**Stack:** Polars + ONNX + Prometheus

The `parquet-conversion-and-fields-mapping/pipeline/schema_extract.py` does heuristic schema inference — regex, levenshtein, semantic_map. Some patterns might overlap with our filename parser in `pipeline/01_ingest.py`. Worth a glance but unlikely to be a 1:1 reuse.

---

### 🟡 Medium value: `jira-meta-parser`

**Default branch:** `main`
**Stack:** FAISS + LightGBM LambdaMART + ColBERT

Their **weak labeling + hybrid semantic/metadata** approach for ranking is conceptually similar to what we want for cross-meeting topic linking (currently Jaccard on topic names). If Jaccard proves insufficient, we could evolve our `04_link.py` to use embeddings + LightGBM ranking like they do.

Not borrowing now — Jaccard works for our scale. File under "future upgrade".

---

### 🔴 Not reusable: `meeting-ai-agent`

**Default branch:** `main`
**Stack:** TypeScript + OpenAI Realtime API (WebRTC)
**Use case:** Real-time browser-based meeting insights (different from our batch processing)

Has its own transcription, but for real-time browser audio. No concept of historical cross-meeting linking. Different architecture entirely. Skip.

---

### 🔴 Not reusable: `wizard-academy`

**Default branch:** likely `main`
Zero Python or Markdown files at root level — only Markdown content files (training material). Not code. Skip.

---

### 🔴 Not reusable: `team-tasks`

**Default branch:** `master`
The "team-tasks" repo IS the source of the spec doc we just adopted. Not code, just checklists. No reuse beyond reading the spec.

---

## Concrete actions to take now

### A. Add new extraction prompts (from `ivan-tasks.md` taxonomy)

In `/opt/data/work/research-repos/meeting-transcriptions/prompts/`:

```bash
# Create new prompt files matching the spec
touch prompts/extract_ideas.md
touch prompts/extract_features.md
touch prompts/extract_projects.md
touch prompts/extract_clients.md
touch prompts/extract_quotes.md
```

Each prompt follows the same structure as the existing5. Total extraction cost goes from ~$0.05/meeting → ~$0.09/meeting.

### B. Save the reference example

```bash
mkdir -p examples/reference
# Manual paste of the Pragmatic Summary into examples/reference/pragmatic_summary_example.md
```

Then add to `prompts/extract_decisions.md` and others:
```markdown
## Reference output format

See `examples/reference/pragmatic_summary_example.md` for a real example
of the kind of structured summary we want to produce.
```

### C. Add STT cascade fallback (Phase 2 enhancement)

Add to `pipeline/02_transcribe.py`:
```python
STT_BACKEND = os.environ.get("MT_STT_BACKEND", "whisperx")
if STT_BACKEND == "auto":
    if os.environ.get("OPENAI_API_KEY"):
        STT_BACKEND = "openai"
    elif os.environ.get("GROQ_API_KEY"):
        STT_BACKEND = "groq"
    else:
        STT_BACKEND = "whisperx"
```

Borrow the cascade logic from `transcriptor-agent/transcriptor/engine.py`.

### D. Document the spec alignment

Add a section to our README:
```markdown
## Aligned with `Ai-Whisperers/team-tasks` spec

This pipeline implements **PROJECT 2: Meeting Recording Analysis System**
from `team-tasks/ivan-tasks.md` (Nov 2025). See:
- ivan-tasks.md § "Define Extraction Categories" → our prompts/
- ivan-tasks.md § "Build Extraction Prompts" → our prompts/
- ivan-tasks.md § "Cross-Meeting Analysis" → our pipeline/04_link.py
```

---

## What we're NOT going to reuse

| Repo | Why skip |
|---|---|
| `meeting-ai-agent` | Real-time architecture, no batch support |
| `wizard-academy` | Training material, no code |
| `analysis-engine` | Built for NPS surveys, not transcription |
| `jira-meta-parser` | Overkill for our current Jaccard-based linking |
| `solstein-v1-archive` | Archived, coaching-specific |
| `marketing-strategy` | PowerShell marketing docs |

---

## Summary

**Net new code to write:** ~0 LOC (we already have a working pipeline).

**Net new prompts to write:** 5 prompt files (`extract_ideas.md`, `extract_features.md`, `extract_projects.md`, `extract_clients.md`, `extract_quotes.md`).

**Net new docs to add:**
- `examples/reference/pragmatic_summary_example.md` (paste from saved-transcriptions)
- Section in README pointing at the spec doc

**Net new pipeline stage:** `pipeline/05_pragmatic_summary.py` — generate the Markdown summary at the end of every batch run, using all extracted fields as input. This is the user-facing output they actually want to read.

**Effort:** ~2 hours of work.