import json
from pathlib import Path

import pytest

from evals.runner import evaluate_case, load_case, write_capture


REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_PATH = REPO_ROOT / "evals" / "cases" / "ruochen_expansion_success.json"


def test_ruochen_case_runs_real_pipeline_and_passes_every_check():
    result = evaluate_case(load_case(CASE_PATH))

    assert result["passed"] is True
    assert result["deterministic_score"] == 1.0
    assert all(check["passed"] for check in result["checks"])
    assert result["actual"]["recommended_cafe_id"] == (
        "cafe:gplaces:fixture-expansion-cafe"
    )
    assert {event["agent"] for event in result["actual"]["tool_calls"]} == {
        "lead",
        "transit_researcher",
        "cafe_researcher",
        "expansion_researcher",
        "writer",
    }


def test_case_loader_requires_provenance_paths(tmp_path):
    malformed = tmp_path / "case.json"
    malformed.write_text(
        json.dumps(
            {
                "case_id": "bad",
                "owner": "ruochen",
                "provenance": {},
                "question": "question",
                "fixtures": {},
                "expected": {},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="provenance"):
        load_case(malformed)


def test_capture_writer_records_timestamp_without_overwriting_score(tmp_path):
    result = evaluate_case(load_case(CASE_PATH))
    path = write_capture(result, tmp_path / "actual.json")
    capture = json.loads(path.read_text(encoding="utf-8"))

    assert capture["passed"] is True
    assert capture["deterministic_score"] == 1.0
    assert capture["captured_at"].endswith("+00:00")
    assert capture["build"]["kind"] == "fixed-data vertical slice"
