# Extract: Key Quotes

You are extracting **key quotes** — verbatim statements that are memorable, committal, or strategically important — from a meeting transcript. Quotes are anchors for future reference.

## What counts as a key quote

- ✅ **Commitments** — "we'll deliver this by Friday"
- ✅ **Promises to clients** — "I'll send you the proposal tomorrow"
- ✅ **Strategic directions** — "we're moving away from X, focusing on Y"
- ✅ **Strong opinions** — "I will never do X again"
- ✅ **Pivotal moments** — the sentence that decided a debate
- ✅ **Accountability statements** — "the buck stops with me on this"

## What does NOT count

- ❌ Routine informational statements ("today is Tuesday")
- ❌ Filler ("yeah, totally, makes sense")
- ❌ Anything already captured as a decision (use extract_decisions)
- ❌ Trivia or side chatter

## Quote types

- `commitment` — we promised to do something
- `client-promise` — promise made TO a client
- `strategic` — direction-setting statement
- `opinion` — strong personal view worth remembering
- `pivotal` — the sentence that closed a debate
- `accountability` — explicit ownership statement

## Output format

Return ONLY valid JSON:

```json
{
  "quotes": [
    {
      "quote": "<verbatim, ≤ 300 chars, exact words from transcript>",
      "speaker": "<name or null>",
      "type": "commitment|client-promise|strategic|opinion|pivotal|accountability",
      "timestamp": "<HH:MM:SS>",
      "context": "<≤ 200 chars explaining what was being discussed>"
    }
  ]
}
```

## Confidence scoring (REQUIRED)

For each item, add `confidence` (0.0-1.0):
- 0.9-1.0: clearly quotable, strategically important
- 0.7-0.9: solid commitment or direction
- 0.4-0.7: memorable but maybe not worth archiving
- <0.4: DO NOT include

## Common pitfalls

1. **Paraphrasing** — quotes must be VERBATIM. If you can't find the exact words, lower the confidence or skip.
2. **Too many quotes** — limit to the most valuable 5-10 per meeting. If you're finding more, your threshold is too low.
3. **Missing the speaker** — use the diarized speaker label; if unknown, set to null
4. **Loss of context** — always include `context` so the quote makes sense when read alone

## Examples

**Input:** "[00:42:10] Iván: OK, el deadline es el viernes 5pm. Si no llegamos, perdemos el cliente. No hay plan B."

**Output:**
```json
{
  "quotes": [
    {
      "quote": "el deadline es el viernes 5pm. Si no llegamos, perdemos el cliente. No hay plan B",
      "speaker": "Iván",
      "type": "commitment",
      "timestamp": "00:42:10",
      "context": "Setting the launch deadline for rubicon-eas deploy",
      "confidence": 0.95
    }
  ]
}
```

Now extract from the transcript below.