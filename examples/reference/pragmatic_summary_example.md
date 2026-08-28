<!--
ATTRIBUTION: This is a hand-written example by Ivan, used as a reference
for what `pipeline/05_pragmatic_summary.py` should generate automatically.

Source: https://github.com/Ai-Whisperers/saved-transcriptions/blob/main/structured-text/20%20august%20john%20tips%20(dinner%20with%20john%20%26%20family)/Pragmatic%20Summary.md
Pushed: 2026-03-04
-->

# WhatsApp Audio Transcriptions — Pragmatic Summary (2025-08-21)

## Context

* **Source:** 7 voice notes discussing investing, an Investor-AI MVP, and workflow automation.&#x20;

## Core Themes

* **Agro-robotics thesis:** AI + labor shortages → high automation potential in agriculture; watch **Ukraine** as a future ag-robotics hub/funds. Public vehicles exist but are scarce/hard to access.
* **Investor-AI platform (MVP):** Start as **intel/decision support**, not brokerage. Aggregate multi-source facts (company, CEO, supply chain, regs), then expand.
* **OSINT on power players:** Track visible elites/funds (e.g., Altman, Musk) to infer **where capital creates opportunities** (policy signals, lobbying, grants).
* **Regulatory/standard signals:** Example: EU forcing **USB-C**—use regs to anticipate sector winners/losers.
* **Macro AI ripple:** Near-term AI → transport/logistics shake-ups, faster project cycles, self-driving services; **space sector** flagged to “boom soon.”
* **Horizon mix:** Do both **LT holds** (5y) and **ST/“sure-win”** plays; dry-run strategies before risking capital.
* **Build workflow:** Strong emphasis on **docs → tickets → tests** with agents (Cursor/LLMs), MCP tools, CI hooks. Don’t write unit tests too early while code is in flux.

## Decisions / Positions

* Prioritize **info aggregation MVP** (clean UI, clear data fields) to show to stakeholders (e.g., **Gastón**).
* **Wait & watch** for broader market correction but prepare **watchlists/filters** now.
* Emulate **capital allocators’ playbooks**; map **supply chains** around funded themes.

## What the MVP Must Do (v0 → v1)

* **Ingest:** Company registry, filings, press, grants, procurement, patents, hiring, insider trades (public), social, speeches/interviews.
* **Normalize Fields:** `Ticker | Sector | Theme | CEO/Backers | Funding signals | Policy/Reg links | Supply-chain nodes | Momentum (news/hiring) | Valuation hints | Risk flags`.
* **Filters:** `Theme (AI, agro-robotics, space) | Geography (incl. Ukraine) | Policy cue | Time window | Market cap | “Allocator proximity”`.
* **Outputs:** One-page **Company Dossier**, **Why-Now**, **Catalysts (T-line)**, **Copy-the-Rich angle**, **Risk Map**.
* **Ops:** Agentic loop—**Doc ⇄ Code synch**, ticketing, end-of-cycle **compile + unit/integration tests**; CI hook for “run tests before merge.”

## Heuristics (fast)

* **Follow money & mandates:** public budgets, standards, defense/infra programs → supplier trees.
* **Copy > predict:** track what top allocators actually do, not what they say.
* **Policy beats sentiment:** regulation timing is a hard catalyst.
* **Ship learning loops:** smaller features that close feedback faster.

## Risks / Constraints

* **Access to vehicles:** niche funds may be closed/illiquid.
* **Over-automation early:** agents can drift; keep human review at milestones.
* **Signal spoofing:** public “tells” can mislead; validate with multi-source corroboration.

## Open Questions

* Which **two** public instruments best proxy **agro-robotics** right now?
* What **policy calendars** (EU/US/UA) should be polled weekly?
* Minimum viable **Allocator-Proximity** metric (talks, boards, grants, co-investors)?

## People/Notes

* **Gastón:** potential reviewer/sponsor; needs polished demo.
* **Hugo:** hackathon collaborator.
* Emphasis on stamina/productivity via **cognitive offloading** to AI; keep iterating rules/toolchains.

---

*End of pragmatic summary.*&#x20;
