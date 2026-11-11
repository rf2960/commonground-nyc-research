from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from commonground.research.models import ResearchBrief
from commonground.research.transit_agent import (
    TransitPairObservation,
    build_transit_result,
)
from evals.andrew_delivery import capture_routes_smoke, write_record


ROOT = Path(__file__).resolve().parents[2]


def brief():
    raw = json.loads(
        (ROOT / "tests/research/fixtures/andrew_research_brief.json").read_text()
    )
    raw["meeting_time"] = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    return ResearchBrief.model_validate(raw)


def test_routes_capture_requires_opt_in_and_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)

    async def forbidden(*args):
        raise AssertionError("Must not call a paid provider without configuration")

    assert capture_routes_smoke(brief(), executor=forbidden)["reason_code"] == (
        "LIVE_OPT_IN_REQUIRED"
    )
    assert capture_routes_smoke(
        brief(), live=True, executor=forbidden
    )["reason_code"] == "MAPS_KEY_NOT_CONFIGURED"


def test_routes_capture_is_bounded_cited_and_credential_free(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fixture-only-secret")
    calls = []

    async def execute(context, b, task):
        calls.append(task)
        now = datetime.now(timezone.utc)
        observations = tuple(
            TransitPairObservation(
                candidate_id=task.candidate_ids[0],
                traveler_id=traveler.traveler_id,
                destination_kind="area_center",
                observed_at=now,
                duration_minutes=20,
                route_available=True,
            )
            for traveler in b.travelers
        )
        return build_transit_result(
            b,
            task,
            observations,
            source_accessed_at=now,
            request_summary={
                "origin_count": len(b.travelers),
                "destination_count": 1,
                "candidate_ids": list(task.candidate_ids),
                "destination_kinds": ["area_center"],
                "arrival_time": b.meeting_time.isoformat(),
                "provider_arrival_time": b.meeting_time.isoformat(),
                "provider_reported_partial": False,
                "travel_mode": "TRANSIT",
                "include_driving": False,
            },
        )

    record = capture_routes_smoke(brief(), live=True, executor=execute)

    assert record["status"] == "passed"
    assert len(calls) == 1 and len(calls[0].candidate_ids) == 1
    assert all(record["checks"].values())
    assert record["scope"]["max_matrix_requests"] == 1
    assert record["scope"]["include_driving"] is False
    assert "fixture-only-secret" not in json.dumps(record)


def test_routes_raw_provider_exceptions_are_never_recorded(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fixture-only-secret")

    async def fail(*args):
        raise RuntimeError("fixture-only-secret")

    record = capture_routes_smoke(brief(), live=True, executor=fail)
    assert record["status"] == "failed"
    assert record["reason_code"] == "SAFE_PROVIDER_FAILURE"
    assert "fixture-only-secret" not in json.dumps(record)


def test_failed_attempt_does_not_destroy_successful_capture(tmp_path):
    path = tmp_path / "capture.json"
    write_record(path, {"status": "passed", "value": "saved evidence"})
    write_record(path, {"status": "blocked", "reason_code": "MISSING_CONFIG"})
    assert json.loads(path.read_text())["status"] == "passed"
    assert json.loads(
        (tmp_path / "capture.latest_attempt.json").read_text()
    )["status"] == "blocked"
