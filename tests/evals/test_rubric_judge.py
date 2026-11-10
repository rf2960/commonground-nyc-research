import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from evals.baseline import capture_no_tools_baseline
from evals.rubric_judge import RubricJudgeError, judge_writer_answer


def _reply(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_rubric_judge_uses_reference_and_returns_normalized_score():
    observed = {}

    def completion(**kwargs):
        observed.update(kwargs)
        return _reply(
            json.dumps(
                {
                    "scores": {
                        "recommendation_correctness": 4,
                        "calibrated_uncertainty": 3,
                        "comparison_usefulness": 4,
                        "citation_support": 3,
                    },
                    "rationale": "Correct recommendation with one citation gap.",
                    "unsupported_claims": ["Opening hours are guaranteed."],
                }
            )
        )

    result = judge_writer_answer(
        question="Can expansion help?",
        answer="Yes [source:routes:1].",
        expected_claims=["Expansion found one feasible cafe."],
        allowed_source_ids=["source:routes:1"],
        model="test-model",
        vertex_location="us-central1",
        completion=completion,
    )

    assert result.normalized_score == 0.875
    assert "tools" not in observed
    assert observed["temperature"] == 0
    judge_input = json.loads(observed["messages"][1]["content"])
    assert judge_input["allowed_source_ids"] == ["source:routes:1"]


def test_rubric_judge_rejects_out_of_range_score():
    payload = {
        "scores": {
            "recommendation_correctness": 5,
            "calibrated_uncertainty": 4,
            "comparison_usefulness": 4,
            "citation_support": 4,
        },
        "rationale": "Invalid score.",
        "unsupported_claims": [],
    }
    with pytest.raises(RubricJudgeError):
        judge_writer_answer(
            question="q",
            answer="a",
            expected_claims=[],
            allowed_source_ids=[],
            model="test-model",
            vertex_location="us-central1",
            completion=lambda **_: _reply(json.dumps(payload)),
        )


def test_baseline_has_question_only_and_records_disabled_conditions():
    observed = {}

    def completion(**kwargs):
        observed.update(kwargs)
        return _reply("A model-only answer.")

    capture = capture_no_tools_baseline(
        case_id="case-1",
        question="What changed?",
        model="test-model",
        vertex_location="us-central1",
        completion=completion,
        now=lambda: datetime(2026, 11, 10, tzinfo=timezone.utc),
    )

    assert observed["messages"] == [{"role": "user", "content": "What changed?"}]
    assert "tools" not in observed
    assert capture["conditions"] == {
        "tools_enabled": False,
        "system_prompt_present": False,
        "input_is_question_only": True,
    }
    assert capture["raw_output"] == "A model-only answer."
