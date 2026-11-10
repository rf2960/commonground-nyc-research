"""Run provenance-recorded Project 2 cases against the real research pipeline."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from commonground.research import (
    DeepResearchService,
    ResearchBrief,
    ResearchResult,
    ResearchRunner,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_DIR = REPO_ROOT / "evals" / "cases"


def _repo_path(value: str) -> Path:
    path = (REPO_ROOT / value).resolve()
    if not path.is_relative_to(REPO_ROOT):
        raise ValueError(f"evaluation path escapes the repository: {value}")
    return path


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_case(path: str | Path) -> dict[str, Any]:
    case_path = Path(path)
    if not case_path.is_absolute():
        case_path = _repo_path(str(case_path))
    payload = _read_json(case_path)
    required = {"case_id", "owner", "provenance", "question", "fixtures", "expected"}
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"evaluation case is missing fields: {missing}")
    if not payload["provenance"].get("source_paths"):
        raise ValueError("evaluation cases must record at least one provenance source path")
    return payload


def _fixture_results(case: dict[str, Any]) -> dict[str, ResearchResult]:
    results: dict[str, ResearchResult] = {}
    for fixture_path in case["fixtures"]["result_paths"]:
        for raw in _read_json(_repo_path(fixture_path)):
            result = ResearchResult.model_validate(raw)
            if result.task_id in results:
                raise ValueError(f"duplicate fixture task ID: {result.task_id}")
            results[result.task_id] = result
    return results


def _check(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {
        "name": name,
        "passed": actual == expected,
        "expected": expected,
        "actual": actual,
    }


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    """Execute one case and return deterministic checks plus the raw agent capture."""

    brief = ResearchBrief.model_validate(
        _read_json(_repo_path(case["fixtures"]["brief_path"]))
    )
    if brief.question != case["question"]:
        raise ValueError("case question must exactly match its ResearchBrief question")
    fixture_results = _fixture_results(case)

    async def executor(_context, _brief, task):
        try:
            return fixture_results[task.task_id]
        except KeyError as error:
            raise ValueError(f"no fixture result for task {task.task_id}") from error

    output = DeepResearchService(ResearchRunner(executor)).run_sync(brief)
    expected = case["expected"]
    feasibility = {
        item.cafe_id: item.status for item in output.run.feasibility_results
    }
    follow_up = output.run.follow_up_decision
    source_ids = sorted(
        {
            source.source_id
            for result in (*output.run.round_one_results, *output.run.round_two_results)
            for source in result.sources
        }
    )
    required_sources = sorted(expected["required_source_ids"])
    required_fragments = expected.get("required_response_fragments", [])
    trace_has_agent_round = all(
        isinstance(event.get("agent"), str)
        and isinstance(event.get("round"), int)
        for event in output.tool_calls
    )

    checks = [
        _check(
            "recommended cafe",
            expected["recommended_cafe_id"],
            output.report.recommended_cafe_id,
        ),
        _check("feasibility statuses", expected["feasibility_statuses"], feasibility),
        _check(
            "follow-up reason",
            expected["follow_up_reason_code"],
            follow_up.reason_code if follow_up else None,
        ),
        _check(
            "follow-up targets",
            expected["follow_up_selected_ids"],
            list(follow_up.selected_ids) if follow_up else [],
        ),
        _check(
            "required source coverage",
            required_sources,
            sorted(set(required_sources) & set(source_ids)),
        ),
        _check(
            "required answer fragments",
            True,
            all(fragment in output.response for fragment in required_fragments),
        ),
        _check(
            "bounded follow-up",
            True,
            (0 if follow_up is None else 1) <= brief.max_follow_up_rounds,
        ),
        _check("trace agent and round fields", True, trace_has_agent_round),
    ]
    return {
        "schema_version": "eval-capture-v1",
        "case_id": case["case_id"],
        "owner": case["owner"],
        "passed": all(check["passed"] for check in checks),
        "deterministic_score": sum(check["passed"] for check in checks) / len(checks),
        "checks": checks,
        "actual": {
            "recommended_cafe_id": output.report.recommended_cafe_id,
            "feasibility_statuses": feasibility,
            "follow_up_reason_code": follow_up.reason_code if follow_up else None,
            "follow_up_selected_ids": list(follow_up.selected_ids) if follow_up else [],
            "source_ids": source_ids,
            "response": output.response,
            "tool_calls": list(output.tool_calls),
        },
    }


def write_capture(result: dict[str, Any], destination: str | Path) -> Path:
    """Write a timestamped raw capture without altering its scored content."""

    path = Path(destination)
    if not path.is_absolute():
        path = _repo_path(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    capture = {
        **result,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "build": {"kind": "fixed-data vertical slice"},
    }
    path.write_text(
        json.dumps(capture, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def _case_paths(case_arg: str | None) -> list[Path]:
    if case_arg:
        return [_repo_path(case_arg)]
    return sorted(DEFAULT_CASE_DIR.glob("*.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", help="Repository-relative case JSON; defaults to all")
    parser.add_argument(
        "--write-capture",
        action="store_true",
        help="Write each result under evals/examples/<owner>/actual_agent.json",
    )
    args = parser.parse_args()

    results = []
    for path in _case_paths(args.case):
        case = load_case(path)
        result = evaluate_case(case)
        results.append(result)
        if args.write_capture:
            write_capture(
                result,
                REPO_ROOT
                / "evals"
                / "examples"
                / case["owner"]
                / "actual_agent.json",
            )

    summary = {
        "cases": len(results),
        "passed": sum(result["passed"] for result in results),
        "mean_deterministic_score": (
            sum(result["deterministic_score"] for result in results) / len(results)
            if results
            else 0
        ),
        "results": results,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
