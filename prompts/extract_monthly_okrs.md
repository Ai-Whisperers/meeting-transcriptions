# Extract: Monthly Objectives (OKRs)

You are extracting **monthly / quarterly objectives** — measurable goals with key results — from a meeting transcript.

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

An OKR is:
- **Objective**: a *qualitative* goal (what we want to achieve)
- **Key Result**: a *quantitative* measure (how we'll know we got there)

- ✅ "Resolve LiteLLM 402 cascade this month" + KR "All 20+ weekly crons back to PASS by Aug 31"
- ❌ "We should be healthier" — no KR, defer to topics
- ❌ "Improve team morale" — no measurable KR, not extractable

OKRs in this codebase link to `Ai-Whisperers/okr-tracker`. The `objective` text should match a tracker OKR if one exists. The `kr` field must have a NUMBER or a state ("all", "zero", "100%").

## Scope by timeframe

- **Monthly**: scoped to current month or next month
- **Quarterly**: scoped to current or next quarter (3-month window)
- If longer-term than a quarter, treat as a vision statement — NOT extracted.

## Output format

Return ONLY valid JSON:

```json
{
  "monthly_okrs": [
    {
      "objective": "<qualitative goal, ≤ 100 chars>",
      "kr": "<measurable KR with number>",
      "owner": "<name or TEAM>",
      "target_date": "<YYYY-MM-DD>",
      "metric": "<number | percentage | count | binary>"
    }
  ]
}
```

## Common pitfalls

1. **No KR** — aspirational goals without a number are not OKRs. Defer to topics.
2. **Vague KRs** — "be better at X" — not measurable.
3. **Over-extraction** — only objectives explicitly raised in this meeting, not inherited OKRs.

## Examples

**Input:** "[00:05:12] Iván: tenemos que resolver el HTTP 402 de LiteLLM este mes. Los 20 jobs semanales están bloqueados."

**Output:**
```json
{
  "monthly_okrs": [
    {
      "objective": "Resolver cascade HTTP 402 de LiteLLM",
      "kr": "20+ crons semanales vuelven a PASS antes de 2026-08-31",
      "owner": "Iván",
      "target_date": "2026-08-31",
      "metric": "count"
    }
  ]
}
```

Now extract from the transcript below.