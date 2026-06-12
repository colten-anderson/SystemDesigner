from pathlib import Path

import pytest

from voice_interview import state as st
from voice_interview.orchestrator import CORE_FACT_KEYS, InterviewOrchestrator
from voice_interview.protocol import REQUIRED_FILES, load_plan
from voice_interview.state import InterviewState, StateStore

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def plan():
    return load_plan(REPO_ROOT)


@pytest.fixture
def orchestrator(plan, tmp_path):
    state = InterviewState(output_dir=str(tmp_path / "portfolio"))
    store = StateStore(tmp_path / "portfolio" / ".interview-state.json")
    return InterviewOrchestrator(plan, state, store)


def fill_core_facts(orch: InterviewOrchestrator) -> None:
    orch.set_system_fact("system_name", "Customer Billing API")
    orch.set_system_fact("owning_team", "Payments Platform")
    orch.set_system_fact("criticality_tier", "Tier 1")
    orch.set_system_fact("environments", "dev, staging, prod")


def complete_current_section(orch: InterviewOrchestrator, file_name: str) -> None:
    section = orch.plan.section_for(file_name)
    for field in section.output_fields:
        orch.record_answer(
            file_name,
            field,
            f"A concrete, well-specified value for {field} with owner names and numbers.",
        )
    orch.set_file_summary(
        file_name, f"Summary of {file_name} captured live during the interview session."
    )


def test_mode_gate_blocks_next_section(orchestrator) -> None:
    result = orchestrator.next_section()
    assert result["status"] == "error"
    assert "mode" in result["message"].lower()


def test_set_mode_unlocks_core_facts(orchestrator) -> None:
    result = orchestrator.set_mode("b")
    assert result["status"] == "ok"
    assert result["mode"] == "B"
    assert "deploy pipeline" in result["mode_emphasis"]
    assert orchestrator.state.phase == st.PHASE_CORE_FACTS


def test_invalid_mode_rejected(orchestrator) -> None:
    result = orchestrator.set_mode("Z")
    assert result["status"] == "error"
    assert orchestrator.state.phase == st.PHASE_MODE_SELECT


def test_core_facts_gate(orchestrator) -> None:
    orchestrator.set_mode("A")
    result = orchestrator.next_section()
    assert result["status"] == "error"
    for key in CORE_FACT_KEYS:
        assert key in result["message"]

    fill_core_facts(orchestrator)
    result = orchestrator.next_section()
    assert result["status"] == "ok"
    assert result["section"]["file"] == REQUIRED_FILES[0]
    # Prompts come from the template, parsed at runtime.
    assert any("official system name" in p for p in result["section"]["interview_prompts"])
    assert result["section"]["mode_emphasis"]


def test_next_section_gated_until_fields_recorded(orchestrator) -> None:
    orchestrator.set_mode("B")
    fill_core_facts(orchestrator)
    first = orchestrator.next_section()["section"]["file"]

    blocked = orchestrator.next_section()
    assert blocked["status"] == "error"
    section = orchestrator.plan.section_for(first)
    for field in section.output_fields:
        assert field in blocked["message"]

    for field in section.output_fields:
        orchestrator.record_answer(first, field, f"Concrete recorded value for {field} here.")

    # Still blocked: summary not yet drafted.
    blocked = orchestrator.next_section()
    assert blocked["status"] == "error"
    assert "summary" in blocked["message"].lower()

    orchestrator.set_file_summary(first, "Two to four sentences of summary text.")
    advanced = orchestrator.next_section()
    assert advanced["status"] == "ok"
    assert advanced["section"]["file"] == REQUIRED_FILES[1]
    assert orchestrator.state.files[first].status == st.FILE_COMPLETE


def test_full_schema_walk_visits_all_ten_files(orchestrator) -> None:
    orchestrator.set_mode("D")
    fill_core_facts(orchestrator)
    visited = []
    result = orchestrator.next_section()
    while result.get("section"):
        file_name = result["section"]["file"]
        visited.append(file_name)
        complete_current_section(orchestrator, file_name)
        result = orchestrator.next_section()

    assert visited == REQUIRED_FILES
    assert orchestrator.state.phase == st.PHASE_WRAP_UP

    ended = orchestrator.end_interview()
    assert ended["status"] == "ok"
    assert orchestrator.is_complete()


def test_skip_section_marks_tbd_and_advances(orchestrator) -> None:
    orchestrator.set_mode("C")
    fill_core_facts(orchestrator)
    first = orchestrator.next_section()["section"]["file"]

    result = orchestrator.skip_section("team ran out of time")
    assert result["status"] == "ok"
    assert result["skipped"] == first
    assert result["section"]["file"] == REQUIRED_FILES[1]

    fs = orchestrator.state.files[first]
    assert fs.status == st.FILE_SKIPPED
    section = orchestrator.plan.section_for(first)
    for field in section.output_fields:
        answer = fs.fields[field]
        assert answer.status == st.TBD
        assert answer.value.startswith("TBD (owner: Payments Platform")


def test_repeat_context_returns_current_prompts(orchestrator) -> None:
    repeat = orchestrator.repeat_context()
    assert "mode" in repeat["repeat"].lower()

    orchestrator.set_mode("A")
    fill_core_facts(orchestrator)
    current = orchestrator.next_section()["section"]["file"]
    repeat = orchestrator.repeat_context()
    assert repeat["section"]["file"] == current
    assert repeat["section"]["interview_prompts"]


def test_section_status_tracks_completion(orchestrator) -> None:
    orchestrator.set_mode("B")
    fill_core_facts(orchestrator)
    first = orchestrator.next_section()["section"]["file"]
    section = orchestrator.plan.section_for(first)
    orchestrator.record_answer(first, section.output_fields[0], "A long enough concrete answer value.")

    status = orchestrator.section_status(first)
    info = status["files"][first]
    assert info["fields_recorded"] == 1
    assert info["fields_total"] == len(section.output_fields)
    assert section.output_fields[0] not in info["remaining_fields"]
    assert len(info["remaining_fields"]) == len(section.output_fields) - 1


def test_end_interview_refuses_mid_section_unless_partial(orchestrator) -> None:
    orchestrator.set_mode("B")
    fill_core_facts(orchestrator)
    orchestrator.next_section()

    refused = orchestrator.end_interview()
    assert refused["status"] == "error"

    ended = orchestrator.end_interview(partial=True)
    assert ended["status"] == "ok"
    assert orchestrator.is_complete()
    # Every field of every file is now recorded (as TBDs) so the writer can
    # render a complete portfolio.
    for section in orchestrator.plan.sections:
        fs = orchestrator.state.files[section.file_name]
        for field in section.output_fields:
            assert field in fs.fields


def test_pause_returns_resume_instructions(orchestrator) -> None:
    result = orchestrator.pause_interview()
    assert "--resume" in result["message"]
    assert orchestrator.store.path.exists()
