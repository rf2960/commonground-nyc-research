# Team ownership and independent work plan

## Boundary rule

All three contributors implement against `docs/EVIDENCE_CONTRACTS.md`. Each owns a
primary module set and its tests. Changes to shared models, `/chat`, or trace ordering
are reviewed by the owners whose modules consume them. This lets work begin in parallel
without copying provider code or editing the same core files.

| Owner | Columbia UNI | GitHub | Suggested first branch |
| --- | --- | --- | --- |
| Ruochen Feng | `rf2960` | `rf2960` | `ruochen/orchestration-schemas` |
| Andrew Chen | `yc4745` | `yc4745-jpg` | `andrew/transit-researcher` |
| Wenyu Duan (Yulia) | `wd2422` | `Dwyyy123` | `yulia/cafe-researcher` |

## Ruochen — orchestration, expansion, Writer, integration

### Primary modules

- `commonground/research/models.py`
- `commonground/research/runner.py`
- `commonground/research/lead.py`
- `commonground/research/feasibility.py`
- `commonground/research/writer.py`
- `commonground/research/expansion.py`
- integration changes in `app.py`, `tools.py`, and shared integration tests

### Inputs

- Clarified user brief, resolved Project 1 origins, and initial candidate areas.
- Research tasks/results conforming to the shared contracts.
- MTA Subway Stations dataset `39hk-dx4f`.
- Andrew/Yulia adapters exposed through the common runner.

### Outputs

- Validated brief and stable IDs.
- Three-way concurrent first-round dispatch with independent contexts.
- Normalized MTA expansion candidates with cited source records.
- One bounded, machine-readable follow-up decision.
- Deterministic feasibility/blocker results.
- Writer response with citations and explicit unknowns.
- Compatible `/chat` trace with `agent` and `round` on sub-agent calls.

### Deliverables

- Shared schemas and contract-validation tests.
- Fixed-data vertical-slice integration test.
- MTA loader/selector, cache/refresh documentation, and dataset fixtures.
- Citation validator and Writer tests that reject unsupported claims.
- End-to-end integration, eval harness coordination, and Cloud Run release.
- Grading example: expansion turns an initial failure into a feasible recommendation.

### Acceptance criteria

- All three Researchers start in the same Lead turn and do not share mutable contexts.
- One researcher failure produces a partial evidence bundle, not a crashed request.
- Follow-up is never issued without a documented reason, dependency, and bounded target.
- A second follow-up attempt is rejected.
- MTA candidates preserve station IDs/source timestamps and exclude initial duplicates.
- Commute and cafe hard constraints are decided by `feasibility.py`, not Writer prose.
- Every final factual claim resolves to fact/source records; unknowns stay unknown.
- Existing `/chat` keys and session separation tests continue to pass.

### First task

Create `research/models.py` plus the round-1/round-2 fixture bundle and contract tests.
This unblocks Andrew and Yulia without requiring the runner to exist yet.

### Current implementation status

Contracts/fixtures, deterministic feasibility, concurrent runner, bounded Lead, cited
Writer, and the MTA expansion adapter are implemented on Ruochen's stacked branches.
Fixed-data `/chat`/trace integration is also complete. Remaining Ruochen work is live
Transit/Cafe adapter injection, natural-language extraction into the now-validated intake,
the frozen-model baseline/reference-judge run, and shared deployment/eval coordination.
The runnable eval registry, first gold case, deterministic score, and raw Ruochen
agent/trace capture are complete; Andrew and Wenyu can copy the documented case schema
without touching orchestration code.

The dispatcher, service factory, and live MTA expansion task are also complete. Andrew
and Wenyu only need to export the documented async callables; Ruochen will pass them to
`build_research_service` during final integration.

## Andrew — Transit Researcher and commute limits

### Primary modules

- `commonground/research/transit_agent.py`
- targeted extensions to `commonground/transit.py`
- Transit Researcher fixtures and tests under `tests/research/`

### Inputs

- `ResearchBrief` with resolved origins, meeting arrival time, and per-person limits.
- A `ResearchTask` containing initial area IDs, expansion area IDs, or exact cafe IDs.
- Lead-assigned coordinates and, for exact verification, Yulia's cafe coordinates/address.

### Outputs

- Per traveler × destination duration and route-availability facts.
- Google Routes source records, provider warnings, and missing-evidence records.
- A deterministic join between duration facts and each traveler's hard limit for the
  shared feasibility evaluator; the agent itself does not declare pass/fail.

### Deliverables

- Adapter for area-center and exact-cafe Routes tasks using the existing request layer.
- Explicit destination-kind and exact-address verification metadata.
- Tests for traveler ordering, different limits, unavailable routes, partial provider
  responses, arrival time/time zone, and dependency-not-ready behavior.
- Cost/concurrency bound for matrices and exact-cafe verification.
- Grading example: area center appears viable but exact cafe exceeds one limit.

### Acceptance criteria

- Every requested traveler/destination pair yields either facts or a missing record.
- Exact-cafe facts use the cafe ID and cannot be confused with its parent area.
- Arrival time is sent as the requested arrival time and preserved in source context.
- Routes errors are redacted/model-readable and never leak the API key.
- Boundary equality passes (`duration == max_commute_minutes`); any larger duration
  fails in deterministic evaluation.
- Existing Project 1 transit tests remain green.

### First task

Write fixture-driven contract tests for one area-center task and one exact-cafe task,
then implement the thin adapter around `get_transit_matrix` without changing provider
request behavior.

## Yulia — Cafe Researcher, opening evidence, and result UI

### Primary modules

- `commonground/research/cafe_agent.py`
- targeted extensions to `commonground/places.py` and `opening_hours.py`
- Project 2 research presentation in `index.html`
- Cafe Researcher/UI fixtures and tests under `tests/research/`

### Inputs

- `ResearchBrief` with meeting time and active rating/price/open constraints.
- A `ResearchTask` containing initial or MTA expansion area IDs and coordinates.
- Research results, feasibility statuses, sources, and gaps for UI rendering.

### Outputs

- Stable cafe IDs with exact coordinates/address and parent candidate ID.
- Rating, price, business-status, and meeting-time hours facts.
- Google Places source records and explicit missing-hours/provider-error records.
- Result cards showing round, agent, citations, constraint status, and unknowns.

### Deliverables

- Cafe task adapter using existing Places and opening-hours logic.
- Normalization that distinguishes known open/closed from unknown/provisional hours.
- Tests for deduplication across expansion areas, future regular hours, overnight hours,
  missing fields, partial failures, and active-filter behavior.
- UI tests for citations, gaps, exact-address verification, and trace metadata.
- Grading example: missing future hours remains insufficient evidence.

### Acceptance criteria

- Duplicate Places IDs collapse to one cafe while retaining all searched parent areas.
- Missing rating/price/hours remains null plus a gap when required; it is never invented.
- Future opening claims state that they are regular-schedule estimates.
- Active constraints are not silently relaxed when a search is empty.
- The UI visibly distinguishes area-center ETA from exact-cafe ETA.
- Existing Project 1 Places, hours, cafe-scoring, and frontend tests remain green.

### First task

Write the Cafe Researcher normalization tests for a successful cafe, missing hours, and
duplicate place across two areas, then implement the adapter against the shared models.

## Integration checkpoints

1. **Contract freeze:** Ruochen lands models/fixtures; Andrew and Yulia approve consumed
   fields.
2. **Adapter demo:** each Researcher converts one fixture/provider result into facts,
   sources, and gaps without running the LLM.
3. **Vertical slice:** runner and Lead execute the fixed two-round trace; Writer renders
   it; no external API calls.
4. **Live-source smoke:** one bounded MTA/Routes/Places example with saved redacted
   evidence.
5. **UI/evals/deploy:** expose trace, run 50+ cases, record hill climbing, deploy the new
   repository.

## Pull-request review matrix

| Change | Required reviewers |
| --- | --- |
| Shared models/evidence contract | Andrew and Yulia |
| Transit adapter/provider behavior | Ruochen |
| Cafe adapter/opening behavior | Ruochen |
| MTA selection/follow-up policy | Andrew or Yulia |
| Writer citation rules/UI evidence mapping | Yulia and Ruochen |
| `/chat` compatibility/deployment | At least one teammate other than author |
