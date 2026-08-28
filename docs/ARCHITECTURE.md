# Architecture

## Pipeline stages

The pipeline is intentionally **stateless per stage**. Each stage reads from a known path, writes to the same path, and is independently re-runnable. This makes failures recoverable: re-run stage N without re-running stage N-1.

| Stage | Module | Input | Output | Idempotent? |
|-------|--------|-------|--------|-------------|
| 1 | `pipeline/01_ingest.py` | Drive folder / local path | `MT_INBOX/<id>/audio.<ext>` + `meta.json` | yes (sha check) |
| 2 | `pipeline/02_transcribe.py` | `audio.<ext>` | `transcript.{json,txt,vtt}`, `meta.json` updated | yes (`--force`) |
| 3 | `pipeline/03_extract.py` | `transcript.json` | `extraction.json`, `meta.json` updated | yes (`--force`) |
| 4 | `pipeline/04_link.py` | all `meta.json` + `extraction.json` | `meta.json` links, `MT_INDEX/*.md` | yes (always rewrites) |

## Why this shape?

### Why per-meeting folders, not a flat directory?

When two meetings happen on the same day (`2026-08-28_standup` and `2026-08-28_client-call`), you need to keep their artifacts separate. Folders give us:

- File-level co-location (audio, transcript, extraction, meta all in one place)
- Trivial filesystem-level rsync / backup
- Easy deletion: `rm -rf /opt/data/inbox/meetings/2026-08-28_standup`

### Why 5 prompts, not one big extraction prompt?

Each prompt has a tight scope rule (daily vs weekly vs OKR). Splitting them:

- Lets us iterate one prompt without breaking others
- Reduces LLM context size (5 small prompts ≪ 1 huge one)
- Lets us swap the LLM per prompt (e.g., use a fast model for daily_tasks, smarter model for OKRs)

### Why deterministic linking, not LLM-based linking?

Stage 4 is pure string-matching (Jaccard on topic tokens). This is intentional:

- **Cheap** — no LLM cost, runs in milliseconds
- **Auditable** — `index/topics.md` is generated from data, not LLM output
- **Reproducible** — same input → same output

The current fuzzy matcher has limitations (e.g., "OKR tracker LLM migration" vs "migrate OKR tracker to local LLM" — token Jaccard = 0.85 ✓ but "LiteLLM" vs "credit problem" — Jaccard ≈ 0). When this becomes a problem, swap in embeddings (`text-embedding-3-small` via LiteLLM). Don't replace with another LLM call — embeddings are cheaper and more deterministic.

## Extension points

### Adding a new extraction kind (e.g. "risks")

1. Create `prompts/extract_risks.md` with the same shape as the other 5
2. Add `risks: []` to `schema/extraction.schema.json`
3. Add a `(extract_risks.md, None)` entry to `prompts` list in `03_extract.py`
4. Add an `index/risks.md` renderer in `04_link.py`

### Replacing WhisperX with ElevenLabs Scribe

`02_transcribe.py` is the only file that knows about WhisperX. Replace the `transcribe_one` body. The output contract (`transcript.json` shape with `segments[]` containing `start_time`, `end_time`, `speaker`, `text`) is what stage 3 consumes. As long as the new engine emits that shape, nothing else changes.

### Speaker identity persistence across meetings

Currently `inferred_name` is `null` for every speaker in every meeting. To make this persist:

1. Extract a 5-second embedding per speaker per meeting (e.g., pyannote, resemblyzer)
2. In stage 4, compare embeddings across meetings — same person if cosine ≥ 0.7
3. Write back to `meta.json.speakers[].inferred_name`

This is the next-biggest feature after this MVP ships.

## Failure modes

### "WhisperX OOM"

Medium model = ~3GB VRAM on GPU. On CPU with `int8` compute, peak RSS ~5GB. If you OOM:

```bash
MT_WHISPER_MODEL=small python -m pipeline.02_transcribe --all
```

Small = 244M params, ~1GB peak.

### "LiteLLM 402 / 429"

The extractor saves partial state per prompt in `extraction.json`. Re-run `--force`:

```bash
python -m pipeline.03_extract --all --force
```

### "Drive folder ID changed"

If you recreate the folder, the ID changes. Update `MT_DRIVE_FOLDER`:

```bash
export MT_DRIVE_FOLDER="<new-id>"
```

Or edit `pipeline/config.py` directly.

### "Topic names diverge across meetings"

E.g., meeting A says "LiteLLM 402" and meeting B says "Cerebras credit exhaustion". The fuzzy matcher won't link them.

Fix: normalize in the prompt. Add to `prompts/extract_topics.md`:

> Normalize topic names to the most concise noun phrase. Don't include adjectives or pronouns. Examples: "LiteLLM credit exhaustion" not "the credit problem".

Then re-run stage 3 + stage 4 with `--force`.

## Cross-references

- See [`voice-notes-transcription`](https://github.com/Ai-Whisperers/skills/blob/main/media/voice-notes-transcription/SKILL.md) for the Whisper recipe this is built on
- See [`WHISPERX-MODEL-CHOICE.md`](WHISPERX-MODEL-CHOICE.md) for the small/medium/large tradeoff matrix
- See [`DRIVE-SETUP.md`](DRIVE-SETUP.md) for the service-account flow