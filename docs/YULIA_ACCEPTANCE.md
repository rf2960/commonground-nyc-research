# Yulia delivery and remaining runtime gates

## Delivered across PR #13 and PR #14

- Cafe Researcher async adapter, stable IDs and all parent search areas.
- Exact venue address/coordinates, rating, price, business status, provisional hours.
- Missing and conflicting evidence remains explicit; partial failures preserve results.
- Shared coordinate handoff fixes, deterministic validation, and Writer citation fixes.
- Missing-hours grading case, raw synthetic provider data, actual program capture,
  deterministic 8/8 score, and a provenance-recorded rubric reference.
- Cafe evidence UI with linked sources/gaps and separate exact-vs-center estimates.
- An executable desktop/mobile Chromium suite and GitHub Actions artifact capture.

The grading example and browser tests use synthetic data. A separate live Places smoke
has now passed in Google Cloud Shell; it is not a production-model or Routes run.

## Live Places smoke (at most one request)

Configure `GOOGLE_MAPS_API_KEY` in a trusted server/local environment using your normal
secret manager. Do not paste it into a chat, commit it, place it in a frontend file, or
put it on a command line. Enable Places API (New) and restrict the server key
appropriately. This command does not ask for or use a Routes API key separately.

From the repository root, supply a future meeting time with an explicit UTC offset:

```bash
uv sync
uv run python -m evals.yulia_delivery places-smoke --live \
  --meeting-time 2026-11-18T14:00:00-05:00
```

Replace the example date if it is no longer future. The brief's first area is Union
Square. It makes at most one existing Places request (800 meters, at most ten records,
15-second provider timeout), does not route travelers, validates citations and unknown
hours, and writes `evals/examples/yulia/live_places_smoke.json`.

Without the key, it exits 2 and records `MAPS_KEY_NOT_CONFIGURED`. A successful provider
response with incomplete fields can still pass the smoke checks when the adapter
correctly represents those gaps. An empty bounded search is not evidence of city-wide
absence. A later blocked/failed attempt will not overwrite an earlier successful file.

Verified live capture: `evals/examples/yulia/live_places_smoke.json`, recorded at
`2026-11-10T07:07:28.941671+00:00` in the user's authenticated Cloud Shell. The single
Union Square request returned ten unique cafes, 81 cited Facts, eleven Google Places
Sources, and no missing fields. All six smoke checks passed. All ten meeting-time
opening Facts are provisional estimates for `2026-11-18T14:00:00-05:00`; no venue
opening is guaranteed and no commute or final feasibility claim is made. The imported
capture validates against `ResearchResult` and contains no detected API key. This
success does not turn the separately synthetic missing-hours grading case into live
missing-hours evidence.

## Same-model baseline and rubric captures

The current actual-agent file is a deterministic fixed-data capture. It has no Writer
model identity. Do not edit its metadata to pretend that it is a model-backed run.

After the production research model is frozen, obtain an actual model-backed capture
for this exact owner case. It must record `case_id`, the exact `question`, and
`build={"kind":"model-backed research","model":"<exact production model ID>"}`,
with actual output at `actual.response`. Model-authentication credentials must be
configured in the runtime through the existing Vertex/GCP mechanism.

Copy `evals/examples/yulia/model_manifest.template.json` to a local manifest. Set the
real model ID, optional separate judge model, location, and `frozen=true` only after
production model selection. Then run:

```bash
uv run python -m evals.yulia_delivery model-eval \
  --manifest /path/to/frozen-model-manifest.json \
  --agent-capture /path/to/actual-model-agent-capture.json
```

This captures exactly one question-only/no-tools/no-system baseline using the same
model, then two rubric calls (agent answer and baseline) using the common reference and
source allowlist. It writes `model_evaluation.json`, `no_tools_baseline.json`, and
`rubric_scores.json`. It never fills the files with guessed scores or a hand-written
baseline. A fixture-only agent capture is rejected, even if model credentials exist.

The single example is not the team's 50-case hill-climbing experiment. Aggregate
baseline/change comparisons and ±1/sqrt(n) reporting still belong to team integration.

## UI checks

These files and commands are on `yulia/research-evidence-ui` (PR #14); PR #13 alone
contains the Cafe adapter and capture commands, not the frontend test package.

The renderer is tested at 1440×1000 and 390×844 with Chromium over an HTTP-served copy
of the production HTML. Only `/chat` is mocked with a labeled synthetic case. External
network requests are blocked in the browser tests; no paid API/model calls occur.

```bash
npm ci
npx playwright install chromium
npm run test:ui
```

The GitHub Actions `browser-ui` job runs the same four checks and uploads screenshots,
traces on failure, and the HTML report as `browser-evidence`. The CI suite checks exact
routes versus center estimates, missing hours, source links, no JavaScript errors, and
no horizontal page/card overflow at both widths. Deployment integration is a separate
team task; these tests do not claim that the live Project 2 service is deployed.

## Remaining model configuration barrier

The live Places capture is complete using the existing key in Cloud Shell. Its
credential is not included in the imported JSON or committed files. The assistant
runtime still has no GCP model authentication or frozen production model manifest.
The repository's Actions secret list was empty at the configuration check, and the
connected collaborator has write access but no repository-admin access. Actual
model-backed grading output, same-model baseline and rubric scores remain pending
those shared model inputs. No new project, billing account, credential or permission
grant was created.
