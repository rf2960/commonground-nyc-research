"""Reproduce the 50-case hill-climbing log across preserved Git revisions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKER = Path(__file__).with_name("hill_climb_worker.py")
DEFAULT_OUTPUT = ROOT / "evals/examples/hill_climb_results.json"
MARGIN = 1 / (50**0.5)
VARIANTS = (
    {
        "stage": "baseline",
        "commit": "7b596c78766e59995d6639113c9128c50c09e28e",
        "change": "Validated evidence contracts only; deterministic feasibility and clarification gates were not implemented yet.",
    },
    {
        "stage": "change_1",
        "commit": "2bbad8bd936c7ec7a636146c5ff79a87c48ccf45",
        "change": "Added deterministic feasibility evaluation for commute, cafe, and missing-evidence outcomes.",
    },
    {
        "stage": "change_2",
        "commit": "96989b02bad0e9432b5c9e6aa691be4f9646e687",
        "change": "Added the deterministic clarification/intake gate for origins, limits, meeting time, and timezone.",
    },
)


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=True,
    )


def evaluate_variant(variant: dict[str, str], worktree: Path) -> dict[str, Any]:
    _run(["git", "worktree", "add", "--detach", str(worktree), variant["commit"]], cwd=ROOT)
    worker_copy = worktree / "_hill_climb_worker.py"
    shutil.copy2(WORKER, worker_copy)
    try:
        completed = _run([sys.executable, str(worker_copy)], cwd=worktree)
        score = json.loads(completed.stdout)
        resolved = _run(["git", "rev-parse", "HEAD"], cwd=worktree).stdout.strip()
        return {**variant, "resolved_commit": resolved, **score}
    finally:
        _run(["git", "worktree", "remove", "--force", str(worktree)], cwd=ROOT)


def build_report() -> dict[str, Any]:
    results = []
    with tempfile.TemporaryDirectory(prefix="commonground-hill-climb-", dir=ROOT.parent) as temp:
        temp_root = Path(temp)
        for index, variant in enumerate(VARIANTS):
            results.append(evaluate_variant(variant, temp_root / f"variant-{index}"))

    previous = None
    summary = []
    for result in results:
        gain = None if previous is None else result["score"] - previous
        summary.append(
            {
                "stage": result["stage"],
                "commit": result["resolved_commit"],
                "change": result["change"],
                "passed": result["passed"],
                "cases": result["cases"],
                "score": result["score"],
                "gain_from_previous": gain,
                "exceeds_margin": None if gain is None else gain > MARGIN,
            }
        )
        previous = result["score"]

    return {
        "schema_version": "hill-climb-report-v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "corpus": {
            "cases": 50,
            "held_out": True,
            "prompt_reuse_prohibited": True,
            "margin": MARGIN,
            "score_definition": "passed_cases / 50 on the same frozen contract expectations",
        },
        "summary": summary,
        "raw_results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": report["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
