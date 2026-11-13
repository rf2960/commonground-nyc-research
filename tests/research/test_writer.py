import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from commonground.research import (
    CitedClaim,
    EvidenceWriter,
    LeadOrchestrator,
    ModelBackedEvidenceWriter,
    ResearchBrief,
    ResearchResult,
    ResearchRunner,
    WriterReport,
    validate_writer_report,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fixture_result_map(round_two=None):
    payloads = fixture("round_1_results.json") + (
        round_two if round_two is not None else fixture("round_2_results.json")
    )
    results = [ResearchResult.model_validate(payload) for payload in payloads]
    return {result.task_id: result for result in results}


def execute_lead(result_map):
    brief = ResearchBrief.model_validate(fixture("research_brief.json"))

    async def executor(context, brief_value, task_value):
        return result_map[task_value.task_id]

    return asyncio.run(
        LeadOrchestrator(ResearchRunner(executor)).run(brief)
    )


def test_writer_reports_supported_expansion_recommendation_with_inline_ids():
    run = execute_lead(fixture_result_map())
    report = EvidenceWriter().write(run)

    assert report.recommended_cafe_id == "cafe:gplaces:fixture-expansion-cafe"
    assert "Fixture Commons Cafe" in report.response
    assert "FEASIBLE" in report.response
    assert "Union Square failed at the area-center stage" in report.response
    assert "Downtown Brooklyn failed at the area-center stage" in report.response
    assert "future regular-schedule estimate, not a guarantee" in report.response
    assert "source:mta-stations:fixture-queensboro-plaza" in report.response
    assert "source:google-places:fixture-r2" in report.response
    assert "source:google-routes:fixture-r2" in report.response
    assert "lead-policy:places-before-routes" in report.response
    validate_writer_report(report, run)


def test_every_fact_claim_cites_exactly_the_sources_attached_to_its_facts():
    run = execute_lead(fixture_result_map())
    report = EvidenceWriter().write(run)
    facts = {
        fact.fact_id: fact
        for result in (*run.round_one_results, *run.round_two_results)
        for fact in result.facts
    }

    for claim in report.claims:
        expected_sources = tuple(
            sorted(
                {
                    source_id
                    for fact_id in claim.fact_ids
                    for source_id in facts[fact_id].source_ids
                }
            )
        )
        assert claim.source_ids == expected_sources
        assert all(reference in report.response for reference in claim.fact_ids)
        assert all(reference in report.response for reference in claim.source_ids)


def test_missing_exact_route_stays_unknown_and_blocks_recommendation():
    round_two = fixture("round_2_results.json")
    transit = round_two[1]
    transit["facts"] = [
        fact
        for fact in transit["facts"]
        if fact["subject_id"] != "traveler:bob"
    ]
    transit["missing"] = [
        {
            "missing_id": "missing:transit:r2:001",
            "candidate_id": "cafe:gplaces:fixture-expansion-cafe",
            "subject_id": "traveler:bob",
            "field": "transit_duration_minutes",
            "reason_code": "ROUTE_UNAVAILABLE",
            "detail": "No exact-destination route was returned for Bob.",
            "retryable": False,
            "next_action": "Report Bob's commute as unknown; do not recommend the cafe.",
        }
    ]

    run = execute_lead(fixture_result_map(round_two))
    report = EvidenceWriter().write(run)

    assert run.feasibility_results[0].status == "EVIDENCE_INSUFFICIENT"
    assert report.recommended_cafe_id is None
    assert "Do not recommend Fixture Commons Cafe" in report.response
    assert "EVIDENCE_INSUFFICIENT" in report.response
    assert "missing:transit:r2:001" in report.response
    assert "No exact-destination route was returned for Bob" in report.response


def test_writer_validator_rejects_a_reference_not_present_in_lead_evidence():
    run = execute_lead(fixture_result_map())
    invalid_claim = CitedClaim(
        text="Unsupported statement.",
        fact_ids=("fact:cafe:r2:999",),
    )
    invalid = WriterReport(
        response=(
            "## Result\n\n- Unsupported statement. "
            "[facts=fact:cafe:r2:999]"
        ),
        claims=(invalid_claim,),
        unknowns=(),
        recommended_cafe_id=None,
    )

    with pytest.raises(ValueError, match="unknown fact"):
        validate_writer_report(invalid, run)


def test_claim_without_any_evidence_is_rejected_at_construction():
    with pytest.raises(ValueError, match="must cite"):
        CitedClaim(text="Uncited prose")


def test_unknown_derived_reference_does_not_bypass_citation_validation():
    run = execute_lead(fixture_result_map())
    claim = CitedClaim(text='Unsupported derived assertion.', derived_ref='invented-rule:anything')
    invalid = WriterReport(response='Unsupported [derived=invented-rule:anything]',
                           claims=(claim,), unknowns=(), recommended_cafe_id=None)
    with pytest.raises(ValueError, match='unknown derived'):
        validate_writer_report(invalid, run)


def test_recommendation_id_must_have_feasible_evidence():
    from dataclasses import replace
    run = execute_lead(fixture_result_map())
    report = replace(EvidenceWriter().write(run), recommended_cafe_id='cafe:gplaces:invented')
    with pytest.raises(ValueError, match='FEASIBLE'):
        validate_writer_report(report, run)


def test_empty_bounded_search_has_explicit_result_not_blank_answer():
    from dataclasses import replace
    run = execute_lead(fixture_result_map())
    empty = replace(run, feasibility_results=())
    report = EvidenceWriter().write(empty)
    assert 'No supported cafe recommendation' in report.response
    assert 'does not prove' in report.response
    assert report.recommended_cafe_id is None


def _completion_with(content, calls):
    def complete(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    return complete


def test_model_backed_writer_can_reorder_only_validated_sections():
    run = execute_lead(fixture_result_map())
    calls = []
    writer = ModelBackedEvidenceWriter(
        model="test-model",
        vertex_location="global",
        completion=_completion_with(
            json.dumps(
                {
                    "section_order": [
                        "What the targeted follow-up added",
                        "Why the initial candidates failed",
                        "Result",
                    ]
                }
            ),
            calls,
        ),
    )

    report = writer.write(run)

    assert report.writer_mode == "model-backed-validated"
    assert report.model == "test-model"
    assert report.response.startswith("## What the targeted follow-up added")
    assert "Fixture Commons Cafe" in report.response
    assert "source:google-routes:fixture-r2" in report.response
    validate_writer_report(report, run)
    assert calls[0]["model"] == "test-model"
    assert "tools" not in calls[0]
    planner_payload = json.loads(calls[0]["messages"][1]["content"])
    assert set(planner_payload["sections"][0]) == {"title", "claim_count"}


def test_model_backed_writer_falls_back_when_model_changes_section_set():
    run = execute_lead(fixture_result_map())
    writer = ModelBackedEvidenceWriter(
        model="test-model",
        vertex_location="global",
        completion=_completion_with(
            '{"section_order":["Result","Invented section"]}', []
        ),
    )

    report = writer.write(run)

    assert report.writer_mode == "deterministic"
    assert report.model is None
    assert report.response.startswith("## Result")
