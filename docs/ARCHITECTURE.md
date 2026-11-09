# Deep Research architecture

## Runtime shape

Project 2 has three agent role shapes and five instances in the initial turn:

```text
User /chat request
       |
       v
Lead -- clarify + reuse Project 1 location/candidate tools
       |
       +---- parallel, fresh context ---- Transit Researcher
       +---- parallel, fresh context ---- Cafe Researcher
       +---- parallel, fresh context ---- Expansion Researcher
       |
       v
deterministic feasibility + gap analysis
       |
       +---- optional one targeted follow-up round
       |       (expansion cafe search and/or exact-address transit)
       v
Writer -- comparison + recommendation/blocker + citations + unknowns
       |
       v
compatible /chat response and visible trace
```

Researchers may use one generic runner, but each invocation receives a new message list,
one role prompt, one allowlisted tool set, the same immutable research brief, and a
deadline. No Researcher sees another Researcher's chain-of-thought or mutable context.
`commonground/research/runner.py` now enforces this boundary for the three initial tasks,
including concurrent execution, deterministic output order, a hard turn budget, and
explicit missing-evidence results for timeout, execution, or validation failure.

## Lead responsibilities

Lead owns planning and control flow, not provider facts.

1. Clarify ambiguous origins, arrival time/time zone, missing per-person limits, and
   active cafe constraints before research begins.
2. Call Project 1 location resolution and initial candidate generation.
3. Assign stable candidate IDs and create one immutable `ResearchBrief`.
4. Dispatch all three first-round Researchers concurrently.
5. Validate their structured results and pass facts to deterministic feasibility/gap
   analysis.
6. If needed, record one `FollowUpDecision` and dispatch only tasks whose dependencies
   are available.
7. Hand the complete evidence bundle to Writer.

The Lead does not claim that a cafe is feasible. It asks deterministic code for the
status and uses the returned blockers to plan a follow-up.
`commonground/research/lead.py` implements this bounded fixed-data control flow. It
creates the three initial tasks, emits at most one `FollowUpDecision`, and does not
create an exact-cafe Transit task until the selected Cafe result supplies coordinates.

## Researcher responsibilities

### Transit Researcher

- Round 1: Routes ETA from every resolved origin to every initial area center.
- Round 2: Routes ETA to exact cafe coordinates/addresses selected after Cafe results.
- Preserve traveler order, arrival time, route availability, provider warnings, and
  attribution.
- Emit duration facts; do not decide whether limits pass.

### Cafe Researcher

- Search initial or expansion areas through Google Places.
- Normalize identity, exact address/coordinates, rating, price, business status, and
  regular-schedule opening estimate at the meeting time.
- Missing hours remain a gap. A future regular-hours estimate is provisional, not a
  guarantee.
- Emit cafe facts; do not relax active filters.

### Expansion Researcher

- Use the MTA Subway Stations dataset to propose stations omitted from the initial
  shortlist.
- Prefer a small, diverse set that plausibly improves access; preserve dataset station
  ID, coordinates, line/name metadata, and source record.
- Exclude duplicates/near-duplicates of initial areas and return the selection rationale.
- It proposes candidates only; Routes and Places must verify feasibility.

## Follow-up policy

The MVP permits a single follow-up round. Lead chooses the smallest task set that can
resolve a decision-critical gap:

| Finding after round 1 | Targeted follow-up |
| --- | --- |
| No qualifying cafe in initial areas; expansion candidates exist | Cafe search around at most three expansion stations, then exact-address transit for promising cafes if the bounded task can include both dependencies |
| Qualifying cafes exist but transit is only to area centers | Transit to a bounded set of exact cafe destinations |
| Transit to initial areas already violates hard limits and expansion candidates exist | Transit to the most promising expansion centers before cafe verification |
| Missing hours or provider failure is the only blocker | One retry only if marked retryable; otherwise report insufficient evidence |
| Evidence already proves feasibility or a terminal blocker | No follow-up |

Because exact cafe routing depends on Places output, that task cannot be dispatched until
the relevant cafe record exists. The runner supports ordered tasks inside round 2 while
still enforcing the single follow-up-round budget.

Every follow-up records:

- `reason_code` and the unresolved predicate;
- selected candidate/cafe IDs;
- dependencies and role/tool requested;
- expected information gain; and
- why unselected expansion candidates were not queried.

## Deterministic decision layer

The evaluator joins evidence by stable IDs and produces one status per cafe:

1. `EVIDENCE_INSUFFICIENT` if any required route, limit, cafe field, or hours fact is
   missing or stale.
2. `COMMUTE_LIMIT_EXCEEDED` if complete exact-address routes show any traveler's duration
   above that traveler's limit.
3. `CAFE_CONSTRAINT_FAILED` if complete cafe evidence violates rating, price, business
   status, or opening constraints.
4. `FEASIBLE` only when all required checks pass.

If several reasons apply, the evaluator returns all reason records. The top-level Writer
may summarize them but cannot change their meaning.

## Writer boundary

`commonground/research/writer.py` implements the fixed-data Writer boundary. It renders
only indexed facts, sources, missing-evidence records, follow-up decisions, and
feasibility results. Its validator requires every referenced ID to exist, requires each
claim's sources to match its cited facts, and requires every citation to appear in the
user-visible response. Future regular-hours evidence is explicitly labeled as an
estimate rather than a guarantee.

## Project 1 reuse map

| Existing file/module | Reuse | Project 2 extension point |
| --- | --- | --- |
| `app.py` | FastAPI route, session ID, response model | Orchestrator service and trace metadata |
| `tools.py` | Tool schemas and JSON error boundary | Role-scoped registries/allowlists |
| `commonground/locations.py` | Origin resolution | Lead clarification and brief normalization |
| `commonground/candidates.py` | Initial shortlist | Stable IDs and separation from expansion candidates |
| `commonground/transit.py` | Google Routes request/normalization | Research tasks, exact cafe destinations, per-person limit join |
| `commonground/places.py` | Google Places search | Fact/source/gap output for initial and expansion areas |
| `commonground/opening_hours.py` | NYC-time regular-hours estimate | Explicit provisional evidence and missing-hours gaps |
| `commonground/fairness.py` / `fastest.py` / `cafes.py` | Explainable scoring utilities | Optional ranking after feasibility, never a substitute for it |
| `commonground/recommendations.py` | Authoritative result alignment | Writer evidence bundle and blocker-aware comparison |
| `index.html` | Decision/result UI | Round, agent, citation, gap, and exact-address indicators |
| `tests/` | Provider fixtures and boundary tests | Multi-agent contract, concurrency, follow-up, and citation tests |

## Proposed new modules

The names are the integration contract; owners may split implementation files if tests
and imports remain clear.

```text
commonground/research/
  models.py          shared typed records and validation
  runner.py          fresh-context researcher execution and bounded concurrency
  lead.py            clarification, fan-out, follow-up decision, Writer handoff
  feasibility.py     deterministic hard-constraint and blocker evaluation
  writer.py          evidence-only report assembly and citation validation
  expansion.py       MTA dataset loader and expansion candidate selection
  transit_agent.py   Transit Researcher task adapter
  cafe_agent.py      Cafe Researcher task adapter
tests/research/
  fixtures/          deterministic round-1/round-2 evidence
  test_vertical_slice.py
```

## Operational bounds

- Initial Researchers: exactly three concurrent tasks.
- Follow-up: one round, at most three expansion areas, and a documented bound on cafes
  routed to exact addresses.
- Provider requests: explicit timeout, partial-result handling, and no automatic
  unbounded retry.
- Agent turns: hard maximum in the runner; Cloud Run request timeout kept below the
  course's five-minute grading allowance.
- Secrets: server environment only; never placed in prompts, tool results, or traces.
