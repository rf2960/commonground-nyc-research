# Project 2 assignment compliance

This is a living checklist. “Planned” means the design is documented but implementation
evidence does not exist yet. Change an item to “Complete” only with a code, test, README,
or deployment link.

## General agent requirements

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| Use data the model does not already know deeply | MTA adapter complete; Routes/Places pending | MTA records carry station-level provenance; add recorded teammate-provider evidence |
| Access data through tools/API/files/search | MTA + Project 1 bridge complete | Bounded Socrata loader plus traced location-resolver/candidate calls; add Routes/Places research adapters |
| Combine evidence into a supported claim | Complete in fixed-data slice | Lead executes two rounds, `feasibility-v1` decides constraints, and Writer renders the supported result with IDs |
| State when data cannot answer | Complete in fixed-data slice | Writer refuses recommendation on `EVIDENCE_INSUFFICIENT` and prints the MissingEvidence detail/next action |
| Show work and preserve `/chat` shape | Complete in fixed-data slice | Service test preserves the three response keys and validates ordered `agent`/`round` trace entries |
| Frontend explains purpose, audience, and use | Complete for fixed-data boundary | Project 2 copy, guided sample, and round-grouped Lead/Researcher/Writer evidence timeline are in `index.html` |
| Deploy to Google Cloud Run | Project 1 baseline only | Create Project 2 deployment and replace `submission.json` URL |

## Deep Research path

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| At least three agent shapes with different jobs | Designed | Lead, Researcher, Writer in `ARCHITECTURE.md` |
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
| At least two scorer types | Implemented; live judge run pending | Deterministic checks plus strict reference/rubric judge in `evals/rubric_judge.py` |
| Documented command to run evals | Complete | `uv run python -m evals.runner` and `uv run python -m evals.contract_corpus` |
| README hill-climbing log with baseline and 2+ changes | Pending frozen-model runs | Harness, 50-case score, judge schema, and no-tools capture boundary exist |
| Identify gains larger than `±1/sqrt(n)` | Planned | Compute in final hill-climbing table |

## README and sample-query requirements

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| Describe project and target user | Complete | Root README research question and workflow |
| Explain data origin and how it is loaded | MTA complete; Google adapters pending | `DATA_SOURCES.md` records endpoint, fields, bounds, provenance, and startup-cache plan |
| Three sample queries with expected answers and source | In progress | All three are designed; Ruochen golden case and raw actual capture are committed |
| Same-model answer with no tools and no system prompt | Capture code complete; run pending | `evals/baseline.py` enforces question-only/no-tools/no-system; capture after production model freeze |

## Repository and deployment requirements

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| Root `app.py`, `pyproject.toml`, `uv.lock` | Complete | Preserved from Project 1 |
| Root `README.md` and valid `submission.json` | Complete for planning | `path` is `research`; replace inherited deploy URL before submission |
| `submission.json` contains every UNI | Complete | `rf2960`, `wd2422`, `yc4745` |
| GitHub repository submitted | Repository created | Public repo; submit URL when ready |
| At least one data source per team member | Ruochen complete; teammates planned | MTA adapter/tests exist; Andrew owns Routes and Wenyu owns Places adapters |
| Data ships with deploy or loads from GCS/startup | Planned | Decide after MTA cache size and refresh design |
| Request may take up to 5 minutes; cap max turns | Runner bound complete; deployment planned | Runner enforces 1–12 turns and a positive per-task timeout; configure/test Cloud Run request limit later |
| Keep service live until grades released | Planned | Operational checklist for final deployment |

## Final pre-submission blockers

- Shared Project 2 contracts, fixed evidence fixtures, deterministic feasibility, the
  concurrent isolated Researcher runner, bounded Lead execution, and evidence-only
  Writer and fixed-data `/chat` trace are implemented; Routes/Places adapters and live
  service injection are not yet done.
- The current `deploy_url` still points to the inherited Project 1 service.
- Credentialed rubric-judge scores, same-model no-tools baselines, and the final
  hill-climbing table remain pending the frozen production model.
- Project 2 frontend changes exist; the new Cloud Run deployment does not yet.

These are expected at the planning milestone; none should be described as complete in a
submission until the linked evidence exists.
