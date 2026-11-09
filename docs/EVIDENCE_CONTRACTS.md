# Evidence and agent contracts

These shapes are the shared boundary between Lead, the three Researchers, deterministic
evaluation, Writer, `/chat`, and the UI. Examples use JSON-compatible values even if the
implementation uses Pydantic models or dataclasses.

Contract version `research-contract-v1` is implemented in
`commonground/research/models.py`. Canonical synthetic examples live in
`tests/research/fixtures/`; they are test evidence and must never be presented as live
MTA, Google Routes, or Google Places results.

The implementation additionally enforces three cross-record safety rules implied by
this document: `research_id` and `task_id` must refer to the same session, every Fact's
source must be present in its ResearchResult, and Source URLs/request summaries must not
contain credential fields.

## Stable identifiers

- Traveler: `traveler:<lead-assigned-slug>`; stable for the session.
- Initial area: `area:initial:<slug>`; assigned by Lead after Project 1 generation.
- Expansion station/area: `area:mta:<station-id>`; derived from the dataset identifier.
- Cafe: `cafe:gplaces:<place-id>`; derived from Google Places identity.
- Fact: `fact:<agent>:<round>:<sequence>`.
- Source: `source:<provider>:<request-or-record-id>`.
- Research task: `task:<session-id>:r<round>:<agent>:<sequence>`.

IDs are never recomputed from display labels. When two agents refer to the same entity,
they must use the ID assigned by Lead or the provider-derived cafe/station ID.

## Research brief

Lead creates one immutable brief after clarification:

```json
{
  "research_id": "research:session-123:1",
  "session_id": "session-123",
  "question": "Can bounded expansion find a feasible cafe?",
  "meeting_time": "2026-11-18T18:00:00-05:00",
  "travelers": [
    {
      "traveler_id": "traveler:alice",
      "input_location": "Columbia University",
      "resolved_location": {"lat": 40.8075, "lng": -73.9626},
      "max_commute_minutes": 35
    }
  ],
  "cafe_constraints": {
    "min_rating": 4.3,
    "price_levels": [1, 2],
    "require_open": true
  },
  "initial_candidates": [
    {
      "candidate_id": "area:initial:union-square",
      "name": "Union Square",
      "kind": "initial_area",
      "lat": 40.7359,
      "lng": -73.9911
    }
  ],
  "max_follow_up_rounds": 1
}
```

Validation rejects missing time zones, duplicate traveler/candidate IDs, non-positive
limits, unresolved origins, and unsupported constraint values before fan-out.

## Research task

```json
{
  "task_id": "task:session-123:r1:transit:1",
  "research_id": "research:session-123:1",
  "round": 1,
  "agent": "transit_researcher",
  "objective": "Measure arrival ETAs to initial area centers",
  "candidate_ids": ["area:initial:union-square"],
  "dependencies": [],
  "allowed_tools": ["get_transit_matrix"]
}
```

`agent` is one of `lead`, `transit_researcher`, `cafe_researcher`,
`expansion_researcher`, or `writer`. Researchers receive only the brief and their task.

## Research result

```json
{
  "task_id": "task:session-123:r1:transit:1",
  "agent": "transit_researcher",
  "round": 1,
  "status": "complete",
  "facts": [],
  "sources": [],
  "missing": [],
  "candidate_ids_considered": ["area:initial:union-square"],
  "summary": "One area/traveler matrix collected."
}
```

`status` is `complete`, `partial`, or `failed`. A partial/failed result still carries
available facts, sources, and missing records. Free-text `summary` cannot be used as a
decision fact.

## Fact

```json
{
  "fact_id": "fact:transit:r1:001",
  "candidate_id": "area:initial:union-square",
  "subject_id": "traveler:alice",
  "predicate": "transit_duration_minutes",
  "value": 31.2,
  "unit": "minutes",
  "observed_at": "2026-11-07T20:15:00Z",
  "valid_for": {"arrival_time": "2026-11-18T18:00:00-05:00"},
  "source_ids": ["source:google-routes:req-abc"],
  "provisional": false
}
```

Required predicates initially include:

- Transit: `transit_duration_minutes`, `route_available`.
- Cafe: `name`, `address`, `coordinates`, `rating`, `price_level`, `business_status`,
  `open_at_meeting_time`.
- Expansion: `station_name`, `coordinates`, `routes_or_lines`,
  `expansion_selection_reason`.

A fact must have at least one source ID. Derived feasibility records cite their input
fact IDs and the deterministic rule version rather than an external provider.

## Source

```json
{
  "source_id": "source:google-routes:req-abc",
  "provider": "google_routes",
  "title": "Routes API transit matrix",
  "url": "https://developers.google.com/maps/documentation/routes",
  "accessed_at": "2026-11-07T20:15:00Z",
  "request_summary": {
    "origin_count": 3,
    "destination_count": 2,
    "arrival_time": "2026-11-18T18:00:00-05:00"
  },
  "provider_record_ids": [],
  "attribution": "Google Maps"
}
```

The source record must contain enough request context to reproduce or audit a claim,
without secrets or full credential-bearing URLs. The MTA source includes dataset ID
`39hk-dx4f`, the record/station ID, and dataset retrieval timestamp. Places sources
include the place ID and Google Maps URL when available.

## Missing evidence

```json
{
  "missing_id": "missing:cafe:r1:001",
  "candidate_id": "cafe:gplaces:place-123",
  "subject_id": null,
  "field": "open_at_meeting_time",
  "reason_code": "PROVIDER_FIELD_MISSING",
  "detail": "Regular opening periods were absent.",
  "retryable": false,
  "next_action": "Report opening status as unknown; ask the user to verify with venue."
}
```

Common reason codes are `PROVIDER_FIELD_MISSING`, `ROUTE_UNAVAILABLE`,
`PROVIDER_ERROR`, `DEPENDENCY_NOT_READY`, `STALE_EVIDENCE`, `VALIDATION_ERROR`,
`AGENT_EXECUTION_ERROR`, and `TIMEOUT`.
Missing IDs use `missing:<agent>:r<round>:<sequence>`. `subject_id` identifies the
affected traveler when a field such as an exact route is missing for only one person.
Feasibility reasons cite `input_missing_ids`; Writer can therefore resolve each unknown
to its provider reason and next action instead of citing an absence indirectly.
Runner-level failures use a fixed, credential-free detail string rather than copying
an arbitrary SDK/provider exception into the evidence trace.

## Follow-up decision

```json
{
  "round": 2,
  "reason_code": "EXACT_DESTINATION_REQUIRED",
  "unresolved_predicate": "transit_duration_minutes to exact cafe",
  "selected_ids": ["cafe:gplaces:place-123"],
  "task_agents": ["transit_researcher"],
  "dependencies": ["fact:cafe:r1:008"],
  "expected_information_gain": "Resolve all commute-limit checks for the leading cafe.",
  "omitted_candidate_reason": "Lower-ranked cafes cannot pass the active rating filter."
}
```

Lead may emit at most one such record. The deterministic follow-up policy validates the
round and task bounds.

## Feasibility result

```json
{
  "cafe_id": "cafe:gplaces:place-123",
  "status": "COMMUTE_LIMIT_EXCEEDED",
  "reasons": [
    {
      "code": "TRAVELER_LIMIT_EXCEEDED",
      "traveler_id": "traveler:alice",
      "actual_minutes": 38.4,
      "limit_minutes": 35,
      "input_fact_ids": ["fact:transit:r2:004"],
      "input_missing_ids": []
    }
  ],
  "rule_version": "feasibility-v1"
}
```

Allowed statuses are `FEASIBLE`, `COMMUTE_LIMIT_EXCEEDED`,
`CAFE_CONSTRAINT_FAILED`, and `EVIDENCE_INSUFFICIENT`.

`commonground/research/feasibility.py` implements `feasibility-v1`. Evidence
insufficiency takes status precedence, followed by commute-limit failure and cafe-
constraint failure, while the result retains every supported reason. A required field
that has neither a Fact nor a MissingEvidence record is a contract error, not a silent
unknown.

## `/chat` compatibility and trace

The top-level response stays:

```json
{
  "response": "Writer output with citations",
  "session_id": "session-123",
  "tool_calls": [
    {
      "agent": "transit_researcher",
      "round": 1,
      "name": "get_transit_matrix",
      "args": {},
      "result": "{}"
    }
  ]
}
```

Legacy Project 1 calls may omit `agent`/`round` only during migration. All Project 2
sub-agent calls require them. Ordering is deterministic: Lead preparation, round 1 tasks
sorted by agent, follow-up decision, round 2 tasks, deterministic evaluation, Writer.

## Writer citation rules

- Every external factual claim cites at least one source ID through its fact ID.
- Derived statements cite the feasibility record and its input fact IDs.
- Comparisons distinguish area-center estimates from exact-address ETAs.
- Regular-hours evidence is labeled provisional for future dates.
- Unknowns list the matching missing-evidence record and next action.
- Writer may omit low-value facts for readability but may not introduce uncited facts.
