import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import requests

from commonground.research import (
    DATASET_ID,
    LeadOrchestrator,
    MTADataError,
    ResearchBrief,
    build_expansion_result,
    fetch_mta_stations,
    parse_mta_stations,
    select_expansion_stations,
)


FIXTURES = Path(__file__).parent / "fixtures"
ACCESSED_AT = datetime(2026, 11, 9, 18, 0, tzinfo=timezone.utc)


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def brief() -> ResearchBrief:
    return ResearchBrief.model_validate(fixture("research_brief.json"))


def stations():
    return parse_mta_stations(fixture("mta_stations.json"))


def expansion_task():
    return LeadOrchestrator.build_initial_tasks(brief())[2]


def test_current_mta_schema_is_normalized_and_duplicate_ids_are_stable():
    records = stations()

    assert len(records) == 6
    queensboro = next(record for record in records if record.station_id == "200")
    assert queensboro.gtfs_stop_id == "R09"
    assert queensboro.routes == ("N", "W", "7")
    assert queensboro.candidate_id == "area:mta:200"
    assert all(record.station_id != "bad/id" for record in records)


def test_selection_excludes_initial_duplicates_and_is_bounded_and_deterministic():
    first = select_expansion_stations(brief(), stations())
    second = select_expansion_stations(brief(), reversed(stations()))

    assert first == second
    assert 1 <= len(first) <= 3
    assert {station.station_id for station in first}.isdisjoint({"100", "101"})
    assert len({station.station_id for station in first}) == len(first)


def test_expansion_result_emits_four_cited_facts_per_selected_station():
    result = build_expansion_result(
        expansion_task(),
        brief(),
        stations(),
        accessed_at=ACCESSED_AT,
    )

    assert result.status == "complete"
    assert 1 <= len(result.candidate_ids_considered) <= 3
    assert len(result.facts) == 4 * len(result.candidate_ids_considered)
    assert len(result.sources) == len(result.candidate_ids_considered)
    assert {fact.predicate for fact in result.facts} == {
        "station_name",
        "coordinates",
        "routes_or_lines",
        "expansion_selection_reason",
    }
    source_ids = {source.source_id for source in result.sources}
    assert all(set(fact.source_ids).issubset(source_ids) for fact in result.facts)
    assert all(
        source.request_summary["dataset_id"] == DATASET_ID
        for source in result.sources
    )
    assert all(source.accessed_at == ACCESSED_AT for source in result.sources)


def test_fetch_uses_official_bounded_endpoint_and_preserves_retrieval_time():
    calls = []

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return fixture("mta_stations.json")

    def getter(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    records, retrieved_at = fetch_mta_stations(
        getter=getter,
        now=lambda: ACCESSED_AT,
    )

    assert records == stations()
    assert retrieved_at == ACCESSED_AT
    assert calls[0][0] == "https://data.ny.gov/resource/39hk-dx4f.json"
    assert calls[0][1]["params"] == {"$limit": 5000}
    assert calls[0][1]["timeout"] == 15


@pytest.mark.parametrize(
    ("getter", "message"),
    [
        (
            lambda *args, **kwargs: (_ for _ in ()).throw(requests.Timeout()),
            "timed out",
        ),
        (
            lambda *args, **kwargs: type(
                "BadResponse",
                (),
                {"status_code": 503, "json": lambda self: {}},
            )(),
            "HTTP 503",
        ),
    ],
)
def test_fetch_errors_are_short_and_safe_for_the_agent_boundary(getter, message):
    with pytest.raises(MTADataError, match=message):
        fetch_mta_stations(getter=getter, now=lambda: ACCESSED_AT)


def test_parser_rejects_a_response_without_any_valid_station():
    with pytest.raises(MTADataError, match="no valid stations"):
        parse_mta_stations([{"station_id": "broken"}])


def test_adapter_rejects_a_naive_retrieval_timestamp():
    with pytest.raises(ValueError, match="time zone"):
        build_expansion_result(
            expansion_task(),
            brief(),
            stations(),
            accessed_at=datetime(2026, 11, 9, 18, 0),
        )
