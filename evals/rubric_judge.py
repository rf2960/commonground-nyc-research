"""Reference/rubric judge for Writer answers, with a strict auditable schema."""

from __future__ import annotations

import json
from typing import Any, Callable

import litellm
from pydantic import BaseModel, ConfigDict, Field, ValidationError


JUDGE_SYSTEM_PROMPT = """You are a strict evaluator, not a research agent.
Use only the supplied reference, allowed source IDs, and answer. Return one JSON object
with integer scores from 0 to 4 for: recommendation_correctness,
calibrated_uncertainty, comparison_usefulness, and citation_support. Also return a
short rationale and a list of unsupported_claims. Do not reward facts absent from the
reference. A cited claim is supported only when its source ID is in allowed_source_ids.
"""


class RubricJudgeError(ValueError):
    """The judge call failed or returned an invalid result."""


class RubricScores(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    recommendation_correctness: int = Field(ge=0, le=4)
    calibrated_uncertainty: int = Field(ge=0, le=4)
    comparison_usefulness: int = Field(ge=0, le=4)
    citation_support: int = Field(ge=0, le=4)


class RubricJudgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scores: RubricScores
    rationale: str = Field(min_length=1, max_length=1200)
    unsupported_claims: tuple[str, ...] = ()

    @property
    def normalized_score(self) -> float:
        values = (
            self.scores.recommendation_correctness,
            self.scores.calibrated_uncertainty,
            self.scores.comparison_usefulness,
            self.scores.citation_support,
        )
        return sum(values) / (4 * len(values))


def judge_writer_answer(
    *,
    question: str,
    answer: str,
    expected_claims: list[str] | tuple[str, ...],
    allowed_source_ids: list[str] | tuple[str, ...],
    model: str,
    vertex_location: str,
    completion: Callable[..., Any] = litellm.completion,
) -> RubricJudgeResult:
    """Judge one answer without tools; callers persist model/version beside the score."""

    payload = {
        "question": question,
        "reference": {"expected_claims": list(expected_claims)},
        "allowed_source_ids": list(allowed_source_ids),
        "answer": answer,
        "rubric": {
            "scale": "0=absent/wrong, 4=fully correct and supported",
            "dimensions": [
                "recommendation_correctness",
                "calibrated_uncertainty",
                "comparison_usefulness",
                "citation_support",
            ],
        },
    }
    try:
        reply = completion(
            model=model,
            vertex_location=vertex_location,
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
    except Exception as error:
        raise RubricJudgeError("rubric judge model call failed safely") from error
    try:
        content = reply.choices[0].message.content
        raw = json.loads(content)
        return RubricJudgeResult.model_validate(raw)
    except (
        AttributeError,
        IndexError,
        TypeError,
        json.JSONDecodeError,
        ValidationError,
    ) as error:
        raise RubricJudgeError("rubric judge returned invalid JSON") from error
