# Cafe adapter review and handoff

## Review baseline

Reviewed `main` at `9a8f5d9`: models, evidence contracts, runner, dispatcher, Lead,
feasibility, Writer, service, assignment checklist, and evaluation harness. Before
these changes, the local branch (including the initial Places preparation) passed
270 tests, the one registered fixed-data pipeline case, and 50/50 synthetic contract
cases. Passing those checks did not prove live-provider integration.

## Confirmed issues and regression coverage

| Issue | Correction | Evidence |
| --- | --- | --- |
| Round-2 tasks received dependency IDs but not coordinates from prior results; fixture executors masked the missing payload | Runner creates an isolated structured dependency bundle; Lead supplies it before expansion Cafe and exact Transit execution | `test_exact_cafe_transit_task_waits_for_cafe_coordinates`, `test_round_two_uses_cited_expansion_coordinates` |
| Unknown hours removed cafes before exact verification, preventing Yulia's intended insufficient-evidence path | Prioritize fully known cafes, then allow bounded exact routing for otherwise passing cafes with an explicit hours gap; the gap remains intact | `test_missing_hours_runs_through_actual_lead_feasibility_and_writer`, `evals/cases/yulia_missing_hours.json` |
| Nonfinite route durations and out-of-range venue coordinates could pass deterministic checks | Reject nonfinite numbers and invalid coordinate ranges as insufficient evidence | `test_nonfinite_route_duration_cannot_be_feasible`, `test_invalid_exact_coordinates_cannot_support_recommendation` |
| Source URL checks did not reject common `key`/`access_token` queries or embedded HTTP credentials | Tightened URL and nested request-summary credential validation | `tests/research/test_source_security.py` |
| Duplicate missing IDs were accepted by a result, then failed later in Writer indexing | Reject duplicate missing IDs at the contract boundary | `test_duplicate_missing_ids_are_rejected_before_writer` |
| Writer validated cited facts/sources but accepted arbitrary derived references or a recommendation ID lacking a FEASIBLE result | Validate derived references and recommendation IDs against the Lead run | `test_unknown_derived_reference_does_not_bypass_citation_validation`, `test_recommendation_id_must_have_feasible_evidence` |
| A completely empty bounded search could render no explicit result | Return a calibrated no-supported-recommendation statement; do not infer city-wide absence | `test_empty_bounded_search_has_explicit_result_not_blank_answer` |

## Cafe delivery

- Exported async `run_cafe_task(context, brief, task)` plugs into the existing dispatcher.
- Existing HTTP provider and opening-hours parser are reused. No second Places client,
  cross-session state, model-generated arithmetic, or implicit filter relaxation.
- Stable provider-derived IDs, all parent area IDs, exact address/coordinates, rating,
  price, business status, provisional schedule facts, auditable sources, explicit gaps.
- Partial provider failures preserve successful evidence. Missing coordinates, malformed
  records, conflicts, missing credentials, and provider errors remain explicit gaps.
- Requests are bounded to six areas, three simultaneous requests, ten records per
  search, 800-meter radius, inherited 15-second request timeout; no retry loop.
- Synthetic missing-hours grading example has raw provider-shaped input, normalized
  results, actual program/trace capture, and deterministic scoring in the common harness.

## Contract review needed

No v1 shared fields or ID formats change. Additive runtime context:
`ResearchContext.dependency_results`. Additive Fact metadata:
`valid_for.parent_candidate_ids`. Source credential checks and duplicate MissingEvidence
ID checks are stricter. Ruochen and Andrew should review these consumed boundaries.
The singular parent Fact keeps a deterministic primary parent for existing consumers.

## Remaining score-critical work

| Requirement | Current evidence | Remaining work / owner |
| --- | --- | --- |
| Real provider data | Cafe adapter is mock-tested; MTA loader exists | Record bounded live Places and Routes smoke evidence, wire both adapters / team integration |
| Usable deployed application | Project 2 `/chat` boundary and research timeline exist | Production service injection and a new live Cloud Run URL / Ruochen |
| Complete readable evidence UI | Existing timeline and raw trace exist | Venue cards with citations, gaps, and exact-vs-center distinctions / Yulia follow-up |
| Three grading examples | Ruochen and Yulia synthetic cases now run | Andrew example and live/model captures / each owner |
| 50+ evals | 50 synthetic contract cases pass | Provider and full-pipeline coverage; synthetic contract count alone is not evidence of 50 real research successes / team |
| Two scoring approaches | Deterministic scores executed; rubric judge code exists | Run credentialed rubric scores after freezing the model / Ruochen |
| Same-model no-tools/no-system comparison | Capture helpers and explicit pending files exist | Freeze production Writer model/architecture, then capture actual model outputs / team |
| Hill climbing and uncertainty | No fabricated score improvements | Run baseline and at least two changes on a fixed held-out set; report ±1/sqrt(n) / Ruochen |
| Agent execution semantics | Lead/Writer are currently deterministic orchestration/rendering, with a model-executor injection boundary | Verify this runtime against the course's agent-role requirement before claiming the live Deep Research path complete / team |

This review is not a guarantee of full marks or an exhaustive security audit. Synthetic
fixtures never become live API/model observations merely because they pass a test.
