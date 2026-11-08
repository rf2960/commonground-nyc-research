# Project 2 assignment compliance

This is a living checklist. “Planned” means the design is documented but implementation
evidence does not exist yet. Change an item to “Complete” only with a code, test, README,
or deployment link.

## General agent requirements

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| Use data the model does not already know deeply | Planned | Routes, Places, and MTA station records; add captured source provenance |
| Access data through tools/API/files/search | Project 1 baseline + planned extension | Existing provider modules; add research adapters and MTA loader |
| Combine evidence into a supported claim | Planned | Evidence contract and deterministic feasibility result; add vertical-slice test |
| State when data cannot answer | Planned | `EVIDENCE_INSUFFICIENT` and MissingEvidence; add Writer test |
| Show work and preserve `/chat` shape | Project 1 baseline + planned extension | Existing response keys; add `agent` and `round` trace tests |
| Frontend explains purpose, audience, and use | Project 1 baseline; Project 2 update planned | Update result UI after vertical slice |
| Deploy to Google Cloud Run | Project 1 baseline only | Create Project 2 deployment and replace `submission.json` URL |

## Deep Research path

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| At least three agent shapes with different jobs | Designed | Lead, Researcher, Writer in `ARCHITECTURE.md` |
| Lead fans out several Researchers in one turn | Designed | Three initial Researchers; add concurrency test |
| Researchers run in parallel in fresh contexts | Designed | Runner contract; add context-isolation test |
| Lead loops back for more on a gap | Designed | One bounded FollowUpDecision; add two-round fixture test |
| Vague questions require clarification | Designed | ResearchBrief validation; add clarification tests |
| Output is accurately cited | Designed | Fact/source IDs and Writer rules; add citation validator tests |

## Evaluation requirements

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| At least 50 gold/silver samples with provenance | Planned | Coverage table in `EVALUATION_PLAN.md`; build case registry |
| Eval cases not reused as few-shot prompt examples | Policy set | Add prompt/corpus separation check |
| At least two scorer types | Planned | Deterministic checks plus rubric/reference judge |
| Documented command to run evals | Planned | Choose framework and commit runnable command |
| README hill-climbing log with baseline and 2+ changes | Planned | Add scores after eval harness exists |
| Identify gains larger than `±1/sqrt(n)` | Planned | Compute in final hill-climbing table |

## README and sample-query requirements

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| Describe project and target user | Complete | Root README research question and workflow |
| Explain data origin and how it is loaded | Designed | README sources; add exact endpoints/cache/refresh after adapters |
| Three sample queries with expected answers and source | Designed | Owner cases in `EVALUATION_PLAN.md`; capture actual outputs later |
| Same-model answer with no tools and no system prompt | Planned | Capture per owner after runnable build exists |

## Repository and deployment requirements

| Requirement | Status | Evidence / next proof |
| --- | --- | --- |
| Root `app.py`, `pyproject.toml`, `uv.lock` | Complete | Preserved from Project 1 |
| Root `README.md` and valid `submission.json` | Complete for planning | `path` is `research`; replace inherited deploy URL before submission |
| `submission.json` contains every UNI | Complete | `rf2960`, `wd2422`, `yc4745` |
| GitHub repository submitted | Repository created | Public repo; submit URL when ready |
| At least one data source per team member | Designed | Ruochen/MTA, Andrew/Routes, Wenyu/Places |
| Data ships with deploy or loads from GCS/startup | Planned | Decide after MTA cache size and refresh design |
| Request may take up to 5 minutes; cap max turns | Designed | Operational bounds; configure/test Cloud Run |
| Keep service live until grades released | Planned | Operational checklist for final deployment |

## Final pre-submission blockers

- Project 2 multi-agent code is not implemented yet.
- The current `deploy_url` still points to the inherited Project 1 service.
- The 50+ case eval corpus, scorer runs, hill-climbing log, and actual/baseline sample
  outputs do not exist yet.
- The Project 2 frontend and Cloud Run deployment do not exist yet.

These are expected at the planning milestone; none should be described as complete in a
submission until the linked evidence exists.
