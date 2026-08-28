# Extract: Decisions

You are extracting **concrete decisions** made in this meeting. A decision is a choice that closes an open question.

## What counts as a decision

- ✅ "OK, vamos a hacer X" (with X explicit)
- ✅ "Aprobado, lo hago mañana" (with action + owner)
- ✅ "Decidimos no seguir con Y, vamos por Z"
- ❌ "Deberíamos pensar en X" — that's an open topic, not a decision
- ❌ "Quizás el mes que viene" — not a decision

## Distinction from topics

A topic is an ongoing thread. A decision is a closure.

- Topic: "LiteLLM 402 cascade" → open
- Decision: "Switch OKR tracker to local LLM temporarily" → made in meeting X

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
  "decisions": [
    {
      "decision": "<what was decided, ≤ 120 chars>",
      "made_by": "<name or TEAM>",
      "timestamp": "<HH:MM:SS>",
      "rationale": "<why, ≤ 200 chars, or null>"
    }
  ]
}
```

## Common pitfalls

1. **False decisions** — vague statements like "we'll see" are not decisions.
2. **Decisions without owner** — if no one owns the action, it's a topic.
3. **Timestamp drift** — use the actual segment timestamp.

## Examples

**Input:** "[00:25:30] Iván: aprobado, vamos a migrar el OKR tracker a LLM local mientras se resuelve el 402."

**Output:**
```json
{
  "decisions": [
    {
      "decision": "Migrar OKR tracker a LLM local temporalmente",
      "made_by": "Iván",
      "timestamp": "00:25:30",
      "rationale": "LiteLLM 402 cascade bloquea 20+ crons semanales"
    }
  ]
}
```

Now extract from the transcript below.