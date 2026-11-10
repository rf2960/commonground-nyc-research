# Evaluation and grading-example plan

## Required corpus and scorers

Before submission, create at least 50 gold or silver cases and record where every case
came from. No evaluation case may also appear in an agent prompt as a few-shot example.

The suite uses at least two scoring approaches:

1. **Deterministic checks:** schema validity, all requested pairs accounted for, hard
   limit math, blocker status, follow-up bound, source coverage, and citation integrity.
2. **Reference/rubric judge:** compare the Writer answer with golden claims and a rubric
   for recommendation correctness, calibrated uncertainty, useful comparison, and
   citation support.

Suggested coverage:

| Slice | Minimum cases |
| --- | ---: |
| Expansion finds a feasible option | 10 |
| Exact-address routing changes the answer | 10 |
| Commute limit remains the blocker | 8 |
| Cafe constraints remain the blocker | 8 |
| Missing/partial evidence must stay unknown | 8 |
| Clarification, malformed inputs, provider errors | 6 |

Record `case_id`, provenance, fixture/live-record version, question, expected structured
outcome, expected claims/source IDs, and scorer results.

## Hill-climbing log

The final README must report:

- baseline score;
- at least two implementation/prompt changes and the new score after each;
- which gains exceed the margin of error `±1/sqrt(n)`; and
- any regressions or slices still below target.

The chosen reproducible command is:

```bash
uv run python -m evals.runner
```

The first registered gold case executes the actual fixed-data application pipeline,
scores eight deterministic properties, writes a raw agent/trace capture, and exits
nonzero on regression. Expand the registry to 50+ cases as live adapters and owner
fixtures arrive. A rubric/reference judge remains required before submission; do not
mislabel the deterministic golden checks as the second scorer.

## Three owner-specific grading examples

Each owner fills all four artifacts: expected answer, sources, actual agent output, and
the same model's output with no tools and no system prompt. Store raw captures under a
future `evals/examples/<owner>/` directory and summarize them in the final README.

### Example 1 — Ruochen: expansion succeeds

**Question.** Given three clarified origins, arrival time, individual limits, and active
cafe filters, initial areas have no feasible cafe. Can a bounded expansion find one, and
what evidence changed the answer?

**Expected answer.** The initial search is infeasible for named, cited reasons. Lead
selects a small MTA-backed expansion with an explicit follow-up reason. Round 2 supplies
cafe and exact-address transit evidence, and deterministic checks mark one cafe
`FEASIBLE`. The answer distinguishes initial failure from the new evidence and lists any
remaining provisional hours caveat.

**Required sources.** MTA dataset `39hk-dx4f` station record, Google Places cafe record,
Google Routes exact-destination request, and deterministic rule/version record.

**Owner deliverables.** Golden structured bundle, actual Writer response and trace,
no-tools/no-system baseline, deterministic score, rubric score, and a short comparison.

**Current capture status.** Golden bundle, actual response/trace, and deterministic
score are committed under `evals/`; the score is `1.0` (8/8 checks). The production
model is not frozen, so the no-tools baseline and rubric/reference-judge score remain
explicitly pending rather than hand-authored.

### Example 2 — Andrew: exact cafe invalidates center estimate

**Question.** An initial area-center ETA is within every limit and Places returns a
qualifying cafe. Does routing to the exact cafe address preserve feasibility?

**Expected answer.** Lead requests exact-address verification because center ETA cannot
support the final claim. Routes shows one named traveler above their limit, so the cafe
is `COMMUTE_LIMIT_EXCEEDED`; the response reports actual versus limit and does not use
the center estimate as if it were door-to-door evidence.

**Required sources.** Google Routes area-center and exact-cafe requests, Google Places
place ID/address, traveler limit in the clarified brief, and deterministic rule/version.

**Owner deliverables.** Golden matrix and boundary calculation, actual Writer response
and trace, no-tools/no-system baseline, both scorer outputs, and a short comparison.

### Example 3 — Yulia: missing hours remains unknown

**Question.** Places returns a well-rated cafe with a valid route, but regular opening
periods for the future meeting time are absent. Is the cafe a supported recommendation?

**Expected answer.** The cafe may satisfy known transit/rating/price checks, but its
status is `EVIDENCE_INSUFFICIENT`, not open or closed. Writer cites the Places record,
names missing meeting-time hours, and recommends direct venue verification or an
alternative with complete evidence.

**Required sources.** Google Places record and request context, explicit missing-evidence
record, Google Routes exact-destination request, and deterministic rule/version.

**Owner deliverables.** Golden cafe/gap record, actual Writer response and trace,
no-tools/no-system baseline, both scorer outputs, and a short comparison.

## Capture template

Use this template for each final example:

```markdown
### Question

### Expected answer / structured outcome

### Sources and provenance

### Actual agent output

### Actual tool/agent/round trace

### Same-model output with no tools and no system prompt

### Deterministic score

### Rubric/reference score

### What the agent added or still missed
```

Do not fill “actual output” with a hand-authored prediction. Capture it from the tested
build and record the model/version and run date.
