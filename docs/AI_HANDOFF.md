# AI handoff guide

This file is the shortest safe entry point for a teammate starting a fresh AI coding
session. The AI must also read `AGENTS.md`, `docs/EVIDENCE_CONTRACTS.md`, the relevant
section of `docs/TEAM_PLAN.md`, and the Project 1 module it will reuse before editing.

**Current handoff:** Ruochen's shared contracts, orchestration, natural-language intake,
fixed-data vertical slice, and evaluation gates are already on `main`. Andrew and Wenyu
should use their sections below now; they do not need to wait for another Ruochen PR.

## Shared rules for every teammate and AI

1. Work from the latest `main` on a focused branch; do not commit directly to `main`.
2. Keep the first pull request fixture-driven and within the owner boundary below.
3. Reuse existing provider request code. Do not create a second Routes or Places client.
4. Do not change shared IDs or evidence shapes silently. Propose contract changes in the
   PR description and request review from both consuming owners.
5. Do not add real secrets or call paid APIs in unit tests.
6. Preserve Project 1 behavior and `/chat` compatibility.
7. Finish with changed files, tests run, assumptions, unresolved questions, and next
   integration dependency.

Before coding, run:

```bash
git status
git pull --ff-only origin main
uv sync
uv run pytest
uv run python -m evals.runner
uv run python -m evals.contract_corpus
```

If the baseline is not clean or tests fail before the change, stop and report the exact
state rather than overwriting or debugging unrelated work.

## Ruochen first PR — shared contracts and fixed fixtures

Suggested branch: `ruochen/orchestration-schemas`

Copy this prompt into a fresh AI coding session:

```text
You are implementing Ruochen's first Project 2 PR in CommonGround NYC Research.
Read AGENTS.md, docs/EVIDENCE_CONTRACTS.md, docs/ARCHITECTURE.md, and Ruochen's section
of docs/TEAM_PLAN.md completely before editing.

Scope: create commonground/research/models.py and deterministic round-1/round-2 fixture
files plus contract validation tests. Model ResearchBrief, ResearchTask, ResearchResult,
Fact, Source, MissingEvidence, FollowUpDecision, and FeasibilityResult exactly from the
documented v1 contract. The fixture must encode: initial candidates fail, Lead has a
machine-readable reason to follow up, and round 2 adds decisive new evidence. Do not
implement the LLM runner, real MTA download, provider adapters, Writer, or UI yet.

Acceptance: duplicate IDs, missing time zone, non-positive commute limits, unsupported
agents/rounds/statuses, uncited facts, and a second follow-up are rejected. Valid fixtures
round-trip without information loss. Existing Project 1 tests remain green. Add focused
tests under tests/research/. End with changed files, tests run, assumptions, and fields
that Andrew/Yulia must approve.
```

The PR is ready only when Andrew and Yulia can implement adapters without inventing any
new shared field.

## Andrew first PR — Transit Researcher adapter

Suggested branch: `andrew/transit-researcher`

Copy this prompt into Andrew's fresh AI coding session:

```text
You are implementing Andrew's first Project 2 PR in CommonGround NYC Research.
Read AGENTS.md, docs/EVIDENCE_CONTRACTS.md, docs/ARCHITECTURE.md, docs/AI_HANDOFF.md,
Andrew's section of docs/TEAM_PLAN.md, and the existing commonground/transit.py plus its
tests completely before editing.

Prerequisite status: satisfied on main. Confirm `commonground/research/models.py` and
`evals/contract_corpus.py` exist after pulling; do not invent a competing schema.

Scope: write fixture-driven contract tests for one area-center task and one exact-cafe
task, then implement a thin commonground/research/transit_agent.py adapter around the
existing get_transit_matrix provider layer. Emit per-traveler duration/availability
facts, Google Routes source records, and one MissingEvidence record for every absent
requested pair. Preserve arrival time, traveler order, candidate/cafe IDs, provider
warnings, and whether the destination is an area center or exact cafe. Do not implement
Lead, Writer, Cafe, Expansion, UI, or a second Routes client. Do not let the model decide
hard-limit pass/fail.

Acceptance: every requested traveler-destination pair produces facts or a gap; exact
cafe facts use the cafe ID; boundary equality is represented without rounding changes;
provider errors are redacted; no API key enters output; existing transit and full test
suites remain green. End with changed files, tests run, assumptions, and the exact input
fields required from Cafe/Lead.
```

Andrew's grading-example ownership is the case where an area-center estimate passes but
exact-cafe routing exceeds one traveler's hard limit.

## Wenyu/Yulia first PR — Cafe Researcher adapter

Suggested branch: `yulia/cafe-researcher`

Copy this prompt into Wenyu/Yulia's fresh AI coding session:

```text
You are implementing Wenyu/Yulia's first Project 2 PR in CommonGround NYC Research.
Read AGENTS.md, docs/EVIDENCE_CONTRACTS.md, docs/ARCHITECTURE.md, docs/AI_HANDOFF.md,
Yulia's section of docs/TEAM_PLAN.md, and the existing commonground/places.py,
commonground/opening_hours.py, commonground/cafes.py, and their tests completely before
editing.

Prerequisite status: satisfied on main. Confirm `commonground/research/models.py` and
`evals/contract_corpus.py` exist after pulling; do not invent a competing schema.

Scope: first write normalization tests for a successful cafe, missing future hours, and
the same Places ID returned from two areas. Then implement a thin
commonground/research/cafe_agent.py adapter around the existing Places/opening-hours
layer. Emit stable cafe IDs, parent candidate IDs, exact address/coordinates, rating,
price, business status, meeting-time opening facts, Google Places source records, and
explicit gaps. Preserve all searched parent areas when deduplicating. Do not implement
Lead, Writer, Transit, Expansion, or UI in this first PR. Never relax active filters or
turn missing hours into open/closed.

Acceptance: future regular hours are labeled provisional; missing required fields remain
null plus a gap; duplicate Places IDs collapse deterministically; partial provider
failure preserves successes; no API key enters output; existing Places, hours, cafe, and
full test suites remain green. End with changed files, tests run, assumptions, and the
exact cafe fields Transit needs for exact-address verification.
```

Wenyu/Yulia's grading-example ownership is the case where a cafe and route exist but
future opening evidence is missing, so the supported result stays insufficient.

## Pull request template for AI-generated work

Use this structure in every PR description:

```markdown
## Owner and scope

## Contract version and assumptions

## Changed files

## Tests run and results

## Fixture evidence vs. live-provider evidence

## Dependencies for the next owner

## Unresolved questions or evidence gaps

## Out-of-scope items intentionally not implemented
```

No teammate should merge an AI-authored PR whose tests, evidence type, or out-of-scope
work are unclear.
