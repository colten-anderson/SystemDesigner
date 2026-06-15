from pathlib import Path

import pytest

from voice_interview.connectors.console_text import (
    ELIDED_TOOL_RESULT,
    prune_old_tool_results,
)
from voice_interview.orchestrator import InterviewOrchestrator
from voice_interview.protocol import load_plan
from voice_interview.report import build_interview_summary, write_interview_summary
from voice_interview.state import InterviewState

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def plan():
    return load_plan(REPO_ROOT)


def make_orchestrator(plan, tmp_path) -> InterviewOrchestrator:
    state = InterviewState(output_dir=str(tmp_path / "p"))
    orch = InterviewOrchestrator(plan, state, None)
    orch.set_mode("B")
    orch.set_system_fact("system_name", "Billing API")
    orch.set_system_fact("owning_team", "Payments")
    orch.set_system_fact("criticality_tier", "Tier 1")
    orch.set_system_fact("environments", "prod")
    orch.next_section()
    orch.record_answer(
        "system-identity.md", "System name", "Customer Billing API, the revenue system."
    )
    orch.mark_unknown(
        "system-identity.md", "Aliases", owner="Jane Doe", next_step="confirm by 2026-07-01"
    )
    orch.record_open_question("system-identity.md", "Is EU in scope?", "Platform PM")
    return orch


def test_summary_lists_coverage_followups_and_questions(plan, tmp_path) -> None:
    orch = make_orchestrator(plan, tmp_path)
    summary = build_interview_summary(orch.state, plan)

    assert "# Interview Summary — Billing API" in summary
    assert "B (In-house application)" in summary
    # Coverage row for the in-progress file.
    assert "| system-identity.md | in_progress | 2/" in summary
    # The TBD became an owned follow-up.
    assert "| system-identity.md | Aliases | Jane Doe | confirm by 2026-07-01 |" in summary
    assert "Is EU in scope? (owner: Platform PM" in summary


def test_summary_shows_resume_block_when_paused(plan, tmp_path) -> None:
    orch = make_orchestrator(plan, tmp_path)
    summary = build_interview_summary(orch.state, plan)
    assert "paused — resumable" in summary
    assert "--resume" in summary


def test_summary_completed_has_no_resume_block(plan, tmp_path) -> None:
    orch = make_orchestrator(plan, tmp_path)
    orch.end_interview(partial=True)
    summary = build_interview_summary(orch.state, plan)
    assert "Status:** completed" in summary
    assert "--resume" not in summary


def test_write_interview_summary_creates_file(plan, tmp_path) -> None:
    orch = make_orchestrator(plan, tmp_path)
    path = write_interview_summary(orch.state, plan, tmp_path / "p")
    assert path.name == "interview-summary.md"
    assert "Follow-ups owed" in path.read_text(encoding="utf-8")


def _round(i: int) -> list[dict]:
    return [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": f"t{i}", "name": "record_answer", "input": {}},
        ]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"t{i}", "content": f"big payload {i}" * 20},
        ]},
    ]


def test_prune_keeps_recent_rounds_and_elides_old_ones() -> None:
    messages = [{"role": "user", "content": "hello"}]
    for i in range(6):
        messages.extend(_round(i))

    prune_old_tool_results(messages, keep_rounds=3)

    results = [
        m["content"][0]
        for m in messages
        if m["role"] == "user" and isinstance(m["content"], list)
    ]
    assert len(results) == 6
    for block in results[:3]:
        assert block["content"] == ELIDED_TOOL_RESULT
    for i, block in enumerate(results[3:], start=3):
        assert f"big payload {i}" in block["content"]
    # Structure (ids and pairing) is untouched.
    assert results[0]["tool_use_id"] == "t0"


def test_prune_noop_on_short_histories() -> None:
    messages = [{"role": "user", "content": "hi"}, *_round(0), *_round(1)]
    prune_old_tool_results(messages, keep_rounds=3)
    results = [
        m["content"][0]
        for m in messages
        if m["role"] == "user" and isinstance(m["content"], list)
    ]
    assert all("big payload" in b["content"] for b in results)
