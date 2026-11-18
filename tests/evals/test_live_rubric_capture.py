from __future__ import annotations

import json
from pathlib import Path

from evals.live_rubric_capture import REFERENCE_CLAIMS, capture_live_rubrics
from evals.rubric_judge import RubricJudgeResult


ROOT = Path(__file__).resolve().parents[2]


def test_live_rubric_capture_scores_all_frozen_questions() -> None:
    captures = json.loads(
        (ROOT / "evals/examples/live_grader_queries_plain_text.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((ROOT / "evals/model_manifest.json").read_text(encoding="utf-8"))
    calls: list[dict] = []

    def fake_judge(**kwargs) -> RubricJudgeResult:
        calls.append(kwargs)
        return RubricJudgeResult.model_validate(
            {
                "scores": {
                    "recommendation_correctness": 4,
                    "calibrated_uncertainty": 4,
                    "comparison_usefulness": 4,
                    "citation_support": 4,
                },
                "rationale": "The answer matches the supplied reference and cites only allowed source IDs.",
                "unsupported_claims": [],
            }
        )

    record = capture_live_rubrics(captures=captures, manifest=manifest, judge=fake_judge)

    assert record["status"] == "passed"
    assert record["mean_normalized_score"] == 1.0
    assert [item["case_id"] for item in record["results"]] == list(REFERENCE_CLAIMS)
    assert len(calls) == 3
    assert all(call["model"] == manifest["judge_model"] for call in calls)
    assert all(call["allowed_source_ids"] for call in calls)
    assert all(call["expected_claims"] == REFERENCE_CLAIMS[item["case_id"]] for call, item in zip(calls, record["results"]))


def test_live_rubric_capture_rejects_unfrozen_manifest() -> None:
    captures = json.loads(
        (ROOT / "evals/examples/live_grader_queries_plain_text.json").read_text(encoding="utf-8")
    )

    try:
        capture_live_rubrics(captures=captures, manifest={"frozen": False})
    except ValueError as error:
        assert "frozen" in str(error)
    else:
        raise AssertionError("unfrozen manifests must be rejected")
