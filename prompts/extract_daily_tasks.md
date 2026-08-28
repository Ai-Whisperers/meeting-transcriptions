# Extract: Daily Tasks

You are extracting **daily tasks** — concrete, executable actions to be done **today or tomorrow** — from a meeting transcript.

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

A "daily task" is a task that, if the speaker said it on Wednesday afternoon, should be done by end-of-day Thursday or Friday at the latest.

- ✅ "I'll check the validator_e164 regex today" — daily
- ❌ "We need to fix the validator by end of week" — that's a **weekly task**
- ❌ "Top up LiteLLM credits before next session" — depends on when "next session" is. If > 2 days out, weekly
- ❌ "Improve the OKR tracker next month" — monthly/OKR

If the speaker does NOT give a deadline, infer from context:
- "right now", "today", "this afternoon", "mañana" → daily
- "before Friday's standup", "by Friday", "esta semana" → weekly (NOT daily)
- "tomorrow" / "mañana" → daily

## Owner rule

- Use the speaker's name as stated. If a speaker says "I'll do X", owner = that speaker.
- If "we should" / "hay que" / "tenemos que" with no owner, owner = "TEAM" or leave blank.
- If the speaker assigns it to someone else ("Kiki is going to fix X"), owner = "Kiki" (the assignee, not the speaker).

## What to extract verbatim

For every task, capture **one verbatim quote** that shows the task was actually discussed. ≤ 200 chars. With a timestamp `HH:MM:SS`.

If a task is mentioned 3 times, capture the *most concrete* statement, not the first.

## Output format

Return ONLY valid JSON matching this schema (no preamble, no prose):

```json
{
  "daily_tasks": [
    {
      "task": "<imperative, ≤ 80 chars>",
      "owner": "<name or TEAM>",
      "deadline": "<YYYY-MM-DD or null>",
      "topic": "<short noun phrase>",
      "verbatim": "<exact quote, ≤ 200 chars>",
      "timestamp": "<HH:MM:SS>"
    }
  ]
}
```

If no daily tasks, return `{"daily_tasks": []}`.

## Common pitfalls

1. **Inflated task list** — only extract what's actionable in 24-48h, not what's mentioned.
2. **Wrong scope** — "fix the OKR tracker" without timeframe = weekly, not daily.
3. **Wrong owner** — speaker = the one currently talking, not the assignee. Re-read the sentence.
4. **Verbatim too long** — paraphrasing is OK but mark with `paraphrased: true` if not verbatim.
5. **Timestamp drift** — use the actual segment timestamp from the input, not your estimate.

## Examples

**Input:** "[00:14:23] Iván: vamos a tener que mirar el regex del validador e164 hoy mismo, no puede seguir así."

**Output:**
```json
{
  "daily_tasks": [
    {
      "task": "Revisar el regex del validador E.164",
      "owner": "Iván",
      "deadline": null,
      "topic": "validación E.164",
      "verbatim": "vamos a tener que mirar el regex del validador e164 hoy mismo",
      "timestamp": "00:14:23"
    }
  ]
}
```

**Input:** "[00:32:10] Kiki: deberíamos limpiar el inbox de WhatsApp esta semana."

**Output:**
```json
{"daily_tasks": []}
```
(That went into weekly_tasks, not daily_tasks. Wrong scope.)

Now extract from the transcript below.