"""Capture no-tools comparisons for the three live README questions."""

from __future__ import annotations

import json
from pathlib import Path

from evals.baseline import capture_no_tools_baseline


EVAL_DIR = Path(__file__).resolve().parent


def main() -> None:
    manifest = json.loads((EVAL_DIR / "model_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("frozen") is not True:
        raise ValueError("Freeze the production model before capturing baselines.")
    examples = EVAL_DIR / "examples"
    cases = json.loads((examples / "live_grader_queries.json").read_text(encoding="utf-8"))
    for case in cases["cases"]:
        baseline = capture_no_tools_baseline(
            case_id=case["case_id"],
            question=case["question"],
            model=manifest["model"],
            vertex_location=manifest["vertex_location"],
        )
        path = examples / f'{case["case_id"]}_baseline.json'
        path.write_text(json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(path.relative_to(EVAL_DIR.parent))


if __name__ == "__main__":
    main()
