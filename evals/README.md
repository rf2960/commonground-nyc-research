# Evaluation harness

Run every registered case from the repository root:

```bash
uv run python -m evals.runner
```

Run the 50-case deterministic contract corpus:

```bash
uv run python -m evals.contract_corpus
```

The corpus contains 10 cases in each of five slices: feasible boundaries, commute-limit
blockers, cafe-condition blockers, missing evidence, and clarification/intake. Every
case records its source fixture/code path, prohibits prompt reuse, and explicitly says
that its boundary mutations are synthetic rather than live provider observations. The
current result is 50/50. This complements the full-pipeline registry; it does not claim
that 50 live Google/MTA requests occurred.

Reproduce the hill-climbing experiment across three preserved implementation revisions:

```bash
uv run python -m evals.hill_climb
```

It evaluates the same 50 expectations at every stage, writes the raw report to
`evals/examples/hill_climb_results.json`, and removes its temporary detached worktrees.
The recorded progression is 0/50 → 40/50 → 50/50; gains of 0.80 and 0.20 both exceed
`1/sqrt(50) = 0.1414`.

Regenerate the raw capture for one owner case:

```bash
uv run python -m evals.runner \
  --case evals/cases/ruochen_expansion_success.json \
  --write-capture
```

The command executes the same `ResearchRunner` → `LeadOrchestrator` → deterministic
feasibility → `EvidenceWriter` path used by the application boundary. It does not score
a hand-written imitation of the answer. A nonzero exit code means at least one golden
check failed.

## Adding a case

1. Add `evals/cases/<owner>_<short_name>.json` with a unique `case_id`.
2. Record every source path and whether the case is gold or silver. Do not reuse an eval
   case in an agent prompt or few-shot example.
3. Point the case at a validated `ResearchBrief` and one or more `ResearchResult` fixture
   files. Synthetic records must say that they are synthetic; live captures must record
   provider request context and retrieval time.
4. Declare the golden cafe status, follow-up decision, required source IDs, and answer
   fragments. Never edit expected values merely to match a failing run.
5. Add a focused regression test and run both `uv run python -m evals.runner` and
   `uv run pytest -q`.
6. Store raw agent output under `evals/examples/<owner>/actual_agent.json`.

## Same-model baseline

Each owner must also capture the exact case question with the production Writer model,
with **no tools and no system prompt**. Record the exact model identifier, UTC timestamp,
raw output, and the two disabled conditions in
`evals/examples/<owner>/no_tools_baseline.json`.

`evals/baseline.py` enforces exactly one user message, no tools, and no system prompt,
and records model, timestamp, conditions, question, and raw output. The three final
live grader questions have authenticated captures in `evals/examples/`. The older
fixture-specific owner placeholder remains labeled `pending` and is not presented as a
live capture. The production model selection is frozen in `evals/model_manifest.json`;
only the question—not the evidence bundle—is allowed in a baseline call.

## Second scorer

`evals/rubric_judge.py` independently scores recommendation correctness, calibrated
uncertainty, comparison usefulness, and citation support on a strict 0–4 scale against
expected claims and an allowed source-ID set. Its schema rejects missing or out-of-range
scores. Tests use an injected completion; actual judge scores remain pending until the
production judge model and credentials are frozen.

## Team handoff

- Andrew owns the exact-cafe-vs-area-center case.
- Wenyu owns the missing-hours/evidence-insufficient case.
- Ruochen owns this harness, the expansion-success case, aggregate scoring, and the
  final hill-climbing table.

Provider-specific full-pipeline cases remain inside each Researcher owner's module;
aggregate discovery and scoring stay here so all owners receive the same semantics.

## Andrew Transit delivery

Run Andrew's synthetic exact-address grading case and refresh its fixed-data capture:

```bash
uv run python -m evals.runner \
  --case evals/cases/andrew_exact_cafe_limit.json \
  --write-capture
```

This case proves that area-center ETAs cannot substitute for exact-cafe Routes evidence:
the center estimates pass, while the exact address puts one traveler over their hard
limit. The committed capture is synthetic and does not claim a live Google result.

Run the bounded live Routes smoke only with explicit opt-in, a server-side
`GOOGLE_MAPS_API_KEY`, and a future timezone-aware arrival time:

```bash
uv run python -m evals.andrew_delivery \
  --live \
  --meeting-time 2026-11-18T14:00:00-05:00
```

The command makes at most one pure-transit matrix request to one area center, records
source/access time and pair-level results, and rejects output containing the key. Change
the example time when it is no longer in the future. A blocked or failed attempt exits
nonzero and never overwrites a previous successful capture.
