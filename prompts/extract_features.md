# Extract: Features

You are extracting **features** — product capabilities that are being requested, discussed, or planned — from a meeting transcript. Features are concrete technical/product things.

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

A **feature** is:
- ✅ "We need to add CSV export"
- ✅ "User requested a Slack integration"
- ✅ "Dark mode has been requested 3 times this month"
- ✅ "The dashboard needs a date range filter"
- ✅ "Mobile app should support offline mode"

**Not a feature:**
- ❌ High-level product ideas (use extract_ideas instead)
- ❌ Bug reports about broken behavior (use extract_clients instead)
- ❌ Internal process tools (use extract_ideas with category=process)

## Feature status (use the closest fit)

- `requested` — someone asked for it but we haven't agreed
- `discussed` — actively being scoped
- `planned` — committed to a roadmap/sprint
- `in-progress` — being built right now
- `shipped` — already live (only include if discussed in this meeting)

## Output format

Return ONLY valid JSON:

```json
{
  "features": [
    {
      "feature": "<the feature in ≤ 200 chars, concrete>",
      "product": "<which product/system, or 'unknown'>",
      "status": "requested|discussed|planned|in-progress|shipped",
      "requested_by": "<customer name, internal name, or null>",
      "raised_at": "<HH:MM:SS>",
      "complexity": "trivial|small|medium|large|epic",
      "blocks": ["<other feature ids this blocks, or empty array>"]
    }
  ]
}
```

## Confidence scoring (REQUIRED)

For each item, add `confidence` (0.0-1.0) and `source_quote`:
- 0.9-1.0: speaker explicitly named the feature with details
- 0.7-0.9: implied, but inference is solid
- 0.4-0.7: speculative
- <0.4: DO NOT include

## Common pitfalls

1. **Vague features** — "improve UX" is not a feature; "add a date range filter to the metrics dashboard" is
2. **Conflating with ideas** — features are concrete product capabilities; ideas can be anything (marketing, business model, etc.)
3. **Double-counting with bugs** — if someone says "the export is broken", that's a bug, not a feature
4. **Missing the product context** — every feature belongs to something; use `unknown` if unclear

## Examples

**Input:** "[00:08:15] Iván: para el cliente Ometz Dental, agreguemos un export de citas en formato CSV para que puedan importar a su sistema de gestión."

**Output:**
```json
{
  "features": [
    {
      "feature": "Exportar citas a formato CSV desde el panel de administración",
      "product": "rubicon-eas",
      "status": "planned",
      "requested_by": "Ometz Dental",
      "raised_at": "00:08:15",
      "complexity": "small",
      "blocks": [],
      "confidence": 0.95,
      "source_quote": "para el cliente Ometz Dental, agreguemos un export de citas en formato CSV para que puedan importar a su sistema de gestión"
    }
  ]
}
```

Now extract from the transcript below.