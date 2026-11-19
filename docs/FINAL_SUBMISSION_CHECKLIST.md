# Final submission checklist

This checklist maps the assignment page to inspectable repository or deployment
evidence. It records readiness; it does not claim that the CourseWorks submission
button has already been pressed.

## Required repository shape

- [x] Root `app.py`, `pyproject.toml`, `uv.lock`, `README.md`, and `submission.json`.
- [x] `submission.json` uses `path: research`, lists `rf2960`, `wd2422`, and `yc4745`,
  and points to the public Project 2 service.
- [x] Repository contains no API keys, service-account JSON, OAuth tokens, or `.env`.
- [x] Project 1 history is preserved; the Project 1 repository was not modified.

## Product and data

- [x] Public Cloud Run application and unauthenticated `/health` endpoint.
- [x] MTA Subway Stations, Google Places, and Google Routes provide one production
  data source per team member.
- [x] The UI states the problem and audience and displays research rounds, sources,
  explicit unknowns, exact-route values, and cafe evidence.
- [x] Cloud Run request timeout and agent turn/task limits stay within the assignment
  bounds; the service must remain online through grade release.

## Deep Research path

- [x] Lead, Researcher, and Writer are distinct execution shapes.
- [x] Lead concurrently fans out Transit, Cafe, and Expansion Researchers in fresh
  contexts with role-scoped tools.
- [x] Lead can perform one evidence-driven follow-up after the initial gap.
- [x] Vague input is clarified before research starts.
- [x] Writer can only render validated facts, sources, feasibility records, and explicit
  missing evidence; invalid model output falls back safely.
- [x] `/chat` preserves `response`, `session_id`, and `tool_calls`; sub-agent calls add
  `agent` and `round`.

## Evaluation and README evidence

- [x] Fifty provenance-recorded gold contract cases; none are prompt examples.
- [x] Deterministic scorer: 50/50 on the final contract corpus.
- [x] Credentialed rubric judge: three live queries passed at 1.0 normalized score,
  with all four dimensions at 4/4 and no unsupported claims. See
  `evals/examples/live_rubric_scores.json`.
- [x] Hill climbing uses the same 50 expectations: 0/50 → 40/50 → 50/50. Both gains
  exceed `1/sqrt(50) = 0.1414`.
- [x] README includes three grader-ready questions, expected answer/source, actual
  deployed answer/trace, and same-model question-only baseline with no tools or system
  prompt.
- [x] Live Places, pure-transit Routes (`include_driving=false`), and deployed
  full-pipeline evidence are committed without credentials.
- [x] Desktop/mobile browser suite and Python CI are green on the final evidence PR.

## Last external actions

- [ ] Confirm the sign-up-sheet row includes `Deep Research`, the exact research
  question, and all three data sources.
- [ ] Record the final healthy Cloud Run revision produced from final `main`.
- [ ] Submit `https://github.com/rf2960/commonground-nyc-research` once in CourseWorks.
- [ ] Keep the service online until grades are released.

Suggested sign-up-sheet question:

> When initial NYC meeting areas contain no cafe that satisfies every traveler's
> transit limit and is expected open at the meeting time, can a bounded MTA-station
> expansion find a feasible option? If not, is the blocker commute time, cafe
> constraints, or missing evidence?

Suggested data-source entry:

> MTA Subway Stations (data.ny.gov dataset 39hk-dx4f); Google Routes API; Google Places
> API (New).
