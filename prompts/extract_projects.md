# Extract: Projects

You are extracting **project-level information** — proposals, status updates, pivots, dependencies — from a meeting transcript. Projects are ongoing initiatives with multiple tasks and a goal.

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

A **project item** is one of:
- A **proposal** for a new project ("we should build X")
- A **status update** ("the OKR tracker is 60% done")
- A **pivot** ("we're changing approach on Y")
- A **dependency** ("Z blocks the launch")
- A **resource need** ("we need to hire a designer")

**Not a project item:**
- ❌ A single task (use extract_daily_tasks or extract_weekly_tasks)
- ❌ A feature in an existing project (use extract_features)
- ❌ A decision (use extract_decisions)

## Project status

- `proposed` — new project idea, not yet committed
- `active` — currently being worked on
- `blocked` — can't progress due to dependencies
- `paused` — temporarily stopped
- `completed` — finished (only include if mentioned in this meeting)
- `cancelled` — explicitly killed

## Output format

Return ONLY valid JSON:

```json
{
  "projects": [
    {
      "name": "<project name in ≤ 80 chars, kebab-case>",
      "status": "proposed|active|blocked|paused|completed|cancelled",
      "owner": "<person or team, or null>",
      "description": "<≤ 300 chars>",
      "next_milestone": "<≤ 120 chars, or null>",
      "blockers": ["<list of blocker names, or empty array>"],
      "depends_on": ["<list of project names this depends on, or empty array>"],
      "raised_at": "<HH:MM:SS>"
    }
  ]
}
```

## Confidence scoring (REQUIRED)

For each item, add `confidence` (0.0-1.0) and `source_quote`:
- 0.9-1.0: speaker explicitly named the project with status details
- 0.7-0.9: implied, but inference is solid
- 0.4-0.7: speculative
- <0.4: DO NOT include

## Common pitfalls

1. **Confusing projects with features** — features live inside projects; a project is the umbrella
2. **Confusing projects with OKRs** — OKRs are measurable outcomes for a month/quarter; projects are ongoing initiatives. A project may serve one or more OKRs.
3. **Made-up project names** — use the speaker's actual name for the project, even if informal ("the liteLLM fix" is fine; don't invent "LLM Infrastructure Stabilization Initiative")
4. **Missing the owner** — every active project has an owner; if not stated, set to null but lower confidence

## Examples

**Input:** "[00:32:10] Iván: el proyecto rubicon-eas está al 60%, lo bloquea el 402 de LiteLLM. Si no resolvemos esto hoy, no llegamos al deploy del viernes."

**Output:**
```json
{
  "projects": [
    {
      "name": "rubicon-eas",
      "status": "blocked",
      "owner": "Iván",
      "description": "Sistema de agendamiento y expedientes para estudios jurídicos en Paraguay",
      "next_milestone": "Deploy a producción antes del viernes",
      "blockers": ["LiteLLM 402 cascade"],
      "depends_on": [],
      "raised_at": "00:32:10",
      "confidence": 0.95,
      "source_quote": "el proyecto rubicon-eas está al 60%, lo bloquea el 402 de LiteLLM. Si no resolvemos esto hoy, no llegamos al deploy del viernes"
    }
  ]
}
```

Now extract from the transcript below.