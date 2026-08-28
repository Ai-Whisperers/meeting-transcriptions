# Reference Examples

Real-world output examples used to calibrate the pipeline's behavior.

## `pragmatic_summary_example.md`

A hand-written "Pragmatic Summary" by Ivan from August 2025, originally written for
the WhatsApp voice notes in `Ai-Whisperers/saved-transcriptions`.

**What this example is the model for:** the Markdown output of
`pipeline/05_pragmatic_summary.py`. Our automatic generator produces a
similarly-structured document for every meeting, with these sections
(in priority order):

- **Context** — participants, cadence, volume
- **Core Themes** — from `extraction.topics`
- **Decisions / Positions** — from `extraction.decisions`
- **What Needs To Happen** — from `extraction.daily_tasks` + `weekly_tasks` + `monthly_okrs`
- **Ideas Raised** — from `extraction.ideas` (grouped by category)
- **Features Discussed** — from `extraction.features`
- **Projects** — from `extraction.projects` (status + blockers)
- **Client Insights** — from `extraction.clients` (sorted by severity)
- **Key Quotes** — from `extraction.quotes` (commitments first)
- **Risks / Constraints** — high/critical client insights
- **Open Questions** — OKRs without metrics, low-confidence tasks
- **People** — speaker labels + inferred names + talk time

**Why the example matters:** the LLM extraction prompts are designed to
produce JSON that maps cleanly into these Markdown sections. If the
extraction drifts, the summary loses its punch.

**To regenerate summaries after re-extraction:**

```bash
python -m pipeline.05_pragmatic_summary --all --force
```