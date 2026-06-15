import json
from pathlib import Path

import pytest

from voice_interview.orchestrator import InterviewOrchestrator
from voice_interview.protocol import load_plan
from voice_interview.state import InterviewState
from voice_interview.tools import TOOL_DEFINITIONS, dispatch_tool, tool_result_text

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def plan():
    return load_plan(REPO_ROOT)


@pytest.fixture
def orch(plan, tmp_path):
    state = InterviewState(output_dir=str(tmp_path / "p"))
    return InterviewOrchestrator(plan, state, None)


def test_tool_definitions_are_well_formed() -> None:
    assert len(TOOL_DEFINITIONS) == 12
    names = [d["name"] for d in TOOL_DEFINITIONS]
    assert len(set(names)) == 12
    for definition in TOOL_DEFINITIONS:
        assert definition["description"]
        schema = definition["input_schema"]
        assert schema["type"] == "object"
        for required in schema.get("required", []):
            assert required in schema["properties"]


def test_every_tool_dispatches_without_unknown_tool_error(orch) -> None:
    """Each schema name routes to a real handler (never 'Unknown tool')."""

    arguments = {
        "set_mode": {"mode": "B"},
        "set_system_fact": {"key": "system_name", "value": "X"},
        "record_answer": {"file": "system-identity.md", "field": "System name", "value": "X system"},
        "mark_unknown": {"file": "system-identity.md", "field": "Aliases", "owner": "J", "next_step": "ask"},
        "record_open_question": {"file": "system-identity.md", "question": "Q?", "owner": "J"},
        "set_file_summary": {"file": "system-identity.md", "summary": "S."},
        "section_status": {},
        "next_section": {},
        "skip_section": {"reason": "time"},
        "repeat_context": {},
        "pause_interview": {},
        "end_interview": {"partial": True},
    }
    for definition in TOOL_DEFINITIONS:
        name = definition["name"]
        result = dispatch_tool(orch, name, arguments[name])
        assert isinstance(result, dict)
        assert "Unknown tool" not in result.get("message", ""), name
        # Every result must be JSON-serializable (it goes back to the LLM).
        json.loads(tool_result_text(result))


def test_dispatch_full_happy_path(orch, plan) -> None:
    assert dispatch_tool(orch, "set_mode", {"mode": "D"})["status"] == "ok"
    for key in ["system_name", "owning_team", "criticality_tier", "environments"]:
        assert dispatch_tool(orch, "set_system_fact", {"key": key, "value": "v"})["status"] == "ok"
    section = dispatch_tool(orch, "next_section", {})["section"]
    assert section["file"] == "system-identity.md"
    recorded = dispatch_tool(
        orch,
        "record_answer",
        {"file": section["file"], "field": section["output_fields"][0], "value": "A concrete recorded value here."},
    )
    assert recorded["status"] in ("recorded", "recorded_provisional")
    status = dispatch_tool(orch, "section_status", {"file": section["file"]})
    assert status["files"][section["file"]]["fields_recorded"] == 1


def test_missing_required_argument_returns_error_not_crash(orch) -> None:
    result = dispatch_tool(orch, "record_answer", {"file": "system-identity.md"})
    assert result["status"] == "error"
    assert "Missing required argument" in result["message"]


def test_unknown_tool_returns_error(orch) -> None:
    result = dispatch_tool(orch, "fly_to_the_moon", {})
    assert result["status"] == "error"
    assert "Unknown tool" in result["message"]


def test_end_interview_defaults_to_non_partial(orch) -> None:
    # Without mode/facts the orchestrator is in MODE_SELECT; non-partial end
    # is allowed there (no open sections) but partial=False must be the default.
    result = dispatch_tool(orch, "end_interview", {})
    assert result["partial"] is False


def test_pause_sets_pause_requested(orch) -> None:
    assert orch.pause_requested is False
    dispatch_tool(orch, "pause_interview", {})
    assert orch.pause_requested is True
