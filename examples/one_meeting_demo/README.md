# Example: one synthetic meeting

This folder shows what a fully-processed meeting looks like after stages 2 + 3 + 4.

## Files

- `meta.json` — canonical meeting record (matches `schema/meeting.schema.json`)
- `transcript.json` — WhisperX diarized segments
- `transcript.txt` — human-readable, one paragraph per speaker turn
- `transcript.vtt` — WebVTT with speaker tags
- `extraction.json` — daily/weekly/OKR/topics/decisions (matches `schema/extraction.schema.json`)

## Synthetic content

Two speakers (SPEAKER_00 = Iván, SPEAKER_01 = Kiki) discussing AIW org priorities for the week.

- Daily tasks: review validator_e164 regex today, top up LiteLLM credits
- Weekly tasks: clean up thesis-active repo, review Rubicón EAS proposal
- Monthly OKR: resolve LiteLLM 402 cascade by end of August
- Topics: LiteLLM 402 cascade, validator_e164_regression, thesis-active, Rubicón EAS
- Decision: switch OKR tracker to local LLM temporarily

Use this to validate the pipeline end-to-end without a real meeting audio.