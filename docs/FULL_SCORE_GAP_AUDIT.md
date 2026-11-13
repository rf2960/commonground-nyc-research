# Full-score gap audit

This audit maps the November 2026 Project 2 assignment page to evidence in this
repository. A requirement is marked complete only when a grader can inspect a file,
test, raw capture, or public URL. It intentionally separates a working implementation
from evidence still needed for submission.

## Current rubric position

**Evidence-backed self-score: 22–23.5 / 25.** The production Writer is now explicitly
model-backed while the deterministic layer retains exclusive authority over facts,
citations, hard constraints, and unknowns. Lead and the three Researchers remain
bounded role-specific execution shapes around real tools rather than free-form model
loops. The assignment does not explicitly require every shape to invoke an LLM, but
this remaining interpretation risk is still disclosed rather than represented as
guaranteed full credit.

| Graded area | Working estimate | Current evidence | Full-score risk | Next proof |
| --- | ---: | --- | --- | --- |
| Basics (1) | 1.0 | Root `README.md`, `submission.json`, `app.py`, `pyproject.toml`, and `uv.lock`; valid `path=research` and all three UNIs | Low | Keep the deploy URL current after the final release |
| Functionality (9) | 7.5–8.5 | Public Cloud Run app, healthy `/health`, real two-round `/chat` smoke, 349 tests | Medium | Save all three final live queries, including clarification and unknown/failure behavior |
| Data (4) | 3.5–4.0 | MTA Stations, Google Places, and Google Routes adapters; normalized sources, facts, and gaps; live Places and full-service smokes | Low–medium | Preserve a bounded raw Routes smoke and document exact request/load policy for every source |
| Deep Research path (7) | 6.5–7.0 | Lead, three parallel fresh-context Researchers, one evidence-driven follow-up, model-backed evidence-locked Writer, clarification, and citation validation | Low–medium | Save a production trace showing `writer_mode=model-backed-validated` plus fan-out/follow-up |
| Creativity (4) | 3.5–4.0 | Expansion after shortlist failure, blocker diagnosis, exact-address correction, evidence UI, and explicit unknowns | Low–medium | Make initial → follow-up → final information gain visually immediate in every result |

The public application is functional and demonstrates the core idea. The largest
remaining score risk is incomplete evaluation evidence required verbatim by the
assignment. Adding more providers or an unbounded third research round would not
address that risk.

## Mandatory gaps before submission

### Same-model comparisons for all three sample queries

The README now includes the expected result and sources, the actual public
agent answer from structured intake, and a summary and raw record of the
authenticated no-tools/no-system-prompt answer for each question.

The authenticated contrasts use `vertex_ai/gemini-3.5-flash-lite`, the same frozen
model configured for natural-language intake and the evidence-locked Writer. The raw
baseline records preserve the question-only, no-tools, no-system-prompt boundary.

The architecture mismatch is resolved in code: production uses the frozen model to
plan the ordering of immutable, already-cited Writer sections, validates the complete
report again, and falls back safely. The remaining proof is a post-deploy production
capture whose Writer trace says `writer_mode=model-backed-validated`; a fixture run or
fallback report must not be mislabeled as that capture.

### P0 — actual second-scorer captures

`evals/rubric_judge.py` implements a strict 0–4 rubric judge, but implementation tests
are not the assignment's requested evaluation result. Commit the credentialed judge
output for the agent and baseline for all three owner examples, including model ID,
timestamp, reference claims, allowed source IDs, and unsupported claims.

### P0 — 50-case hill-climbing log

The 50-case provenance-recorded contract corpus currently scores 50/50. The assignment
also asks for a README hill-climbing log containing a baseline, at least two changes,
each new score, and which gains exceed `±1/sqrt(n)`. For `n=50`, the comparison margin
is approximately `±0.1414`.

Do not manufacture earlier scores. Freeze one held-out corpus and run three real system
variants or preserved commits:

1. baseline;
2. change 1, with rationale and score; and
3. change 2, with rationale and score.

Record the exact commit/configuration for every row. A score gain is called material
only when it exceeds 0.1414 on the same 50 examples.

### P0 — final production evidence for the three grader queries

The README links actual public-service captures for all three queries with explicit
structured intake, including an MTA expansion and an opening-hours caveat.
After deploying the natural-language intake fix, repeat the same questions in
the public UI and confirm the brief retains the requested rating and price.
Fixture captures remain available for successful expansion and missing-hours
regression coverage.

### P0 — final submission action

After the evidence above and final Cloud Build pass:

- verify the public URL in a signed-out context;
- verify `submission.json` from `main`;
- keep the service live through grade release; and
- submit the GitHub repository URL in CourseWorks once for the group.

CourseWorks submission is an external final action and is not complete merely because
the repository is ready.

## High-value polish after the mandatory gaps

### P1 — grader-first result page

- Add a compact top summary showing `initial result → follow-up reason → new evidence →
  final status` before the longer evidence cards.
- Provide three one-click queries that match the README examples exactly.
- Keep unknowns and regular-hours caveats visible without expanding a low-level trace.
- Show provider failure as partial evidence, not as a generic app error.

### P1 — reproducible live-source captures

- Save one bounded pure-transit Routes smoke with arrival time, request count, and
  `include_driving=false`.
- Preserve the existing live Places smoke and public full-pipeline smoke.
- Never store the Maps key, OAuth token, service-account JSON, session identifier, or
  raw provider exception.

### P1 — deployment confidence

- Confirm the continuous-deployment trigger succeeds after the final documentation and
  evaluation commit, not only after the initial service creation.
- Repeat `/health`, one success query, and one explicit-unknown query.
- Check the mobile result page against the real deployed response, supplementing the
  existing synthetic browser tests.

## Honest readiness assessment

The core product, Deep Research mechanics, deployment, and deterministic evaluation are
strong. It is not yet a defensible full-score submission because the post-deploy plain-text retest, credentialed judge results, and real two-change
hill-climbing log are still missing. Those are evidence tasks, not cosmetic README edits. Completing
them should take priority over adding more provider features or another agent round.
