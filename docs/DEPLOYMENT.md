# Cloud Run deployment runbook

## Production service

| Setting | Value |
| --- | --- |
| GCP project | `commonground-nyc` |
| Service | `commonground-nyc-research` |
| Region | `us-east1` |
| Public URL | `https://commonground-nyc-research-1053619589756.us-east1.run.app` |
| Source | `rf2960/commonground-nyc-research`, branch regex `^main$` |
| Build | Cloud Build from root `Dockerfile` |
| Runtime service account | `commonground-runner@commonground-nyc.iam.gserviceaccount.com` |
| Request timeout | 300 seconds |
| Instance bounds | 0 minimum, 3 maximum |
| Container concurrency | 10 |

The Project 1 Cloud Run service and repository remain separate and unchanged.

## Runtime configuration

The service uses these non-secret environment variables:

```text
GOOGLE_CLOUD_PROJECT=commonground-nyc
GOOGLE_CLOUD_LOCATION=global
GEMINI_MODEL=vertex_ai/gemini-3.5-flash-lite
SESSION_TTL_SECONDS=7200
MAX_SESSIONS=500
RESEARCH_TASK_TIMEOUT_SECONDS=45
RESEARCH_MAX_TURNS=6
```

`GOOGLE_MAPS_API_KEY` is injected from Secret Manager secret
`google-maps-api-key`, version `latest`. The runtime service account has only the
secret-access permission needed to read that value; no service-account key file is
created or committed.

## Release verification

After every merge to `main`:

1. Confirm the Cloud Build trigger completes.
2. Confirm the latest Cloud Run revision is healthy and receives 100% of traffic.
3. Open `/health` and require `status: ok` and `research_ready: true`.
4. Send one bounded `/chat` research request and require:
   - HTTP 200;
   - unchanged `response`, `session_id`, and `tool_calls` keys;
   - Lead, three Researcher roles, and Writer in the trace;
   - round 2 only when Lead records a structured reason;
   - exact cafe Routes evidence before a hard commute conclusion; and
   - cited source/fact IDs or an explicit missing-evidence record.
5. Run `uv run pytest -q`, `uv run python -m evals.runner`, and
   `uv run python -m evals.contract_corpus` from a clean checkout.

The November 11, 2026 production smoke is summarized in
`evals/examples/ruochen/live_cloud_run_smoke.json`.

## Operations and safety

- Keep the service public and running through grade release.
- Do not paste or log API keys. Rotate the Secret Manager value without changing code.
- Preserve the one-follow-up policy, task timeout, turn cap, and maximum instance count
  before increasing provider traffic.
- A future-hours result is a regular-schedule estimate, not a holiday guarantee.
- If `/health` is healthy but research fails, inspect missing-evidence reason codes
  before changing IAM or API restrictions.
- If a revision cannot read the Maps secret, verify that the service still runs as the
  dedicated `commonground-runner` account rather than the default compute account.

