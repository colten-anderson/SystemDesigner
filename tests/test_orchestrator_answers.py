from pathlib import Path

import pytest

from voice_interview import state as st
from voice_interview.orchestrator import InterviewOrchestrator, format_tbd
from voice_interview.protocol import load_plan
from voice_interview.state import InterviewState, StateStore

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def plan():
    return load_plan(REPO_ROOT)


@pytest.fixture
def orch(plan, tmp_path):
    state = InterviewState(output_dir=str(tmp_path / "portfolio"))
    store = StateStore(tmp_path / "portfolio" / ".interview-state.json")
    orchestrator = InterviewOrchestrator(plan, state, store)
    orchestrator.set_mode("B")
    orchestrator.set_system_fact("system_name", "Billing API")
    orchestrator.set_system_fact("owning_team", "Payments")
    orchestrator.set_system_fact("criticality_tier", "Tier 1")
    orchestrator.set_system_fact("environments", "prod")
    orchestrator.next_section()
    return orchestrator


def test_record_answer_normal(orch) -> None:
    result = orch.record_answer(
        "system-identity.md", "System name", "Customer Billing API, also known as CBA."
    )
    assert result["status"] == "recorded"
    answer = orch.state.files["system-identity.md"].fields["System name"]
    assert answer.status == st.ANSWERED
    assert "Customer Billing API" in answer.value


def test_record_answer_accepts_name_without_extension_and_case(orch) -> None:
    result = orch.record_answer(
        "system-identity", "system name", "Customer Billing API, our revenue system."
    )
    assert result["status"] == "recorded"
    assert "System name" in orch.state.files["system-identity.md"].fields


def test_thin_answer_flagged_with_follow_up_hint(orch) -> None:
    result = orch.record_answer("system-identity.md", "Aliases", "CBA")
    assert result["status"] == "recorded_provisional"
    assert "follow-up" in result["follow_up_hint"].lower() or "follow up" in result[
        "follow_up_hint"
    ].lower()
    assert orch.state.files["system-identity.md"].fields["Aliases"].status == st.PROVISIONAL


def test_vague_answer_flagged(orch) -> None:
    result = orch.record_answer(
        "system-identity.md",
        "Criticality tier",
        "I think it is probably tier one but I am not sure about it honestly",
    )
    assert result["status"] == "recorded_provisional"


def test_provisional_answer_does_not_block_advance(orch, plan) -> None:
    # Provisional answers count as recorded; the gate only requires coverage.
    section = plan.section_for("system-identity.md")
    for field in section.output_fields:
        orch.record_answer("system-identity.md", field, "CBA")
    orch.set_file_summary("system-identity.md", "Short summary of the system identity.")
    result = orch.next_section()
    assert result["status"] == "ok"


def test_mark_unknown_formats_tbd_with_owner(orch) -> None:
    result = orch.mark_unknown(
        "system-identity.md", "Aliases", owner="Jane Doe", next_step="confirm by 2026-07-01"
    )
    assert result["status"] == "recorded_unknown"
    answer = orch.state.files["system-identity.md"].fields["Aliases"]
    assert answer.value == "TBD (owner: Jane Doe; next: confirm by 2026-07-01)"
    assert answer.status == st.TBD


def test_format_tbd_counts_as_filled_for_validator() -> None:
    # The validator treats a bare "TBD" as unfilled but a TBD with owner/next
    # as filled; this is the contract the writer relies on.
    rendered = format_tbd("Jane", "confirm")
    assert rendered != "TBD"
    assert rendered.startswith("TBD (")


def test_unknown_file_and_field_errors(orch) -> None:
    assert orch.record_answer("nope.md", "X", "value")["status"] == "error"
    bad_field = orch.record_answer("system-identity.md", "Nonexistent", "value")
    assert bad_field["status"] == "error"
    assert "Valid fields" in bad_field["message"]


def test_record_open_question(orch) -> None:
    result = orch.record_open_question(
        "system-identity.md", "Is the EU tenant in scope?", owner="Platform PM"
    )
    assert result["status"] == "ok"
    questions = orch.state.files["system-identity.md"].open_questions
    assert questions[0]["question"] == "Is the EU tenant in scope?"
    assert questions[0]["owner"] == "Platform PM"


def test_mode_emphasis_in_section_payload_for_each_mode(plan, tmp_path) -> None:
    for mode in ["A", "B", "C", "D", "Other"]:
        state = InterviewState(output_dir=str(tmp_path / f"p-{mode}"))
        orch = InterviewOrchestrator(plan, state, None)
        orch.set_mode(mode)
        for key, value in {
            "system_name": "S",
            "owning_team": "T",
            "criticality_tier": "1",
            "environments": "prod",
        }.items():
            orch.set_system_fact(key, value)
        payload = orch.next_section()["section"]
        assert payload["mode_emphasis"] == plan.mode_emphasis[mode]


def test_system_prompt_contains_protocol_and_mode(orch) -> None:
    prompt = orch.system_prompt()
    assert "System Context Interviewer" in prompt
    assert "Live Voice Interview Rules" in prompt
    assert "## Selected Mode: B" in prompt


def test_transcript_recording(orch) -> None:
    orch.on_assistant_text("Which mode applies?")
    orch.on_user_transcript("It's an in-house app")
    roles = [t["role"] for t in orch.state.transcript]
    assert roles[-2:] == ["assistant", "user"]
