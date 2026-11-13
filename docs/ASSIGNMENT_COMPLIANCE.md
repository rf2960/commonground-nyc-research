# Project 2 assignment compliance

This is a living checklist. “Planned” means the design is documented but implementation
evidence does not exist yet. Change an item to “Complete” only with a code, test, README,
or deployment link.

## General agent requirements

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| Use data the model does not already know deeply | Complete | Live Cloud Run smoke uses current Google Places and Routes results plus the MTA expansion task; the saved Places smoke separately records ten cafes, 81 facts, and eleven sources |
| Access data through tools/API/files/search | Complete | The deployed production dispatcher calls MTA Socrata, Google Places, and Google Routes through role-scoped adapters |
| Combine evidence into a supported claim | Complete | The public service completed two rounds, `feasibility-v1` applied hard constraints, and Writer returned cited recommendations and blockers |
| State when data cannot answer | Complete | Writer refuses recommendation on `EVIDENCE_INSUFFICIENT` and prints the MissingEvidence detail/next action |
| Show work and preserve `/chat` shape | Complete | Tests and the public smoke preserve `response`, `session_id`, and `tool_calls`; eleven live trace entries include `agent` and `round` |
| Frontend explains purpose, audience, and use | Complete | The deployed UI explains the research question and renders round-grouped Lead/Researcher/Writer evidence, venue cards, gaps, and citations |
| Deploy to Google Cloud Run | Complete | Public Project 2 URL is in `submission.json`; `/health` reports `status=ok` and `research_ready=true` |

## Deep Research path

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| At least three agent shapes with different jobs | Complete | Lead, Researcher, Writer are implemented and exercised by the full-pipeline eval |
| Lead fans out several Researchers in one turn | Complete in fixed-data slice | `LeadOrchestrator` creates all three tasks and `ResearchRunner.run_initial_round` executes them concurrently |
| Researchers run in parallel in fresh contexts | Complete at runner boundary | `test_runner.py` proves overlap, distinct contexts/message lists, role tool scopes, and deterministic output ordering |
| Lead loops back for more on a gap | Complete in fixed-data slice | Lead records one bounded FollowUpDecision, waits for Cafe coordinates, then dispatches exact-address Transit |
| Vague questions require clarification | Complete at natural-language boundary | Quote-validated extraction creates partial intake; missing travelers/origins/limits/timezone produce deterministic prompts before provider or Researcher dispatch |
| Output is accurately cited | Complete in fixed-data slice | `validate_writer_report` rejects unknown/mismatched references and verifies every cited ID appears in rendered text |

## Evaluation requirements

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| At least 50 gold/silver samples with provenance | Complete for contract corpus | `evals.contract_corpus` runs 50 provenance-recorded synthetic gold boundary cases across five slices; provider/full-pipeline cases continue to grow |
| Eval cases not reused as few-shot prompt examples | Enforced in corpus metadata | Every case records `prompt_reuse_prohibited=true`; no eval case is embedded in an agent prompt |
| At least two scorer types | Implemented; credentialed judge capture pending | Deterministic checks plus strict reference/rubric judge in `evals/rubric_judge.py` |
| Documented command to run evals | Complete | `uv run python -m evals.runner` and `uv run python -m evals.contract_corpus` |
| README hill-climbing log with baseline and 2+ changes | Complete | `evals.hill_climb` replays the same 50 held-out expectations against preserved commits `7b596c7`, `2bbad8b`, and `96989b0`; raw results and the README table are committed |
| Identify gains larger than `±1/sqrt(n)` | Complete | Gains of `+0.80` and `+0.20` both exceed `1/sqrt(50) = 0.1414`; the final score is 50/50 |

## README and sample-query requirements

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| Describe project and target user | Complete | Root README research question and workflow |
| Explain data origin and how it is loaded | MTA and Cafe documented; live Places capture complete | `DATA_SOURCES.md` and `YULIA_ACCEPTANCE.md` record provenance, request bounds and remaining model gates |
| Three sample queries with expected answers and source | Recorded | README includes three questions, expected results and sources, public-service captures with structured intake, and matching no-tools answers. Repeat the plain-text queries after deploying the intake fix |
| Same-model answer with no tools and no system prompt | Captured for all three live queries | The captured model is `vertex_ai/gemini-3.5-flash-lite`, used for intake. The final Writer renders the deterministic evidence record. The raw files are linked in the README |

## Repository and deployment requirements

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| Root `app.py`, `pyproject.toml`, `uv.lock` | Complete | Preserved from Project 1 |
| Root `README.md` and valid `submission.json` | Complete | `path` is `research`; all three UNIs and the public Project 2 deploy URL are current |
| `submission.json` contains every UNI | Complete | `rf2960`, `wd2422`, `yc4745` |
| GitHub repository submitted | Repository created | Public repo; submit URL when ready |
| At least one data source per team member | Complete at production-smoke boundary | Public smoke exercised MTA Expansion, Google Routes Transit, and Google Places Cafe roles; separate live Places capture remains committed |
| Data ships with deploy or loads from provider | Complete for API-backed design | No static dataset exceeds GitHub limits; MTA, Routes, and Places are bounded authoritative API requests with fixture copies for offline tests |
| Request may take up to 5 minutes; cap max turns | Complete | Cloud Run timeout is 300 seconds; Researcher tasks default to 45 seconds and six turns, clamped to 1–120 seconds and 1–12 turns |
| Keep service live until grades released | Operational commitment recorded | `docs/DEPLOYMENT.md` records the public service, continuous deployment, bounds, health checks, and keep-live requirement |

## Final pre-submission blockers

- Shared contracts, fixed evidence, the concurrent isolated runner, bounded Lead,
  evidence-only Writer, Cafe/Transit/Expansion adapters, live service injection,
  desktop/mobile UI checks, public Cloud Run release, and a live full-pipeline smoke are
  complete.
- Three credentialed no-tools answers and the reproducible hill-climbing report are
  committed. The public plain-text retest and credentialed rubric-judge scores remain
  pending.

Do not describe the remaining evaluation artifacts as complete until their raw outputs
and scores are committed. Deployment itself is complete and separately evidenced.
