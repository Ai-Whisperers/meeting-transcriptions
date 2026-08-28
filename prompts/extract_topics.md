# Extract: Topics

You are extracting **discussion topics** — themes that come up in the meeting. Topics are the cross-meeting linking graph: a topic raised in meeting A and again in meeting C is a carried topic.

## What counts as a topic

- A substantive subject discussed for > 30 seconds OR mentioned 3+ times
- Has a name (short noun phrase) and a status
- Examples: "LiteLLM 402 cascade", "validator_e164_regression", "rubicón EAS landing", "thesis-active autonomy"

Not a topic:
- One-line mentions ("hi", "thanks", "ok") — discard
- Procedural noise ("let's start", "we'll come back to this") — discard
- Personal chatter unrelated to work — discard

## Status taxonomy

- `open` — raised, no decision, no action yet
- `in-progress` — has an owner and a deadline, work has started
- `blocked` — work has started but is waiting on something external
- `resolved` — explicitly closed in this meeting or earlier
- `deferred` — explicitly punted ("not now", "later", "next quarter")

## Cross-meeting links

The input transcript may include a list of **prior meetings** (id + topics). For each topic:
- If a topic with the same name was raised in a prior meeting, mark `related_to: [<prior_meeting_id>]`
- If the topic is **new** in this meeting, mark `first_raised_here: true`

## Date anchoring (CRITICAL)

The meeting's actual date is provided in the `Context` block as
`meeting_date` (YYYY-MM-DD) and `iso_week` (e.g. `2026-W08`). When a task or
OKR mentions a deadline:

- Use `meeting_date` for the deadline if the speaker says "today" or "tomorrow"
- Use the speaker's explicit date verbatim (reformat to YYYY-MM-DD)
- For relative deadlines ("this week", "next month", "by Friday"), compute
  from `meeting_date` and write `deadline` / `week` / `target_date` as YYYY-MM-DD
- If no deadline is mentioned, set `deadline` (and `target_date`, `week`) to `null` — **NEVER guess or invent a date**

Example: meeting_date=2026-02-18, speaker says "we need this by Friday":
- Friday after Feb-18-2026 (Wed) is Feb-20-2026
- Output: `"deadline": "2026-02-20"`, NOT `"2023-04-25"` or `"2023-W36"`

This rule prevents the model from hallucinating dates (verified bug:
zai-glm-4-flash said "2023-W36" for a2026 meeting).

## Output format

Return ONLY valid JSON:

```json
{
  "topics": [
    {
      "name": "<short noun phrase, ≤ 60 chars>",
      "status": "open|in-progress|blocked|resolved|deferred",
      "first_mentioned_at": "<HH:MM:SS>",
      "related_to": ["<prior_meeting_id>"]
    }
  ]
}
```

## Common pitfalls

1. **Topic inflation** — only substantive topics, not every mention.
2. **Name mismatch** — same topic with different names breaks the link. Normalize ("LiteLLM 402" not "credit problem" and not "Cerebras exhaustion").
3. **Status hallucination** — only assign status that's actually stated or strongly implied. "Probably will fix next week" = open, not in-progress.

## Examples

**Input (with prior meeting context):**
```
PRIOR MEETINGS:
- 2026-08-25_aiw-strategy: ["LiteLLM 402 cascade", "stale_repos", "thesis-active resume"]

TRANSCRIPT:
[00:02:10] Iván: el 402 de LiteLLM sigue sin resolverse, vamos a tener que meter créditos antes de fin de mes.
[00:18:00] Kiki: propongo migrar el OKR tracker a un LLM local mientras tanto.
[00:25:30] Iván: aprobado, lo hago esta semana.
```

**Output:**
```json
{
  "topics": [
    {
      "name": "LiteLLM 402 cascade",
      "status": "in-progress",
      "first_mentioned_at": "00:02:10",
      "related_to": ["2026-08-25_aiw-strategy"]
    },
    {
      "name": "OKR tracker LLM migration",
      "status": "in-progress",
      "first_mentioned_at": "00:18:00",
      "related_to": []
    },
    {
      "name": "stale_repos=18",
      "status": "open",
      "first_mentioned_at": null,
      "related_to": ["2026-08-25_aiw-strategy"]
    }
  ]
}
```

Now extract from the transcript below.