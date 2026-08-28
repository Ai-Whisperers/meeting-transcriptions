# Extract: Monthly Objectives (OKRs)

You are extracting **monthly / quarterly objectives** — measurable goals with key results — from a meeting transcript.

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