"""Run the rubric judge over the three committed live grader-query captures.

The command is intended for a credentialed runtime such as a one-off Cloud Run Job.
It never reads Maps credentials and prints only the questions, source IDs, model
identity, and normalized rubric results already suitable for committing as evidence.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from evals.rubric_judge import RubricJudgeResult, judge_writer_answer


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CAPTURES = ROOT / "evals/examples/live_grader_queries_plain_text.json"
DEFAULT_MANIFEST = ROOT / "evals/model_manifest.json"

REFERENCE_CLAIMS: Mapping[str, tuple[str, ...]] = {
    "expansion": (
        "Keep the 5-star minimum, moderate-price requirement, meeting time, and every commute limit unchanged.",
        "Explain which initial area-center commute checks exceed which traveler limits.",
        "Use at most one MTA-supported targeted follow-up and cite the selected station records.",
        "If the bounded initial and expansion searches support no feasible cafe, make no recommendation and do not claim that none exists elsewhere.",
    ),
    "exact_route": (
        "Use exact-cafe Routes evidence rather than area-center estimates for the final hard-limit decision.",
        "Report Alex 29.9/35 minutes, Blair 28.6/30 minutes, and Casey 22/40 minutes for Little Collins.",
        "Recommend Little Collins only because the cited exact routes and cafe facts satisfy every unchanged constraint.",
        "Qualify future regular-schedule opening evidence as an estimate rather than a guarantee.",
    ),
    "cafe_hours": (
        "Use exact-cafe Routes evidence and preserve the rating, moderate-price, opening, meeting-time, and commute constraints.",
        "Report Alex 29.9/35 minutes, Blair 28.6/30 minutes, and Casey 22/40 minutes for Little Collins.",
        "Identify future regular-opening-hours evidence as provisional and advise direct venue verification.",
        "Do not turn missing or provisional hours evidence into a guaranteed open claim.",
    ),
}


def _source_ids(case: Mapping[str, Any]) -> tuple[str, ...]:
    values = []
    for source in case.get("sources", []):
        if isinstance(source, Mapping) and isinstance(source.get("source_id"), str):
            values.append(source["source_id"])
    return tuple(sorted(set(values)))


def capture_live_rubrics(
    *,
    captures: Mapping[str, Any],
    manifest: Mapping[str, Any],
    judge: Callable[..., RubricJudgeResult] = judge_writer_answer,
) -> dict[str, Any]:
    """Score all three frozen live answers with one strict rubric implementation."""

    if manifest.get("frozen") is not True:
        raise ValueError("model manifest must be frozen")
    model = manifest.get("judge_model") or manifest.get("model")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("judge model is required")
    location = manifest.get("vertex_location", "global")
    cases = captures.get("cases")
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        raise ValueError("live captures must contain cases")

    results = []
    for case in cases:
        if not isinstance(case, Mapping):
            raise ValueError("each live capture must be an object")
        case_id = case.get("case_id")
        if case_id not in REFERENCE_CLAIMS:
            raise ValueError(f"missing rubric reference for {case_id!r}")
        question = case.get("question")
        answer = case.get("response")
        allowed_source_ids = _source_ids(case)
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"question missing for {case_id}")
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError(f"answer missing for {case_id}")
        if not allowed_source_ids:
            raise ValueError(f"source IDs missing for {case_id}")
        scored = judge(
            question=question,
            answer=answer,
            expected_claims=REFERENCE_CLAIMS[case_id],
            allowed_source_ids=allowed_source_ids,
            model=model,
            vertex_location=location,
        )
        results.append(
            {
                "case_id": case_id,
                "question": question,
                "expected_claims": list(REFERENCE_CLAIMS[case_id]),
                "allowed_source_ids": list(allowed_source_ids),
                "rubric": scored.model_dump(mode="json"),
                "normalized_score": scored.normalized_score,
            }
        )

    return {
        "schema_version": "live-rubric-capture-v1",
        "status": "passed",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "model": manifest.get("model"),
        "judge_model": model,
        "vertex_location": location,
        "source_capture": str(DEFAULT_CAPTURES.relative_to(ROOT)).replace("\\", "/"),
        "execution": {
            "commit": os.getenv("EVAL_EXECUTION_COMMIT") or None,
            "cloud_run_revision": os.getenv("EVAL_EXECUTION_REVISION") or None,
        },
        "results": results,
        "mean_normalized_score": sum(item["normalized_score"] for item in results) / len(results),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, default=DEFAULT_CAPTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        record = capture_live_rubrics(
            captures=json.loads(args.captures.read_text(encoding="utf-8")),
            manifest=json.loads(args.manifest.read_text(encoding="utf-8")),
        )
    except Exception:
        print(json.dumps({"schema_version": "live-rubric-capture-v1", "status": "failed", "reason_code": "SAFE_JUDGE_FAILURE"}))
        return 2
    rendered = json.dumps(record, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
