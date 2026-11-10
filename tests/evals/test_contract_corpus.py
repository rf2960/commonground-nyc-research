from evals.contract_corpus import evaluate_contract_corpus


def test_contract_corpus_has_50_unique_provenance_recorded_passing_cases():
    result = evaluate_contract_corpus()

    assert result["cases"] == 50
    assert result["passed"] == 50
    assert result["score"] == 1.0
    assert result["slices"] == {
        "cafe_constraint_blocker": 10,
        "clarification_and_intake": 10,
        "commute_limit_blocker": 10,
        "evidence_insufficient": 10,
        "feasible_boundaries": 10,
    }
    ids = [case["case_id"] for case in result["results"]]
    assert len(ids) == len(set(ids))
    for case in result["results"]:
        assert case["provenance"]["source_paths"]
        assert case["provenance"]["live_provider_observation"] is False
        assert case["provenance"]["prompt_reuse_prohibited"] is True
