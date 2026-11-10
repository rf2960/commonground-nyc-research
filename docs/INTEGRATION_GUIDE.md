# Teammate integration guide

This is the shortest path for Andrew and Wenyu/Yulia to connect their adapters without
changing the shared orchestration contract. Read `AGENTS.md`, `EVIDENCE_CONTRACTS.md`,
your owner section in `TEAM_PLAN.md`, and your prompt in `AI_HANDOFF.md` first.

## Before editing

1. Accept the GitHub collaborator invitation for this repository.
2. Wait until Ruochen's stacked contract/orchestration PRs are merged to `main` in
   dependency order.
3. Clone or fetch this repository and create only your documented branch:
   `andrew/transit-researcher` or `yulia/cafe-researcher`.
4. Run `uv sync` and `uv run pytest -q` before making changes.

Do not copy Project 1 into another folder, create competing evidence models, or add a
second Google client. The existing request functions remain the provider boundary.

## Adapter callable contract

The shared runner invokes one asynchronous callable with exactly three inputs:

```python
async def execute(context, brief, task) -> ResearchResult | dict:
    ...
```

- `context.messages` is fresh for this task and must not be shared or cached.
- `context.allowed_tools` is the role's hard allowlist.
- `context.max_turns` is a hard bound, not a suggestion.
- `brief` and `task` are frozen Pydantic records.
- Return a validated `ResearchResult` or a JSON-compatible dict with the exact shape.
- Every requested entity/field must produce a cited Fact or MissingEvidence record.

The integration dispatcher is implemented in `commonground/research/dispatch.py`.
Teammates provide only their two role callables:

```python
from commonground.research import build_research_service

research_service = build_research_service(
    transit=run_transit_task,
    cafe=run_cafe_task,
)
```

The factory supplies Ruochen's MTA expansion task by default and keeps runner bounds in
one place. Teammate PRs should export their adapter functions and tests; they should not
write dispatch conditionals or assign the global service in `app.py` themselves.

## Andrew handoff

Consume `ResearchTask.candidate_ids`, the ordered travelers and arrival time in the
brief, and Cafe coordinates for exact-destination tasks. Emit duration/availability
facts or one gap for every traveler × destination pair. Preserve `destination_kind` as
`area_center` or `exact_cafe`. Never apply the commute limits in the adapter; the shared
evaluator owns pass/fail.

Your PR is integration-ready when both initial-area and exact-cafe fixture tasks return
valid ResearchResults and the full suite remains green.

## Wenyu/Yulia handoff

Consume area IDs/coordinates, meeting time, and active constraints. Emit cafe identity,
parent area, address, coordinates, rating, price, business status, and opening evidence
or explicit gaps. Future regular-hours evidence must set `provisional=true`. Do not
route to cafes or relax constraints in this adapter.

Your PR is integration-ready when success, missing-hours, duplicate-place, and partial-
provider fixtures return valid ResearchResults and the full suite remains green.

## `/chat` boundary

Project 1 requests remain unchanged. The fixed Project 2 boundary accepts:

```json
{
  "message": "Can expansion find a feasible cafe?",
  "session_id": "session-123",
  "mode": "research",
  "research_brief": {"...": "research-contract-v1 fields"}
}
```

The response still contains only `response`, `session_id`, and `tool_calls`. Project 2
trace entries add `agent` and `round` while preserving `name`, `args`, and string
`result`. Trace order is Lead brief, three round-1 Researchers, optional FollowUpDecision,
ordered round-2 tasks, deterministic feasibility, then Writer.

Until live adapters are wired, research mode explicitly says it is unavailable. Fixture
evidence may appear only in tests and must never be presented as a live API result.

Before a complete brief exists, clients may send `research_intake` instead. The partial
shape contains `meeting_time`, traveler IDs/origins/individual limits, and optional cafe
constraints. `/chat` returns a targeted clarification and performs no research. After
Project 1 resolves every origin and generates initial areas, Ruochen's dispatcher calls
`build_research_brief`; adapters must not construct briefs independently.

## Pull-request handoff checklist

- Changed files stay inside the documented owner boundary.
- Full command and result for `uv run pytest -q` are in the PR body.
- Fixture evidence and live smoke evidence are labeled separately.
- Provider errors are short and credential-free.
- Shared contract assumptions and any requested schema changes are explicit.
- Exact inputs needed from the other adapter are listed.
- No API key, `.env`, service-account file, or copied provider URL with credentials is
  committed or included in a trace.
