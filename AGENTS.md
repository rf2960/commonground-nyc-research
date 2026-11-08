# Repository instructions for coding agents

This repository is the Project 2 Deep Research continuation of CommonGround NYC. The
Project 1 instruction that prohibited multi-agent architecture no longer applies here.
Multi-agent orchestration is the core Project 2 scope, within the boundaries below.

- Keep `app.py`, `pyproject.toml`, `uv.lock`, `README.md`, and `submission.json` at the
  repository root; the grader expects them there.
- Never commit API keys, service-account JSON, `.env`, or generated credentials.
- Preserve the `/chat` response keys: `response`, `session_id`, and `tool_calls`.
  Preserve each call's `name`, `args`, and `result`; add `agent` and `round` for
  sub-agent calls.
- Read `docs/EVIDENCE_CONTRACTS.md` before changing agent messages, tool arguments,
  result shapes, candidate IDs, source records, or gap records.
- Read `docs/ARCHITECTURE.md` before changing orchestration or follow-up policy.
- The first MVP has five instances across three role shapes: one Lead, three parallel
  Researchers in fresh contexts, and one Writer. It allows one initial research round
  plus at most one targeted follow-up round.
- Keep hard commute-limit and cafe-feasibility decisions in deterministic code. Models
  may plan and explain but must not invent arithmetic or silently relax constraints.
- A claim in Writer output must reference normalized fact/source IDs. Missing or stale
  evidence must be reported as a gap, not converted to a negative fact.
- Provider/API code stays behind small functions and returns model-readable JSON
  errors at the tool boundary. Reuse the Project 1 Routes, Places, location, hours, and
  scoring modules instead of duplicating them.
- Researchers may share a runner implementation, but each instance receives an
  independent message context and a role-scoped tool allowlist.
- Add or update tests for every contract, scoring rule, follow-up trigger, and edge
  case. The first implementation test must cover initial failure, justified follow-up,
  and new second-round evidence with fixed data.
- Run `uv run pytest` before opening a pull request.
- Do not add reservations, payments, user accounts, or an unbounded autonomous loop.
  Retrieval is limited to the three documented Project 2 sources unless the plan and
  evidence contract are updated first.

