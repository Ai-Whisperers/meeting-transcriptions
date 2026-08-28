# Extract: Client Insights

You are extracting **client intelligence** — what clients (external customers) said, need, want, or struggled with — from a meeting transcript. This is the sales-and-CS layer of meeting intelligence.

## Scope rule (CRITICAL)

An **insight** is something said about a specific named client or about clients-as-a-group. Categories:

- `pain-point` — problem the client is experiencing
- `requirement` — explicit need they expressed
- `feedback` — opinion on what we delivered
- `objection` — pushback, hesitation, blocker
- `success-story` — positive outcome, win, testimonial
- `upsell` — opportunity to sell more / expand the engagement
- `churn-risk` — sign they might leave
- `general` — anything else client-related

## Distinction from features

If a client asks for "CSV export" → that's BOTH a feature (extract_features) AND a client insight (this prompt, category=requirement). Extract both. The insight captures the WHO/WHY; the feature captures the WHAT.

## Output format

Return ONLY valid JSON:

```json
{
  "clients": [
    {
      "insight": "<≤ 250 chars, the insight stated concretely>",
      "category": "pain-point|requirement|feedback|objection|success-story|upsell|churn-risk|general",
      "client": "<client name, or 'unknown', or 'multiple'>",
      "severity": "low|medium|high|critical",
      "raised_at": "<HH:MM:SS>",
      "follow_up_needed": true|false,
      "follow_up_owner": "<name or null>"
    }
  ]
}
```

## Confidence scoring (REQUIRED)

For each item, add `confidence` (0.0-1.0) and `source_quote`:
- 0.9-1.0: speaker explicitly described a SPECIFIC NAMED client's situation
- 0.7-0.9: implied, inference is solid (named client present)
- 0.4-0.7: speculative
- <0.4: **DO NOT include** — particularly when no client name is given

## Common pitfalls

1. **No client named** — if the speaker is talking about generic companies or abstract concepts (no name, no actual customer), it's **NOT** a client insight. Skip it entirely or set category=`general` with confidence <0.4. Don't invent client insights from casual reflections.
2. **Confusing with internal complaints** — pain points are the CLIENT's pain, not ours
3. **Missed opportunities** — success stories and upsell signals are valuable; don't overlook them
4. **Forgetting severity** — a "minor UX issue" is severity=low; "they might cancel next quarter" is severity=critical
5. **Phantom clients** — if the speaker says "in a bigger company" or "in general", there is NO specific client. Skip.

## Examples

**Input:** "[00:21:45] Kiki: Ometz Dental nos pidió soporte 24/7 porque sus recepcionistas trabajan turnos rotativos. Si no lo ofrecemos, evalúan cambiar de proveedor."

**Output:**
```json
{
  "clients": [
    {
      "insight": "Ometz Dental pide soporte 24/7 por turnos rotativos de recepcionistas; evalúan cambiar de proveedor si no lo ofrecemos",
      "category": "requirement",
      "client": "Ometz Dental",
      "severity": "critical",
      "raised_at": "00:21:45",
      "follow_up_needed": true,
      "follow_up_owner": "Kiki",
      "confidence": 0.95,
      "source_quote": "Ometz Dental nos pidió soporte 24/7 porque sus recepcionistas trabajan turnos rotativos. Si no lo ofrecemos, evalúan cambiar de proveedor"
    },
    {
      "insight": "Riesgo de churn: Ometz Dental evalúa cambiar de proveedor si no ofrecemos soporte 24/7",
      "category": "churn-risk",
      "client": "Ometz Dental",
      "severity": "critical",
      "raised_at": "00:21:45",
      "follow_up_needed": true,
      "follow_up_owner": "Kiki",
      "confidence": 0.85,
      "source_quote": "evalúan cambiar de proveedor"
    }
  ]
}
```

Now extract from the transcript below.