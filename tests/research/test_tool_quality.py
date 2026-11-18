import json

import pytest

import tools as tool_registry


DATA_TOOL_NAMES = (
    "resolve_group_locations",
    "generate_candidate_areas",
    "get_transit_matrix",
    "search_cafes_in_areas",
)


def _tool(name):
    return next(item["function"] for item in tool_registry.TOOLS if item["function"]["name"] == name)


@pytest.mark.parametrize("name", DATA_TOOL_NAMES)
def test_primary_data_tool_parameters_include_concrete_format_examples(name):
    parameters = json.dumps(_tool(name)["parameters"])
    assert "Example:" in parameters or "for example" in parameters


def test_outer_tool_boundary_redacts_unexpected_exception_details(monkeypatch):
    def failed_tool(**_kwargs):
        raise RuntimeError("fixture-secret-token")

    monkeypatch.setitem(
        tool_registry.TOOL_MAP,
        "resolve_group_locations",
        failed_tool,
    )
    payload = json.loads(
        tool_registry.run_tool(
            "resolve_group_locations",
            {"locations": [{"traveler_id": "traveler:alex", "query": "Astoria"}]},
        )
    )

    assert payload["error"] == "resolve_group_locations failed safely: RuntimeError"
    assert "fixture-secret-token" not in json.dumps(payload)
