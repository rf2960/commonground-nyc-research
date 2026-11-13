import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_committed_hill_climb_report_uses_preserved_commits_and_frozen_corpus():
    report = json.loads(
        (ROOT / "evals/examples/hill_climb_results.json").read_text(encoding="utf-8")
    )

    assert report["schema_version"] == "hill-climb-report-v1"
    assert report["corpus"]["cases"] == 50
    assert report["corpus"]["held_out"] is True
    assert report["corpus"]["prompt_reuse_prohibited"] is True
    assert report["corpus"]["margin"] == 1 / (50**0.5)

    summary = report["summary"]
    assert [row["stage"] for row in summary] == ["baseline", "change_1", "change_2"]
    assert [row["passed"] for row in summary] == [0, 40, 50]
    assert [row["score"] for row in summary] == [0.0, 0.8, 1.0]
    assert summary[1]["exceeds_margin"] is True
    assert summary[2]["exceeds_margin"] is True
    assert summary[0]["commit"].startswith("7b596c7")
    assert summary[1]["commit"].startswith("2bbad8b")
    assert summary[2]["commit"].startswith("96989b0")


def test_hill_climb_raw_results_cover_same_50_cases_at_every_stage():
    report = json.loads(
        (ROOT / "evals/examples/hill_climb_results.json").read_text(encoding="utf-8")
    )

    for result in report["raw_results"]:
        assert result["cases"] == 50
        assert len(result["results"]) == 50
