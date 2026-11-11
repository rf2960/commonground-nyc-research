"""Opt-in, redacted live Routes smoke capture for Andrew's Transit delivery.

The command makes at most one inherited Google Routes matrix request and never
fabricates a successful live result when configuration is missing. Unit tests inject
the paid boundary; a real capture requires both ``--live`` and a server-side key.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from commonground.research.models import ResearchBrief, ResearchTask
from commonground.research.runner import ResearchContext
from commonground.research.transit_agent import run_transit_task


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRIEF = ROOT / "tests/research/fixtures/andrew_research_brief.json"


def _record(status: str, **values: Any) -> dict[str, Any]:
    return {
        "schema_version": "andrew-routes-smoke-v1",
        "kind": "routes_smoke",
        "status": status,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        **values,
    }


def _same_instant(raw: Any, expected: datetime) -> bool:
    if not isinstance(raw, str):
        return False
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None and parsed == expected


def capture_routes_smoke(
    brief: ResearchBrief,
    *,
    live: bool = False,
    executor=run_transit_task,
) -> dict[str, Any]:
    """Make one pure-transit matrix request to one area center."""

    if not live:
        return _record(
            "blocked",
            reason_code="LIVE_OPT_IN_REQUIRED",
            live_provider_observation=False,
        )
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        return _record(
            "blocked",
            reason_code="MAPS_KEY_NOT_CONFIGURED",
            live_provider_observation=False,
        )
    if brief.meeting_time <= datetime.now(timezone.utc):
        return _record(
            "blocked",
            reason_code="FUTURE_MEETING_TIME_REQUIRED",
            live_provider_observation=False,
        )

    target = brief.initial_candidates[0]
    task = ResearchTask(
        task_id=f"task:{brief.session_id}:r1:transit:1",
        research_id=brief.research_id,
        round=1,
        agent="transit_researcher",
        objective="One-area live Routes smoke using pure transit only.",
        candidate_ids=(target.candidate_id,),
        allowed_tools=("get_transit_matrix",),
    )
    context = ResearchContext(
        messages=[],
        allowed_tools=task.allowed_tools,
        max_turns=1,
    )
    try:
        result = asyncio.run(executor(context, brief, task))
        serialized = result.model_dump_json()
        if key in serialized:
            return _record(
                "failed",
                reason_code="OUTPUT_REDACTION_FAILED",
                live_provider_observation=False,
            )

        source_ids = {source.source_id for source in result.sources}
        duration_pairs = {
            (fact.candidate_id, fact.subject_id)
            for fact in result.facts
            if fact.predicate == "transit_duration_minutes"
        }
        missing_pairs = {
            (gap.candidate_id, gap.subject_id)
            for gap in result.missing
            if gap.field == "transit_duration_minutes"
        }
        expected_pairs = {
            (target.candidate_id, traveler.traveler_id)
            for traveler in brief.travelers
        }
        checks = {
            "one_matrix_one_destination": result.candidate_ids_considered
            == (target.candidate_id,),
            "provider_source_received": bool(result.sources)
            and all(source.provider == "google_routes" for source in result.sources),
            "all_pairs_accounted_for": duration_pairs | missing_pairs == expected_pairs,
            "all_facts_cited": all(
                set(fact.source_ids) <= source_ids for fact in result.facts
            ),
            "arrival_time_preserved": all(
                _same_instant(
                    fact.valid_for.get("arrival_time"),
                    brief.meeting_time,
                )
                for fact in result.facts
                if fact.predicate == "transit_duration_minutes"
            ),
            "pure_transit_only": all(
                source.request_summary.get("travel_mode") == "TRANSIT"
                and source.request_summary.get("include_driving") is False
                for source in result.sources
            ),
        }
        passed = all(checks.values())
        return _record(
            "passed" if passed else "failed",
            live_provider_observation=bool(result.sources),
            checks=checks,
            scope={
                "candidate_id": target.candidate_id,
                "origin_count": len(brief.travelers),
                "destination_count": 1,
                "max_matrix_requests": 1,
                "arrival_time": brief.meeting_time.isoformat(),
                "include_driving": False,
            },
            result=result.model_dump(mode="json"),
        )
    except Exception:
        return _record(
            "failed",
            reason_code="SAFE_PROVIDER_FAILURE",
            live_provider_observation=False,
        )


def write_record(path: Path, record: dict[str, Any]) -> None:
    """Keep successful evidence intact if a later attempt is blocked or fails."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous.get("status") == "passed" and record.get("status") != "passed":
            path = path.with_name(path.stem + ".latest_attempt" + path.suffix)
    path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--meeting-time",
        required=True,
        help="Future ISO time with an explicit UTC offset.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evals/examples/andrew/live_routes_smoke.json",
    )
    args = parser.parse_args()
    try:
        raw = json.loads(DEFAULT_BRIEF.read_text(encoding="utf-8"))
        raw["question"] = "One-area live Routes smoke; collect pure-transit evidence only."
        raw["meeting_time"] = args.meeting_time
        brief = ResearchBrief.model_validate(raw)
        record = capture_routes_smoke(brief, live=args.live)
    except Exception:
        record = _record(
            "blocked",
            reason_code="INVALID_INPUT_OR_CAPTURE",
            live_provider_observation=False,
        )
    write_record(args.output, record)
    print(
        json.dumps(
            {
                key: record[key]
                for key in ("kind", "status", "reason_code", "checks")
                if key in record
            }
        )
    )
    return 0 if record["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
