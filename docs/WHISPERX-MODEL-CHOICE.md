# WhisperX Model Choice

The default is `medium`. This doc explains when to use what.

## Comparison (CPU, `int8` compute)

| Model | Params | Disk | Peak RAM | Speed (2h meeting) | Spanish quality | Notes |
|-------|--------|------|----------|--------------------|-----------------|-------|
| `tiny` / `tiny.es` | 39M | 75 MB | ~1 GB | ~3 min | poor | Pre-flight only. Hallucinates in silence. |
| `base` / `base.es` | 74M | 140 MB | ~1.5 GB | ~7 min | fair | Quick triage, not for production. |
| `small` | 244M | 460 MB | ~3 GB | ~20 min | **good** | Validated 2026-08-26 in voice-notes-transcription skill. |
| `medium` | 769M | 1.5 GB | ~5 GB | ~60 min | very good | **Default**. Best accuracy/CPU tradeoff. |
| `large-v3` | 1.5B | 3 GB | ~10 GB | ~120 min | best | When quality is paramount and you have 2h to wait. |
| `turbo` | 809M | 1.6 GB | ~5 GB | ~45 min | very good | Faster than `large-v3` with similar quality. |

## Pick by use case

| Situation | Model | Why |
|-----------|-------|-----|
| Daily standups, internal sync | `medium` | Good enough, fast enough |
| Client meetings (will be quoted) | `large-v3` | Need near-perfect accuracy |
| Hour-long discovery call | `medium` | Default |
| Voice notes (lots of small files) | `small` | 5x faster, sufficient quality |
| Long interview (>2h) | `medium` | large-v3 too slow |
| Test pipeline with synthetic audio | `tiny` | Quick smoke test |

## CPU vs GPU

CPU + `int8`: works on any laptop, ~5GB peak RAM.
GPU + `float16`: 5-10x faster but needs CUDA.

```bash
# CPU (default)
MT_WHISPER_MODEL=medium python -m pipeline.02_transcribe --all

# GPU (if you have one)
MT_USE_CUDA=1 MT_WHISPER_MODEL=large-v3 python -m pipeline.02_transcribe --all
```

## Diarization

WhisperX uses **pyannote** for speaker diarization. Requires `HF_TOKEN`:

1. Create a free HuggingFace account
2. Accept the user agreement at <https://huggingface.co/pyannote/speaker-diarization-3.1>
3. Generate a token at <https://huggingface.co/settings/tokens>
4. Set `HF_TOKEN=<your-token>` in your environment

Without `HF_TOKEN`, all speakers get labeled `SPEAKER_UNKNOWN` and diarization is skipped.

## Mishear caveats (Paraguayan/Rioplatense Spanish)

WhisperX reproduces the mishears documented in the `voice-notes-transcription` skill. The most common ones:

- `ent11s → entonces`
- `Evan → Iván` (always when "Iván" is in subject position)
- `odontolog[íi]a → loquería 3`
- `Ram[ií]rez Nizza → ramires mi...`

A post-processor pass (regex substitution table) cleans ~95% without re-running Whisper. Add this in a future stage.

## Reproducibility

WhisperX is **non-deterministic** by default (sampling temperature > 0). For reproducible transcripts, set:

```python
# In pipeline/02_transcribe.py, in the transcribe call:
result = model.transcribe(audio_data, batch_size=8, temperature=0.0)
```

This is on the roadmap; default is currently sampling.

## References

- WhisperX paper: <https://arxiv.org/abs/2303.00747>
- pyannote: <https://github.com/pyannote/pyannote-audio>
- AIW skill `voice-notes-transcription`: validated 38-audio Spanish batch on this stack