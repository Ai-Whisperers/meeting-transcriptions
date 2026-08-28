# Extract: Ideas

You are extracting **ideas** — new concepts, suggestions, brainstorms — from a meeting transcript. Ideas are seeds for future work, not commitments.

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

An **idea** is:
- ✅ A product feature concept ("we could add dark mode")
- ✅ A business model suggestion ("what if we charged per seat")
- ✅ A marketing angle ("let's try TikTok ads for Q4")
- ✅ A partnership opportunity ("partner with X for co-marketing")
- ✅ A content idea ("publish a weekly newsletter")
- ✅ A process improvement ("automate the daily report")

**Not an idea:**
- ❌ An already-decided action item (use extract_daily_tasks instead)
- ❌ A description of existing work (use extract_projects instead)
- ❌ A customer requirement (use extract_clients instead)
- ❌ A vague aspirational statement without substance ("we should be better")

## Idea categories (use the closest fit)

- `product` — features or capabilities for a product
- `business-model` — pricing, packaging, revenue streams
- `marketing` — positioning, channels, campaigns
- `partnership` — relationships with other companies/people
- `content` — articles, videos, social posts to create
- `process` — internal workflow improvements
- `other` — anything that doesn't fit

## Output format

Return ONLY valid JSON:

```json
{
  "ideas": [
    {
      "idea": "<the idea in ≤ 200 chars, concrete>",
      "category": "product|business-model|marketing|partnership|content|process|other",
      "raised_by": "<speaker name or null>",
      "timestamp": "<HH:MM:SS>",
      "novelty": "incremental|moderate|breakthrough",
      "estimated_impact": "low|medium|high"
    }
  ]
}
```

## Confidence scoring (REQUIRED)

For each item, add `confidence` (0.0-1.0) and `source_quote` (verbatim 1-2 sentence quote):
- 0.9-1.0: speaker explicitly proposed it with detail
- 0.7-0.9: implied, but inference is solid
- 0.4-0.7: speculative
- <0.4: DO NOT include

## Common pitfalls

1. **Conflating with action items** — "let's add dark mode" is an idea, NOT a task (unless someone is assigned to do it now)
2. **Conflating with decisions** — ideas are proposed, decisions are committed
3. **Hindsight bias** — only include ideas raised IN this meeting
4. **Inflation** — not every offhand comment is an idea; require at least one sentence of substance

## Examples

**Input:** "[00:14:22] Kiki: podríamos probar con TikTok ads, segmentando por país, para captar más clientes B2B en Paraguay."

**Output:**
```json
{
  "ideas": [
    {
      "idea": "Probar TikTok ads segmentados por país para captar clientes B2B en Paraguay",
      "category": "marketing",
      "raised_by": "Kiki",
      "timestamp": "00:14:22",
      "novelty": "moderate",
      "estimated_impact": "medium",
      "confidence": 0.9,
      "source_quote": "podríamos probar con TikTok ads, segmentando por país, para captar más clientes B2B en Paraguay"
    }
  ]
}
```

Now extract from the transcript below.