import json
from pathlib import Path

import app as webapp
from commonground.research import (
    DeepResearchService,
    ResearchBrief,
    ResearchResult,
    ResearchRunner,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def brief() -> ResearchBrief:
    return ResearchBrief.model_validate(fixture("research_brief.json"))


def service() -> DeepResearchService:
    results = [
        ResearchResult.model_validate(payload)
        for payload in (
            fixture("round_1_results.json") + fixture("round_2_results.json")
        )
    ]
    by_task = {result.task_id: result for result in results}

    async def executor(context, brief_value, task_value):
        return by_task[task_value.task_id]

    return DeepResearchService(ResearchRunner(executor))


def test_service_returns_writer_output_and_deterministic_full_trace():
    output = service().run_sync(brief())

    assert "Fixture Commons Cafe" in output.response
    assert len(output.tool_calls) == 9
    assert [call["agent"] for call in output.tool_calls] == [
        "lead",
        "transit_researcher",
        "cafe_researcher",
        "expansion_researcher",
        "lead",
        "cafe_researcher",
        "transit_researcher",
        "lead",
        "writer",
    ]
    assert [call["round"] for call in output.tool_calls] == [
        1,
        1,
        1,
        1,
        2,
        2,
        2,
        2,
        2,
    ]
    assert all(
        {"name", "args", "result", "agent", "round"}.issubset(call)
        for call in output.tool_calls
    )
    assert [call["name"] for call in output.tool_calls[1:4]] == [
        "get_transit_matrix",
        "search_cafes_in_areas",
        "search_mta_expansion_candidates",
    ]
    assert output.tool_calls[4]["name"] == "choose_follow_up"
    assert output.tool_calls[-1]["name"] == "write_evidence_report"
    assert all(isinstance(call["result"], str) for call in output.tool_calls)


def test_chat_research_mode_preserves_response_shape_and_session_identity(monkeypatch):
    webapp.sessions.clear()
    webapp.session_last_seen.clear()
    monkeypatch.setattr(webapp, "research_service", service())

    response = webapp.chat(
        webapp.ChatRequest(
            message="Expand beyond the initial CommonGround candidates.",
            mode="research",
            research_brief=brief(),
        )
    )
    payload = response.model_dump()

    assert set(payload) == {"response", "session_id", "tool_calls"}
    assert response.session_id == "session-123"
    assert "Fixture Commons Cafe" in response.response
    assert len(response.tool_calls) == 9
    assert all("agent" in call and "round" in call for call in response.tool_calls)
    assert webapp.sessions[response.session_id][-1] == {
        "role": "assistant",
        "content": response.response,
    }


def test_research_mode_clarifies_missing_brief_before_any_tool_call():
    webapp.sessions.clear()
    webapp.session_last_seen.clear()

    response = webapp.chat(
        webapp.ChatRequest(message="Find somewhere for us", mode="research")
    )

    assert response.tool_calls == []
    assert "resolved origins" in response.response
    assert "commute limit" in response.response
    assert "timezone" in response.response


def test_unconfigured_live_research_never_claims_fixture_or_provider_results(monkeypatch):
    webapp.sessions.clear()
    webapp.session_last_seen.clear()
    monkeypatch.setattr(webapp, "research_service", None)

    response = webapp.chat(
        webapp.ChatRequest(
            message="Run deep research",
            mode="research",
            research_brief=brief(),
        )
    )

    assert response.tool_calls == []
    assert "not connected to live Routes and Places" in response.response
    assert "no live provider result was claimed" in response.response
    assert "Fixture Commons Cafe" not in response.response


def test_research_session_mismatch_is_rejected_without_execution(monkeypatch):
    webapp.sessions.clear()
    webapp.session_last_seen.clear()
    monkeypatch.setattr(webapp, "research_service", service())

    response = webapp.chat(
        webapp.ChatRequest(
            message="Run deep research",
            session_id="different-session",
            mode="research",
            research_brief=brief(),
        )
    )

    assert response.tool_calls == []
    assert "session_id must match" in response.response
    assert response.session_id == "different-session"
