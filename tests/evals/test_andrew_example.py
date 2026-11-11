from pathlib import Path

from evals.runner import evaluate_case, load_case


ROOT = Path(__file__).resolve().parents[2]


def test_andrew_exact_cafe_case_runs_full_pipeline():
    result = evaluate_case(
        load_case(ROOT / "evals/cases/andrew_exact_cafe_limit.json")
    )

    assert result["passed"] is True
    assert result["deterministic_score"] == 1.0
    assert result["actual"]["recommended_cafe_id"] is None
    assert result["actual"]["feasibility_statuses"] == {
        "cafe:gplaces:andrew-leading-cafe": "COMMUTE_LIMIT_EXCEEDED"
    }
    feasibility_event = next(
        event
        for event in result["actual"]["tool_calls"]
        if event["name"] == "evaluate_feasibility"
    )
    assert '"actual_minutes":34.0' in feasibility_event["result"]
    assert '"limit_minutes":30.0' in feasibility_event["result"]
