# Project 2 plan

## Goal and decision question

CommonGround should not stop at “no result” when the Project 1 shortlist fails. It
should determine whether a small, evidence-driven expansion can find a feasible cafe
and, if not, explain which constraint or evidence gap prevents a recommendation.

A cafe is feasible only when all of the following are supported:

1. every traveler has an available route to the exact destination;
2. every traveler's duration is at or below that traveler's hard limit;
3. the cafe satisfies active rating/price constraints;
4. the cafe is expected to be open at the requested meeting time; and
5. the evidence is sufficiently complete and attributable.

The system never interprets missing route or hours data as a confirmed failure. It
labels that outcome `EVIDENCE_INSUFFICIENT` and says what to check next.

## Scope

### In the MVP

- One Lead, three Researchers, and one Writer.
- Parallel first-round Transit, Cafe, and Expansion research in fresh contexts.
- One targeted follow-up round chosen from structured findings.
- Initial area-center routing followed by exact-cafe routing when needed.
- Google Routes, Google Places, and MTA Subway Stations evidence.
- Code-enforced per-person commute limits and blocker classification.
- Traceable facts, sources, gaps, agent names, and research rounds.
- Existing `/chat` response compatibility and a research-oriented UI.
- Fixed-fixture vertical slice, real-provider integration, evals, and Cloud Run.

### Deferred

- More than one follow-up round or open-ended autonomous research.
- Reservations, payments, user accounts, durable conversation storage, and RAG.
- Live service alerts, accessibility routing, seating/noise verification, and holiday
  opening guarantees unless explicitly added as new cited sources.

## Phases and gates

### Phase 0 — repository and contracts (this milestone)

- Preserve Project 1 history at baseline commit `2fc33bd29a5e5bde237c31333245bde2f1f89555`.
- Create the independent private Project 2 repository.
- Agree on architecture, evidence contracts, ownership, and evaluation responsibilities.
- Update `AGENTS.md` so the former multi-agent prohibition does not carry forward.

**Gate:** teammates can implement their modules from the written contracts without
editing one another's primary files.

### Phase 1 — fixed-fixture vertical slice

- Add shared schemas and deterministic feasibility/blocker evaluator.
- Add a common researcher runner with role-scoped prompts/tools and fresh contexts.
- Implement Lead fan-out, result collection, one follow-up decision, and Writer handoff.
- Exercise fixed evidence where round 1 has no solution and round 2 adds decisive data.
- Preserve `/chat` compatibility and add `agent`/`round` trace metadata.

**Gate:** an integration test proves initial failure → justified follow-up → new evidence
→ supported final diagnosis, without network calls.

**Current checkpoint (2026-11-11):**

- [x] Strict shared contract models and stable-ID validation.
- [x] Synthetic round-1 failure, FollowUpDecision, round-2 evidence, and expected outcome.
- [x] Contract and fixture-story tests, including citation and secret-safety checks.
- [x] Deterministic feasibility evaluator that computes the expected outcome and every
  supported blocker without model arithmetic.
- [x] Fresh-context concurrent Researcher runner with role-scoped tools, bounded turns,
  per-task timeout, deterministic ordering, and partial-failure conversion.
- [x] Lead execution over the fixture bundle, including one dependency-aware Cafe →
  exact-address Transit follow-up and deterministic feasibility handoff.
- [x] Evidence-only Writer handoff with inline fact/source/missing/derived references,
  provisional-hours qualification, and unsupported-citation rejection.
- [x] Fixed-data `/chat` service/trace integration with preserved response keys and
  `agent`/`round` metadata; live adapter injection remains Phase 2 integration.
- [x] Deterministic partial-intake clarification and immutable ResearchBrief construction
  from Project 1 resolver/candidate outputs.
- [x] Application bridge reuses the real Project 1 location resolver and candidate
  generator, traces both calls, and stops on unresolved/provider/validation failures.
- [x] Quote-validated natural-language extraction over multi-turn user messages, with
  no tools, explicit-offset enforcement, and deterministic model/auth failure fallback.
- [x] Single role dispatcher/service factory plus bounded MTA, Transit, and Cafe tasks,
  composed in the public Cloud Run service.

The current tests prove the data story, contract boundaries, deterministic feasibility
decision, concurrent isolated Researcher execution, and the bounded Lead/follow-up
loop, citation-audited Writer output, compatible `/chat` trace integration, and quote-
validated natural-language brief intake. They do not yet prove the live Routes/Places
provider adapters.

### Phase 2 — real data adapters

- Load and normalize MTA station data with provenance and a reproducible refresh path.
- Adapt Project 1 Routes calls for per-person limits and exact cafe destinations.
- Adapt Project 1 Places/hours calls to emit normalized facts, sources, and gaps.
- Bound concurrency, provider calls, timeouts, and follow-up candidate count.

**Gate:** recorded-provider tests pass; partial failures are explicit and API secrets
never enter prompts, traces, or git.

**Current adapter checkpoint:** MTA field parsing, bounded fetch, stable station IDs,
near-duplicate removal, three-candidate selection, provenance, and fixture tests are
implemented. Routes and Places Researcher adapters remain teammate work; the live MTA
startup cache and one opt-in smoke test remain integration work.

### Phase 3 — Writer, citations, and UI

- Generate a concise comparison, recommendation, blocker diagnosis, and unknown list.
- Validate that every factual sentence maps to fact/source IDs.
- Show round, agent, source, missing evidence, and exact-address verification status.
- Keep the interface usable for a grader and explain what the agent explores.

**Gate:** citation and UI tests reject unsupported claims and expose the complete trace.

### Phase 4 — evaluation and hill climbing

- [x] Build 50 provenance-recorded synthetic gold contract cases; none may appear in
  prompts or few-shot examples. Continue adding owner-specific full-pipeline cases.
- [x] Add deterministic contract/constraint checks plus a strict reference/rubric
  judge boundary.
- Capture the three team-owned grading examples and same-model no-tools/no-system
  baselines.
- Record baseline score, at least two changes with new scores, and gains greater than
  the margin of error `±1/sqrt(n)`.

**Gate:** the documented eval command is reproducible from a clean checkout.

Current progress: the full-pipeline registry and all three owner traces are complete.
A separate 50-case contract corpus scores the actual hard-decision and intake functions
at 50/50 across five balanced slices. The reference/rubric judge and no-tools capture
code are implemented and tested. The production model is fixed as
`vertex_ai/gemini-3.5-flash-lite`; credentialed judge/baseline captures and the final
hill-climbing table still require an auditable offline credentialed run.

### Phase 5 — Cloud Run and submission

- [x] Connect the new repository to continuous deployment.
- [x] Raise the request timeout as needed, cap agent turns, and keep provider use bounded.
- [x] Replace the inherited Project 1 `deploy_url` in `submission.json` with the Project 2
  Cloud Run URL.
- [x] Make the service publicly callable without grader authentication.
- Keep the service live through grade release and submit the repository URL in
  CourseWorks after the remaining eval evidence is committed.

**Gate:** public URL works without grader setup and all repository submission fields are
current.

## First vertical-slice fixture

The fixture contains two initial areas, two expansion stations, three travelers with
different hard limits, and cafe/hour evidence. Initial cafes are closed or violate at
least one commute limit. Expansion supplies one plausible station, its cafe result, and
then exact-address Routes evidence. Lead's follow-up must name the unresolved predicate,
the selected candidate IDs, and the expected information gain. Writer must reach one of
these outcomes without changing constraints:

- `FEASIBLE`
- `COMMUTE_LIMIT_EXCEEDED`
- `CAFE_CONSTRAINT_FAILED`
- `EVIDENCE_INSUFFICIENT`

## Key risks and controls

| Risk | Control |
| --- | --- |
| Parallel contexts return incompatible prose | Require the shared structured result contract |
| Area-center ETA hides last-mile cost | Verify exact cafe addresses before final feasibility |
| Missing hours are treated as closed/open | Record a gap and classify evidence as insufficient |
| Lead loops or expands too broadly | One follow-up round, bounded candidate count, explicit reason |
| Model applies hard limits inconsistently | Deterministic evaluator owns all pass/fail decisions |
| Provider facts cannot be cited later | Normalize source records at collection time |
| External APIs make tests flaky or expensive | Fixed fixtures and recorded-provider tests before live smoke tests |

## Repository workflow

Use small branches and pull requests. Suggested first branches are
`ruochen/orchestration-schemas`, `andrew/transit-researcher`, and
`yulia/cafe-researcher-ui`. Shared-contract changes require review from the two affected
owners before merge.
