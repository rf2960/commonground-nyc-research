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
and records model, timestamp, conditions, question, and raw output. The committed
Ruochen baseline file remains deliberately `pending`: no credentialed production-model
run has yet been performed, so it contains no fabricated answer. Freeze the production
model before capturing it. Only the question—not the evidence bundle—is allowed.

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
