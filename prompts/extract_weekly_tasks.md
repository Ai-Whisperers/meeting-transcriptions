# Extract: Weekly Tasks

You are extracting **weekly tasks** — actions to be done **this week or next week**.

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

## Scope rule (CRITICAL)

A "weekly task" is a task that takes more than 1-2 days, or is scoped to a week, or is "esta semana" / "this week" / "by Friday".

- ✅ "Clean up the OKR tracker this week" — weekly
- ✅ "Resolve the LiteLLM 402 cascade before next Friday" — weekly (with deadline)
- ❌ "I'll check X today" — daily, not weekly
- ❌ "We should improve Y over the next month" — monthly/OKR
- ❌ "Eventually we'll do Z" — deferred, no week attached

If the speaker says "next week", use next week's ISO week (`YYYY-Www`).

## Owner rule

Same as daily_tasks. Speaker-assigned name, or "TEAM", or blank.

## What to extract verbatim

Same as daily_tasks: one verbatim quote + timestamp per task.

## Output format

Return ONLY valid JSON:

```json
{
  "weekly_tasks": [
    {
      "task": "<imperative, ≤ 80 chars>",
      "owner": "<name or TEAM>",
      "week": "<YYYY-Www, ISO week>",
      "topic": "<short noun phrase>",
      "blocks": ["<other task names this unblocks>"]
    }
  ]
}
```

## Common pitfalls

1. **Scope creep** — only what's actually scoped to a week, not aspirational month-long plans.
2. **Week formatting** — `YYYY-Www`, e.g. `2026-W35`. ISO week starts Monday. If today is 2026-08-28 (Friday), this week = `2026-W35`, next week = `2026-W36`.
3. **No week attached** — if the speaker just says "we should fix X" with no week, classify as deferred/topics, NOT weekly.

## Examples

**Input:** "[00:08:55] Iván: hay que limpiar el inbox de WhatsApp esta semana, está lleno de basura."

**Output:**
```json
{
  "weekly_tasks": [
    {
      "task": "Limpiar inbox de WhatsApp",
      "owner": "Iván",
      "week": "2026-W35",
      "topic": "inbox WhatsApp",
      "blocks": []
    }
  ]
}
```

Now extract from the transcript below.