# Extract: Weekly Tasks

You are extracting **weekly tasks** — actions to be done **this week or next week**.

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