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
now includes strict shared contracts, a deterministic two-round fixture, the hard-
constraint evaluator, a bounded concurrent Researcher runner, and a dependency-aware
Lead vertical slice, and an evidence-only Writer with citation validation. The inherited
Project 1 app still runs; provider adapters, `/chat` integration, Project 2 UI, eval
suite, and Cloud Run deployment remain later checkpoints.

| Document | Purpose |
| --- | --- |
| [Project plan](docs/PROJECT_PLAN.md) | Scope, phases, risks, and definition of done |
| [Architecture](docs/ARCHITECTURE.md) | Five-agent flow, follow-up policy, and Project 1 reuse |
| [Evidence contracts](docs/EVIDENCE_CONTRACTS.md) | Shared IDs, requests, facts, sources, gaps, and `/chat` trace shape |
| [Data sources](docs/DATA_SOURCES.md) | Endpoints, consumed fields, provenance, fixture/live boundary, and loading plan |
| [Team plan](docs/TEAM_PLAN.md) | Module ownership, inputs/outputs, deliverables, and acceptance checks |
| [AI handoff](docs/AI_HANDOFF.md) | Copy-ready prompts and first-PR boundaries for each teammate |
| [Integration guide](docs/INTEGRATION_GUIDE.md) | Adapter callable, dispatcher, `/chat` boundary, and teammate merge checklist |
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
- `commonground/research/feasibility.py` deterministically computes the four documented
  statuses from normalized evidence, preserves every blocker, treats equality at a
  commute limit as passing, and refuses to hide an absent field that lacks an explicit
  MissingEvidence record.
- `tests/research/test_feasibility.py` proves the fixed round-2 evidence produces the
  expected result and covers commute, cafe, conflict, unknown, boundary, and inactive-
  filter cases.
- `commonground/research/runner.py` launches the three initial Researchers concurrently
  with a fresh message list, role-scoped tool allowlist, per-task timeout, and hard turn
  budget. A failed task becomes explicit missing evidence while successful siblings are
  preserved; raw provider exceptions are not copied into traces.
- `tests/research/test_runner.py` proves actual overlap, deterministic result ordering,
  context isolation, tool-scope enforcement, timeout handling, partial failure, result
  identity validation, and the exact three-role initial fan-out.
- `commonground/research/lead.py` creates the three initial tasks, chooses at most one
  evidence-backed follow-up, waits for expansion Cafe coordinates before exact-address
  Transit, and passes the complete evidence bundle to deterministic feasibility.
- `tests/research/test_lead.py` executes the fixed first-round failure through the
  second-round feasible result and rejects unjustified or invented follow-up targets.
- `commonground/research/writer.py` renders comparison, recommendation/blockers, and
  unknowns only from normalized facts, sources, feasibility records, and gaps. Every
  visible claim carries auditable IDs and provisional future hours remain qualified.
- `tests/research/test_writer.py` rejects uncited or unknown references and proves both
  the feasible recommendation and insufficient-evidence output paths.
- `commonground/research/expansion.py` loads the official MTA Socrata schema through a
  bounded adapter, removes invalid/duplicate/initial-nearby stations, selects at most
  three diverse candidates, and emits cited station facts.
- `tests/research/test_expansion.py` verifies current field normalization, stable IDs,
  bounded deterministic selection, provenance, timeouts/errors, and timestamp safety
  without making live network calls.
- `commonground/research/service.py` joins Lead, deterministic evaluation, and Writer,
  then emits the ordered Project 2 trace while preserving legacy tool-call fields.
- Root `app.py` now accepts an optional structured `research` mode without changing the
  default Project 1 route. It clarifies a missing brief and refuses to claim fixture or
  live results until real Routes/Places adapters are injected.
- `tests/research/test_service.py` proves the full nine-entry fixture trace and the
  unchanged `/chat` response keys, session identity, clarification, and safe unconfigured
  behavior.
- `commonground/research/intake.py` records partial user inputs, produces specific
  clarification gaps, and is the only constructor joining clarified limits/time to
  authoritative Project 1 location and candidate outputs.
- The same intake module now runs the actual Project 1 `resolve_group_locations` and
  `generate_candidate_areas` boundaries in order, stops on only the unresolved people,
  preserves both calls in the Lead trace, and dispatches research only after the joined
  brief validates.
- `commonground/research/intake_extraction.py` converts multi-turn user text into partial
  intake without tools. Every extracted identity, origin, limit, and normalized meeting
  time must cite an exact quote present in the user's messages; unsupported fields are
  rejected and model/auth failures fall back to deterministic clarification.
- `tests/research/test_intake.py` covers missing/naive time, per-traveler origin and
  limit gaps, duplicate identities, unresolved joins, stable candidate IDs, and `/chat`
  clarification without starting research prematurely.
- `evals/runner.py` runs provenance-recorded cases through the real fixed-data pipeline
  and fails on recommendation, feasibility, follow-up, source, answer, bound, or trace
  regressions. Ruochen's first raw capture scores `1.0` on eight golden checks; its
  same-model/no-tools/no-system baseline remains explicitly pending rather than
  fabricated.
- `commonground/research/dispatch.py` is the single production composition boundary:
  it routes each task to exactly one owner adapter, provides the real bounded MTA task,
  and constructs the service while preserving runner timeout/turn limits.
- `index.html` identifies the Project 2 research purpose and renders an accessible,
  round-grouped Lead/Researcher/Writer evidence path whenever `/chat` returns Project 2
  `agent` and `round` trace entries. Its requests now use Project 2 research mode, while
  legacy Project 1 API behavior and result cards remain compatible.

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

Ruochen's fixed-data agent answer and full trace are now captured under `evals/examples/`.
The same-model baseline must be recorded only after the production model is frozen.

Run the current provenance-recorded case registry with:

```bash
uv run python -m evals.runner
```

See [evals/README.md](evals/README.md) for the case schema, capture procedure, and owner
handoff.

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
| Andrew Chen | `yc4745` | `yc4745-jpg` | Transit Researcher, commute limits, exact-address verification |
| Wenyu Duan (Yulia) | `wd2422` | `Dwyyy123` | Cafe Researcher, opening evidence, research result UI |
