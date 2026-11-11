# Teammate integration guide

This is the shortest path for Andrew and Wenyu/Yulia to connect their adapters without
changing the shared orchestration contract. Read `AGENTS.md`, `EVIDENCE_CONTRACTS.md`,
your owner section in `TEAM_PLAN.md`, and your prompt in `AI_HANDOFF.md` first.

## Before editing

1. Accept the GitHub collaborator invitation for this repository.
2. Fetch and fast-forward from latest `main`; Ruochen's required contracts and
   orchestration are already merged, so no further wait is required.
3. Create or update only your documented branch:
   `andrew/transit-researcher` or `yulia/cafe-researcher`.
4. Run `uv sync`, `uv run pytest -q`, `uv run python -m evals.runner`, and
   `uv run python -m evals.contract_corpus` before making changes.

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
- `context.dependency_results` contains independent, deep-copied structured prior
  results for round-2 destinations. It contains no other Researcher's messages. Read
  expansion station coordinates from these records for Cafe tasks and exact venue
  coordinates from Cafe records for Transit tasks. A dependency ID alone is not the
  coordinate payload. Never use cross-session global caches to reconstruct it.
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

The Cafe callable is now exported as `commonground.research.run_cafe_task`. It uses
the existing Places `_request_area` boundary and `opening_status`; there is no second
Google HTTP client. At most six areas and three concurrent requests are allowed,
each with the inherited 15-second timeout and ten-record/800-meter search bound.
An empty response means this bounded request returned no cafe, not that no feasible
venue exists anywhere in NYC. There are no automatic retries.

Each cafe has one canonical `parent_candidate_id` Fact (lexically first stable area
ID). Every cafe Fact also carries all matched IDs in `valid_for.parent_candidate_ids`.
This additive metadata preserves deduplication across areas without creating
conflicting singular parent facts. Missing values have no value-bearing Fact and do
have a field-specific MissingEvidence record, as required by the frozen v1 model.
Transit consumes the cafe ID plus `coordinates.value={lat,lng}` (and address when
present); it must not route to the parent area's center instead.

The provider collection keeps low-rated, over-budget, and incomplete cafe records as
evidence. This does not relax user constraints: Lead and feasibility still apply the
unchanged brief. Known failing cafes are never upgraded to recommendations. When only
hours are unknown, Lead may use its one exact-routing follow-up and the final status
remains `EVIDENCE_INSUFFICIENT` with the original hours gap.

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

Both live teammate adapters are now wired through the production dispatcher. A complete
validated brief can run Transit, Cafe, and MTA research; missing credentials or provider
failures become explicit gaps rather than fixture results. Fixture evidence may appear
only in tests and must never be presented as a live API result.

Before a complete brief exists, clients may send `research_intake` instead. The partial
shape contains `meeting_time`, traveler IDs/origins/individual limits, and optional cafe
constraints. `/chat` returns a targeted clarification and performs no research. After
Project 1 resolves every origin and generates initial areas, Ruochen's dispatcher calls
`prepare_research_brief`, which invokes both inherited boundaries and then calls the
validated builder. Adapters must not resolve user text or construct briefs independently.

## Pull-request handoff checklist

- Changed files stay inside the documented owner boundary.
- Full command and result for `uv run pytest -q` are in the PR body.
- Both eval commands pass; GitHub Actions enforces all three gates on team branches.
- Fixture evidence and live smoke evidence are labeled separately.
- Provider errors are short and credential-free.
- Shared contract assumptions and any requested schema changes are explicit.
- Exact inputs needed from the other adapter are listed.
- No API key, `.env`, service-account file, or copied provider URL with credentials is
  committed or included in a trace.
