# CommonGround NYC Research

CommonGround NYC Research is the Project 2 Deep Research continuation of
[CommonGround NYC](https://github.com/rf2960/commonground-nyc). It investigates a
specific failure mode from Project 1:

> When the initial meeting areas contain no cafe that is within every traveler's
> commute limit and expected to be open at the meeting time, can a targeted expansion
> find a feasible option? If it cannot, is the blocker commute time, cafe constraints,
> or missing evidence?

This repository preserves the complete Project 1 history and starts from
`2fc33bd29a5e5bde237c31333245bde2f1f89555` on `main`. Project 1 remains unchanged.

## Project 2 status

The repository-preparation milestone is complete. The first implementation checkpoint
is also complete: strict shared contract models and a deterministic two-round fixture
now prove the intended evidence flow without network calls. The inherited Project 1 app
still runs; the parallel runner, provider adapters, Writer, Project 2 UI, eval suite,
and Cloud Run deployment remain later checkpoints.

| Document | Purpose |
| --- | --- |
| [Project plan](docs/PROJECT_PLAN.md) | Scope, phases, risks, and definition of done |
| [Architecture](docs/ARCHITECTURE.md) | Five-agent flow, follow-up policy, and Project 1 reuse |
| [Evidence contracts](docs/EVIDENCE_CONTRACTS.md) | Shared IDs, requests, facts, sources, gaps, and `/chat` trace shape |
| [Team plan](docs/TEAM_PLAN.md) | Module ownership, inputs/outputs, deliverables, and acceptance checks |
| [AI handoff](docs/AI_HANDOFF.md) | Copy-ready prompts and first-PR boundaries for each teammate |
| [Evaluation plan](docs/EVALUATION_PLAN.md) | Three owner-specific examples and the 50+ case eval strategy |
| [Assignment compliance](docs/ASSIGNMENT_COMPLIANCE.md) | Requirement-by-requirement status and final evidence checklist |

### Implemented in the current checkpoint

- `commonground/research/models.py` validates stable IDs, explicit time zones,
  per-traveler limits, agent/round identity, cited facts, explicit gaps, bounded
  follow-up, feasibility states, and credential-free source metadata.
- `tests/research/fixtures/` contains clearly labeled synthetic evidence for initial
  failure, a justified MTA-backed follow-up, and decisive round-2 cafe/exact-route data.
- `tests/research/test_models.py` checks contract round trips, invalid/ambiguous input,
  source integrity, secret rejection, the one-follow-up bound, and the complete fixture
  story. These are fixture claims only, not live provider results.

## Deep Research design

The first turn uses five agent instances across three role shapes:

1. **Lead** clarifies origins, arrival time, and per-person commute limits; reuses the
   Project 1 resolver and candidate generator; and fans out three independent research
   contexts in the same turn.
2. **Transit Researcher** queries Google Routes for per-traveler arrival ETAs.
3. **Cafe Researcher** queries Google Places for cafes and meeting-time regular hours.
4. **Expansion Researcher** uses the MTA Subway Stations dataset to identify plausible
   stations omitted by the initial shortlist.
5. **Writer** turns only structured, cited evidence into a comparison, recommendation,
   blocker diagnosis, and explicit unknowns.

Lead may initiate exactly one targeted follow-up round in the MVP. Typical follow-ups
are cafe search around a few expansion stations or transit checks to specific cafe
addresses after Places results exist. Hard commute limits are evaluated in code, not
by model arithmetic.

## Data sources

- Google Routes API: door-to-door transit duration to an area center or exact cafe.
- Google Places API (New): cafe identity, address, rating, price, and regular opening
  hours.
- [MTA Subway Stations](https://data.ny.gov/Transportation/MTA-Subway-Stations/39hk-dx4f/about_data):
  station coordinates and identifiers used to propose expansion candidates.

Each supported claim must point to a normalized source record. Missing provider data
remains a gap and never silently becomes a negative fact.

## What is reused and what is new

| Project 1 baseline | Project 2 work |
| --- | --- |
| FastAPI app, `/chat`, sessions, and tool trace | Lead/Researcher/Writer orchestration with fresh researcher contexts |
| `resolve_group_locations` | Clarification and per-person commute-limit intake |
| `generate_candidate_areas` | MTA-backed expansion beyond the initial shortlist |
| `get_transit_matrix` | Research tasks for initial centers and exact cafe destinations |
| `search_cafes_in_areas` and opening-hours parser | Cited cafe findings and targeted second-round searches |
| Fairness, fastest, and cafe scoring utilities | Deterministic feasibility/blocker classification |
| Existing decision UI and result cards | Research rounds, evidence, citations, gaps, and comparison display |
| Dockerfile, `pyproject.toml`, `uv.lock`, tests | Fixed-fixture multi-agent slice, real-provider integration, evals, Cloud Run |

Existing provider functions remain small and testable. Project 2 adds orchestration and
normalization around them rather than duplicating their API logic.

## First implementation milestone

Using deterministic fixtures, run this complete trace:

1. Initial areas contain no feasible cafe.
2. Researchers return cited facts plus explicit gaps.
3. Lead records a machine-readable reason for selecting a limited follow-up.
4. The second round returns new evidence for expansion areas or exact cafe addresses.
5. Writer identifies a feasible option or one of the documented blocker categories.
6. `/chat` still returns `response`, `session_id`, and `tool_calls`; every sub-agent
   call also contains `agent` and `round`.

Only after this slice passes do we connect real MTA, Routes, and Places data.

## Setup

The inherited Project 1 app can still be run while Project 2 is implemented:

```bash
uv sync
uv run pytest
uv run app.py
```

Never commit API keys, service-account JSON, `.env`, or generated credentials.

## Planned grading examples

Each teammate owns one example end to end. The complete expected claims, evidence
sources, agent-output capture, and no-tools/no-system-prompt baseline format are in
[docs/EVALUATION_PLAN.md](docs/EVALUATION_PLAN.md).

| Owner | Grader query | Expected supported answer | Required sources |
| --- | --- | --- | --- |
| Ruochen | “Our initial CommonGround areas have no feasible cafe for October 10, 2026 at 2:00 PM Eastern Time. Expand to a few additional MTA stations without changing our commute, rating, price, or opening constraints. Did expansion find a feasible option, and what new evidence changed the answer?” | Name why initial candidates failed, justify the bounded expansion, and recommend an expansion cafe only if exact-address routes and cafe evidence pass all hard constraints. | MTA station record, Google Places cafe record, Google Routes exact-destination result |
| Andrew | “The area-center ETAs are within everyone's limits. Recheck the leading cafe at its exact address for October 10, 2026 at 2:00 PM Eastern Time. Does it still satisfy each person's limit?” | Request the dependency-aware exact-address route check; report actual versus limit for any failing traveler and do not treat a center ETA as cafe ETA. | Google Routes center and exact-cafe requests, Google Places address, clarified traveler limits |
| Wenyu/Yulia | “This cafe has a good rating and acceptable commutes, but can you prove it will be open at our meeting time?” | If regular hours are missing, return `EVIDENCE_INSUFFICIENT`, identify the missing field, and recommend venue verification rather than claiming open/closed. | Google Places record/request, MissingEvidence record, exact-cafe Routes result |

The final README will include the recorded agent answer and same-model baseline for
each example after the fixed-fixture slice exists.

The shared fixture meeting time is **October 10, 2026 at 2:00 PM Eastern Time** so every
Routes, Places-hours, expected-answer, and baseline comparison refers to the same
unambiguous arrival time.

## Course requirements tracked here

- At least Lead, Researcher, and Writer role shapes.
- Several Researchers launched in parallel in fresh contexts.
- Lead can request one additional targeted research round.
- Vague origins, arrival time, or limits trigger clarification.
- Output claims are accurately cited and unknowns are explicit.
- At least 50 sourced eval cases, at least two scoring methods, and a documented
  hill-climbing log before submission.
- Root `app.py`, `pyproject.toml`, `uv.lock`, `README.md`, and `submission.json` remain.
- Final app is deployed to Cloud Run and kept live through grading.

## Team

| Team member | Columbia UNI | GitHub | Project 2 focus |
| --- | --- | --- | --- |
| Ruochen Feng | `rf2960` | `rf2960` | Lead, Writer, parallel runner, MTA expansion, integration |
| Andrew Chen | `yc4745` | `achen711` | Transit Researcher, commute limits, exact-address verification |
| Wenyu Duan (Yulia) | `wd2422` | `Dwyyy123` | Cafe Researcher, opening evidence, research result UI |
