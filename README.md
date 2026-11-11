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

The complete Project 2 application is now deployed and publicly reachable at
[commonground-nyc-research-1053619589756.us-east1.run.app](https://commonground-nyc-research-1053619589756.us-east1.run.app).
The build includes strict contracts, bounded concurrent research, one justified
follow-up, deterministic blockers, cited writing, MTA expansion, Project 1 intake reuse,
natural-language clarification, `/chat` trace compatibility, the Project 2 UI, and a
50-case deterministic contract corpus. The Transit, Cafe, and Expansion adapters are
composed through the production dispatcher. A public Cloud Run smoke on November 11,
2026 returned HTTP 200, all five agent instances across rounds 1–2, live Places and
Routes evidence, and exact-cafe commute values versus each person's limit. Frozen-model
no-tools baselines, credentialed rubric-judge captures, and the aggregate hill-climbing
table remain explicit pre-submission evaluation work; they are not represented by the
live service smoke.

| Document | Purpose |
| --- | --- |
| [Project plan](docs/PROJECT_PLAN.md) | Scope, phases, risks, and definition of done |
| [Architecture](docs/ARCHITECTURE.md) | Five-agent flow, follow-up policy, and Project 1 reuse |
| [Evidence contracts](docs/EVIDENCE_CONTRACTS.md) | Shared IDs, requests, facts, sources, gaps, and `/chat` trace shape |
| [Data sources](docs/DATA_SOURCES.md) | Endpoints, consumed fields, provenance, fixture/live boundary, and loading plan |
| [Team plan](docs/TEAM_PLAN.md) | Module ownership, inputs/outputs, deliverables, and acceptance checks |
| [AI handoff](docs/AI_HANDOFF.md) | Copy-ready prompts and first-PR boundaries for each teammate |
| [Integration guide](docs/INTEGRATION_GUIDE.md) | Adapter callable, dispatcher, `/chat` boundary, and teammate merge checklist |
| [Cafe review and handoff](docs/YULIA_REVIEW_AND_HANDOFF.md) | Confirmed integration fixes, Cafe delivery, contract assumptions, and remaining grading work |
| [Evaluation plan](docs/EVALUATION_PLAN.md) | Three owner-specific examples and the 50+ case eval strategy |
| [Assignment compliance](docs/ASSIGNMENT_COMPLIANCE.md) | Requirement-by-requirement status and final evidence checklist |
| [Deployment runbook](docs/DEPLOYMENT.md) | Cloud Run configuration, release verification, and operations checklist |
| [Full-score gap audit](docs/FULL_SCORE_GAP_AUDIT.md) | Rubric-aligned evidence, remaining risks, and prioritized submission work |

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
  default Project 1 route. It clarifies a missing brief and composes the real bounded
  Transit, Cafe, and MTA adapters without making provider requests at import time.
- `tests/research/test_service.py` proves the full nine-entry fixture trace, production
  service construction, unchanged `/chat` response keys, session identity,
  clarification, and safe unconfigured behavior.
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
- `evals/contract_corpus.py` runs 50 provenance-recorded synthetic gold boundary cases
  through the actual feasibility and intake functions: 10 each for feasible, commute,
  cafe, missing-evidence, and clarification slices. The current result is 50/50.
- `evals/rubric_judge.py` supplies the second scoring method with a strict 0–4 reference
  rubric, while `evals/baseline.py` enforces the same-model question-only comparison
  with no tools and no system prompt. Credentialed captures remain pending model freeze.
- `commonground/research/dispatch.py` is the single production composition boundary:
  it routes each task to exactly one owner adapter, provides the real bounded MTA task,
  and constructs the service while preserving runner timeout/turn limits.
- `index.html` identifies the Project 2 research purpose and renders an accessible,
  round-grouped Lead/Researcher/Writer evidence path whenever `/chat` returns Project 2
  `agent` and `round` trace entries. Its requests now use Project 2 research mode, while
  legacy Project 1 API behavior and result cards remain compatible.
- `submission.json` points to the independent public Project 2 Cloud Run service. The
  deployed `/health` endpoint reports `status=ok` and `research_ready=true`.

## Deep Research design

Yulia's missing-hours grading example runs through the actual fixed-data pipeline:
`uv run python -m evals.runner --case evals/cases/yulia_missing_hours.json`.
It returns `EVIDENCE_INSUFFICIENT`, never recommends the venue as open, and cites the
missing-hours record plus the successful exact-route evidence. See the
[raw synthetic input](tests/research/fixtures/yulia_places_missing_hours.json) and
[actual program output and trace](evals/examples/yulia/actual_agent.json).
The deterministic result is 8/8 checks. This is simulated provider evidence, not a
live Google request or model run. The
[same-model baseline](evals/examples/yulia/no_tools_baseline.json) remains explicitly
pending model freeze; the credentialed rubric score and hill-climbing table are also
pending.

The research evidence UI now presents each cafe's status, known attributes, provisional
opening estimate or explicit gap, and per-person exact-cafe commute versus limit.
Area-center estimates have a separate label and cannot fill an exact-route row.
Expandable evidence records link to HTTPS sources and expose fact/gap IDs for auditing.
Six executable renderer tests cover the missing-hours capture, center-only routes,
unsafe source links, provisional hours, area failures, and legacy responses.
The separate Playwright suite now passes four real Chromium checks at desktop and
mobile widths, including scrolling a missing-evidence notice above the composer.
See [the successful browser CI run](https://github.com/rf2960/commonground-nyc-research/actions/runs/42765954735)
and [Yulia's acceptance/run instructions](docs/YULIA_ACCEPTANCE.md). These browser
checks use synthetic chat responses, not live Google or model results.

The separate [live Places capture](evals/examples/yulia/live_places_smoke.json) passed
all six smoke checks on `2026-11-10T07:07:28.941671+00:00`: ten cafes, 81 cited Facts
and eleven Sources from one bounded request. Its ten meeting-time opening estimates
are provisional; it contains no Routes or production-model claims. This live success
is separate from the synthetic missing-hours grading example above.

The [public Cloud Run smoke](evals/examples/ruochen/live_cloud_run_smoke.json) exercises
the deployed `/chat` boundary rather than a fixture. It returned eleven trace entries
covering Lead, Transit, Cafe, Expansion, and Writer across rounds 1–2. The response
recommended two feasible cafes with exact-address Routes evidence, diagnosed one
commute-limit failure with the actual value and limit, qualified future opening hours,
and cited normalized Google Places and Routes source IDs. This is a bounded operational
smoke, not a substitute for the required same-model baseline or 50-case hill-climbing
experiment.

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

That fixture milestone now passes, and the live MTA, Routes, and Places adapters are
connected through the same contracts. Provider-backed smoke evidence remains separate
from synthetic grading examples.

## Setup

The inherited Project 1 app can still be run while Project 2 is implemented:

```bash
uv sync
uv run pytest
uv run app.py
```

Never commit API keys, service-account JSON, `.env`, or generated credentials.

## Live deployment

- App: [CommonGround NYC Research](https://commonground-nyc-research-1053619589756.us-east1.run.app)
- Health: [`/health`](https://commonground-nyc-research-1053619589756.us-east1.run.app/health)
- Platform: Google Cloud Run, `us-east1`, continuous deployment from `main`
- Runtime bounds: 300-second Cloud Run request timeout, 45 seconds per Researcher task,
  six turns per task, concurrency 10, and at most three service instances

The Maps credential is referenced from Secret Manager at runtime and never appears in
the repository, browser trace, or `/chat` response. See the
[deployment runbook](docs/DEPLOYMENT.md) for configuration and release checks.

## Grader queries

Choose **Deep Research** and start a new meetup for each query. The examples use
December 4, 2026. For later grading, substitute a future Friday at the same
local time. Transit schedules and available venue evidence may change.

The [public-service captures](evals/examples/live_grader_queries.json) contain
the actual Writer answers, source IDs and trace. They used the live `/chat`
endpoint with explicit structured intake to hold the stated constraints fixed.
The intake fix in this release preserves those same rating and price constraints
when they are entered as text. Gemini 3.5 Flash-Lite extracts the natural-language
intake. The cited Writer renders the deterministic evidence and feasibility result.

### Expand a failed shortlist

> Alex starts at Columbia University with a 22-minute transit limit, Blair starts in Astoria with a 20-minute transit limit, and Casey starts at Bedford Ave Station with a 24-minute transit limit. We meet December 4, 2026 at 2:00 PM Eastern Time. Find a cafe with a minimum rating of 5 stars and a moderate price. Do not relax the 5-star minimum. If the initial areas fail, check whether expanding to more MTA stations can help without relaxing any limit. Explain what the evidence supports.

| Expected result and sources | Actual agent answer (summary) | Same-model no-tools answer |
| --- | --- | --- |
| Keep the constraints fixed, search a bounded set of additional MTA stations, and report whether the expanded search supports a recommendation. MTA Subway Stations (Socrata dataset `39hk-dx4f`), Google Places Nearby Search, and Google Routes Compute Route Matrix. | The follow-up checked three MTA areas. The Writer reported no supported recommendation and flagged missing price evidence. | Pending an authenticated Vertex run. |

### Check exact cafe routes

> Alex starts at Columbia University with a 35-minute transit limit, Blair starts in Astoria with a 30-minute transit limit, and Casey starts at Bedford Ave Station with a 40-minute transit limit. We meet December 4, 2026 at 2:00 PM Eastern Time. Find a moderate-price cafe rated at least 4.3. Check each commute to the exact cafe address and report the actual times versus the individual limits.

| Expected result and sources | Actual agent answer (summary) | Same-model no-tools answer |
| --- | --- | --- |
| Verify each traveler’s transit duration to the actual cafe before deciding whether it meets their individual limit. Google Places Nearby Search for venue coordinates and Google Routes Compute Route Matrix for exact transit times. | Little Collins qualified. Exact commutes were 29.9/35, 28.6/30, and 22/40 minutes. | Pending an authenticated Vertex run. |

### Qualify opening-hour evidence

> Alex starts at Columbia University with a 35-minute transit limit, Blair starts in Astoria with a 30-minute transit limit, and Casey starts at Bedford Ave Station with a 40-minute transit limit. We meet December 4, 2026 at 2:00 PM Eastern Time. Find a moderate-price cafe rated at least 4.3 that is open at the meeting time. What can the available hours evidence establish, and what should we verify with the cafe?

| Expected result and sources | Actual agent answer (summary) | Same-model no-tools answer |
| --- | --- | --- |
| Report what the available regular hours suggest and explain what the group should verify with the venue. Google Places Nearby Search regular opening hours and venue coordinates, plus Google Routes Compute Route Matrix. | Little Collins qualified on the available evidence. The Writer identified opening as a future regular-schedule estimate and advised venue verification. | Pending an authenticated Vertex run. |

Use the following command in a Vertex-authenticated checkout to capture the
same Gemini model's answer to each question with no tools and no system prompt.
Copy the captured answers into the corresponding README rows before submission.

```bash
uv run python -m evals.capture_grader_baselines
```

The [fixed-data regression suite](docs/EVALUATION_PLAN.md) separately covers
successful MTA expansion, a cafe-specific route that exceeds a limit, and
missing opening hours. Those fixture outputs are reproducible offline.

Run the current provenance-recorded case registry with:

```bash
uv run python -m evals.runner
```

Run the 50-case contract corpus with:

```bash
uv run python -m evals.contract_corpus
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
