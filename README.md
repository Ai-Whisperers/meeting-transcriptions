# Meeting Transcriptions

Self-hosted pipeline that takes meeting audios and produces a structured, searchable record:

1. **Daily tasks** (today/tomorrow) — actionable in 24-48h
2. **Weekly tasks** — this week / next week
3. **Monthly OKRs** — measurable key results
4. **Topics** — cross-meeting discussion graph
5. **Decisions** — what was decided, by whom, when

## The shape of the system

```
                  ┌──────────────────────────────┐
                  │  Google Drive folder         │
                  │  1iuz-q9fPxup4MZjuRLSs3U3iw6FmgIF2
                  └──────────────┬───────────────┘
                                 │ service account / public-link / local
                                 ▼
                  ┌──────────────────────────────┐
                  │  /opt/data/inbox/meetings/   │
                  │  2026-08-28_aiw-strategy/    │
                  │    audio.mp3                  │
                  │    meta.json                  │
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────▼───────────────┐
                  │  Stage 2: WhisperX (medium)  │
                  │  + pyannote diarization      │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  transcript.json + transcript.txt + transcript.vtt
                                 │
                  ┌──────────────▼───────────────┐
                  │  Stage 3: LiteLLM extraction │
                  │  10 prompts: daily/weekly/   │
                  │  OKR/decisions/ideas/        │
                  │  features/projects/clients/  │
                  │  quotes/topics                │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  extraction.json
                                 │
                  ┌──────────────▼───────────────┐
                  │  Stage 4: cross-meeting      │
                  │  topic linking + index rollup│
                  └──────────────┬───────────────┘
                                 │
                  ┌──────────────▼───────────────┐
                  │  Stage 5: pragmatic summary  │
                  │  human-readable Markdown     │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  /opt/data/indexed/meetings/
                    topics.md
                    people.md
                    decisions.md
                    okrs.md
                    daily_tasks.md
                    weekly_tasks.md
                    ideas.md
                    features.md
                    projects.md
                    clients.md
                    quotes.md
                    summaries/<meeting_id>.md
                    pragmatic_index.md
```

## Source of truth

This pipeline implements **PROJECT 2: Meeting Recording Analysis System** from
[`Ai-Whisperers/team-tasks/team-assignments/ivan-tasks.md`](https://github.com/Ai-Whisperers/team-tasks/blob/master/team-assignments/ivan-tasks.md)
(Nov 2025 spec). The extraction taxonomy — ideas, features, projects, clients,
quotes, tasks, decisions, OKRs, topics — matches Ivan's original checklist.

The pragmatic-summary output format is modeled after
[this hand-written example](examples/reference/pragmatic_summary_example.md)
from `Ai-Whisperers/saved-transcriptions` (Aug 2025).

## Quickstart

### 1. Local-only (no Drive) — fastest path to first result

```bash
# Drop a meeting audio into any directory, then:
python -m pipeline.01_ingest --file /path/to/2026-08-28_aiw-strategy.mp3

# Transcribe + diarize
python -m pipeline.02_transcribe --all

# Extract (10 prompts)
python -m pipeline.03_extract --all

# Build indexes
python -m pipeline.04_link

# Generate pragmatic summaries
python -m pipeline.05_pragmatic_summary --all

# Or run everything end-to-end:
bash run_all.sh
```

### 2. Public Drive folder (anyone-with-link) — zero setup, RECOMMENDED

```bash
# Default folder ID is already set in pipeline/config.py
python -m pipeline.01_ingest --source drive-public

# Or override the folder
MT_DRIVE_FOLDER=1iuz-q9fPxup4MZjuRLSs3U3iw6FmgIF2 \
  python -m pipeline.01_ingest --source drive-public

# Then run the rest:
python -m pipeline.02_transcribe --all
python -m pipeline.03_extract --all
python -m pipeline.04_link
```

No service account, no JSON keys, no OAuth — Drive's `embeddedfolderview`
endpoint returns the folder listing for any "anyone with the link can view" folder.

### 3. Private Drive folder (service account)

See [`docs/DRIVE-SETUP.md`](docs/DRIVE-SETUP.md) for the full walkthrough.
Short version: create a service account in Google Cloud, share the folder
with its `client_email` as Viewer, point `MT_GOOGLE_SA_JSON` at the JSON key.

## Repository layout

```
meeting-transcriptions/
├── README.md                       # this file
├── run_all.sh                      # end-to-end orchestrator
├── schema/
│   ├── meeting.schema.json         # canonical per-meeting shape
│   ├── extraction.schema.json      # LLM output validation
│   └── meta.schema.json            # pipeline run metadata
├── prompts/
│   ├── extract_daily_tasks.md      # 10 extraction prompt templates
│   ├── extract_weekly_tasks.md
│   ├── extract_monthly_okrs.md
│   ├── extract_topics.md
│   ├── extract_decisions.md
│   ├── extract_ideas.md
│   ├── extract_features.md
│   ├── extract_projects.md
│   ├── extract_clients.md
│   └── extract_quotes.md
├── pipeline/
│   ├── 01_ingest.py                # Drive watcher + local fallback
│   ├── 02_transcribe.py            # WhisperX + pyannote
│   ├── 03_extract.py               # LiteLLM extraction (10 prompts)
│   ├── 04_link.py                  # cross-meeting linking + index rollup
│   ├── 05_pragmatic_summary.py     # human-readable Markdown digest
│   ├── run_all.py                  # end-to-end orchestrator
│   ├── config.py                   # env-driven config
│   └── lib/
│       ├── speaker_inference.py    # speaker identity helpers
│       └── transcript_repair.py    # WhisperX output normalization
├── docs/
│   ├── ARCHITECTURE.md             # design choices + extension points
│   ├── DRIVE-SETUP.md              # all 3 ingest modes (public, service-account, local)
│   └── WHISPERX-MODEL-CHOICE.md    # small/medium/large tradeoffs
├── .github/workflows/
│   └── pipeline.yml                # cron + manual trigger
└── examples/
    └── one_meeting_demo/           # synthetic example to test against
```

## Outputs

For each meeting:

```
2026-08-28_aiw-strategy/
├── audio.mp3                       # original
├── meta.json                       # canonical record (matches meeting.schema.json)
├── transcript.json                 # WhisperX diarized segments
├── transcript.txt                  # human-readable, one paragraph per turn
├── transcript.vtt                  # WebVTT with speaker tags
└── extraction.json                 # daily/weekly/OKR/topics/decisions
```

Cross-meeting:

```
/opt/data/indexed/meetings/
├── topics.md                       # every topic, every meeting it appeared in
├── people.md                       # inferred speaker identities
├── decisions.md                    # every decision with meeting link
├── okrs.md                         # every monthly KR
├── daily_tasks.md                  # today's tasks across all meetings
└── weekly_tasks.md                 # this week's tasks across all meetings
```

## Configuration

Everything is env-driven (`pipeline/config.py`). Key vars:

| Variable | Default | Notes |
|----------|---------|-------|
| `MT_INBOX` | `/opt/data/inbox/meetings` | where ingested meetings live |
| `MT_INDEX` | `/opt/data/indexed/meetings` | where rolled-up indexes land |
| `MT_DRIVE_FOLDER` | `1iuz-q9fPxup4MZjuRLSs3U3iw6FmgIF2` | Google Drive folder ID (public or shared) |
| `MT_WHISPER_MODEL` | `medium` | `small`, `medium`, `large-v3` |
| `MT_LITELLM_MODEL` | `claude-sonnet-4-5` | any LiteLLM-routed model |
| `MT_LITELLM_BASE_URL` | `http://localhost:4000` | LiteLLM gateway |
| `MT_LINK_WINDOW_DAYS` | `30` | how far back to look for carried topics |
| `MT_GOOGLE_SA_JSON` | (unset) | path to service-account key |
| `HF_TOKEN` | (unset) | HuggingFace token for pyannote diarization |

## License

MIT. See `LICENSE`.