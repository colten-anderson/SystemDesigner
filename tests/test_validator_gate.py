"""End-to-end: a scripted interview through the console loop must produce a
portfolio that passes scripts/validate_portfolio.py --quality-gate 80."""

from pathlib import Path
import asyncio
import subprocess
import sys

import pytest

from voice_interview.connectors.console_text import run_text_interview
from voice_interview.llm import ScriptedLLM
from voice_interview.orchestrator import InterviewOrchestrator
from voice_interview.protocol import REQUIRED_FILES, load_plan
from voice_interview.state import InterviewState, StateStore

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPO_ROOT / "scripts" / "validate_portfolio.py"


def build_full_interview_script(plan) -> list[dict]:
    """Generate the scripted LLM turns for a complete interview."""

    turns: list[dict] = [
        {"text": "Got it, mode B.", "tool_calls": [{"name": "set_mode", "arguments": {"mode": "B"}}]},
        {
            "text": "Recording the basics.",
            "tool_calls": [
                {"name": "set_system_fact", "arguments": {"key": "system_name", "value": "Customer Billing API"}},
                {"name": "set_system_fact", "arguments": {"key": "owning_team", "value": "Payments Platform"}},
                {"name": "set_system_fact", "arguments": {"key": "criticality_tier", "value": "Tier 1"}},
                {"name": "set_system_fact", "arguments": {"key": "environments", "value": "dev, staging, prod"}},
            ],
        },
        {"tool_calls": [{"name": "next_section", "arguments": {}}]},
    ]
    for index, section in enumerate(plan.sections):
        calls = []
        for field_index, field in enumerate(section.output_fields):
            if field_index % 6 == 5:
                calls.append(
                    {
                        "name": "mark_unknown",
                        "arguments": {
                            "file": section.file_name,
                            "field": field,
                            "owner": "Jane Doe",
                            "next_step": "confirm by 2026-07-15",
                        },
                    }
                )
            else:
                calls.append(
                    {
                        "name": "record_answer",
                        "arguments": {
                            "file": section.file_name,
                            "field": field,
                            "value": (
                                f"Concrete interview answer for {field}: owned by "
                                "Payments Platform, reviewed quarterly, runbook RB-42."
                            ),
                        },
                    }
                )
        calls.append(
            {
                "name": "set_file_summary",
                "arguments": {
                    "file": section.file_name,
                    "summary": (
                        f"The team walked through {section.title.lower()} in detail, "
                        "naming owners, environments, and current operational practice."
                    ),
                },
            }
        )
        calls.append({"name": "next_section", "arguments": {}})
        turns.append({"text": f"Thanks, moving on ({index + 1}/10).", "tool_calls": calls})
    turns.append(
        {
            "text": "That's everything — thank you all!",
            "tool_calls": [{"name": "end_interview", "arguments": {"partial": False}}],
        }
    )
    return turns


async def _drive(orchestrator, llm, user_lines: list[str | None]):
    lines = iter(user_lines)

    async def input_fn():
        try:
            return next(lines)
        except StopIteration:
            return None

    outputs: list[str] = []
    written = await run_text_interview(
        orchestrator, llm, input_fn=input_fn, output_fn=outputs.append
    )
    return written, outputs


def run_validator(portfolio: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(portfolio), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.fixture(scope="module")
def plan():
    return load_plan(REPO_ROOT)


def test_full_scripted_interview_passes_quality_gate_80(plan, tmp_path) -> None:
    out_dir = tmp_path / "portfolio"
    state = InterviewState(output_dir=str(out_dir))
    store = StateStore(out_dir / ".interview-state.json")
    orchestrator = InterviewOrchestrator(plan, state, store)
    llm = ScriptedLLM(build_full_interview_script(plan))

    written, outputs = asyncio.run(_drive(orchestrator, llm, ["hello, we're ready"]))

    assert orchestrator.is_complete()
    assert [p.name for p in written] == REQUIRED_FILES
    # The agent introduced itself and led the conversation.
    assert "SystemDesigner interviewer" in outputs[0]

    result = run_validator(out_dir, "--quality-gate", "80")
    assert result.returncode == 0, result.stdout
    assert "Quality score" in result.stdout


def _hangup_script() -> list[dict]:
    """Mode + core facts + the first section's first field, then nothing."""

    return [
        {"tool_calls": [{"name": "set_mode", "arguments": {"mode": "A"}}]},
        {
            "tool_calls": [
                {"name": "set_system_fact", "arguments": {"key": "system_name", "value": "Exchange Online"}},
                {"name": "set_system_fact", "arguments": {"key": "owning_team", "value": "Messaging"}},
                {"name": "set_system_fact", "arguments": {"key": "criticality_tier", "value": "Tier 0"}},
                {"name": "set_system_fact", "arguments": {"key": "environments", "value": "prod tenant"}},
                {"name": "next_section", "arguments": {}},
            ]
        },
        {
            "text": "What is the official system name?",
            "tool_calls": [
                {
                    "name": "record_answer",
                    "arguments": {
                        "file": "system-identity.md",
                        "field": "System name",
                        "value": "Microsoft Exchange Online, the corporate mail platform.",
                    },
                }
            ],
        },
        {"text": "And which aliases are in use?"},
    ]


def test_early_hangup_writes_partial_and_stays_resumable(plan, tmp_path) -> None:
    out_dir = tmp_path / "portfolio"
    state = InterviewState(output_dir=str(out_dir))
    store = StateStore(out_dir / ".interview-state.json")
    orchestrator = InterviewOrchestrator(plan, state, store)
    llm = ScriptedLLM(_hangup_script())

    # The user "hangs up" (input_fn returns None) mid-section.
    written, _ = asyncio.run(_drive(orchestrator, llm, ["hi", "it's exchange", None]))

    # A hang-up pauses; it does NOT finalize — the session stays resumable.
    assert not orchestrator.is_complete()
    assert orchestrator.pause_requested
    assert state.phase == "SECTIONS"
    assert len(written) == 10
    assert (out_dir / ".interview-state.json").exists()

    # The partial portfolio still passes the gate (unrecorded fields are
    # rendered as TBDs with the owning team, without mutating state).
    result = run_validator(out_dir, "--quality-gate", "80")
    assert result.returncode == 0, result.stdout
    identity = (out_dir / "system-identity.md").read_text(encoding="utf-8")
    assert "Microsoft Exchange Online" in identity
    assert "TBD (owner:" in identity
    # State was not TBD-filled: only the one real answer is recorded.
    assert list(state.files["system-identity.md"].fields) == ["System name"]


def test_hangup_then_resume_finishes_the_interview(plan, tmp_path) -> None:
    out_dir = tmp_path / "portfolio"
    store = StateStore(out_dir / ".interview-state.json")

    # Call 1: drops mid-way through the first section.
    state = InterviewState(output_dir=str(out_dir))
    first = InterviewOrchestrator(plan, state, store)
    asyncio.run(_drive(first, ScriptedLLM(_hangup_script()), ["hi", "exchange", None]))
    assert not first.is_complete()

    # Call 2: resume from the saved state file and finish everything.
    resumed_state = store.load()
    second = InterviewOrchestrator(plan, resumed_state, store)
    assert second.is_resuming()
    assert "Resuming" in second.opening_message() or "Hello again" in second.opening_message()

    finish_turns: list[dict] = []
    for section in plan.sections:
        calls = []
        for field in section.output_fields:
            if section.file_name == "system-identity.md" and field == "System name":
                continue  # already answered before the drop
            calls.append(
                {
                    "name": "record_answer",
                    "arguments": {
                        "file": section.file_name,
                        "field": field,
                        "value": f"Resumed-session answer for {field} with owner and details.",
                    },
                }
            )
        calls.append(
            {
                "name": "set_file_summary",
                "arguments": {
                    "file": section.file_name,
                    "summary": f"Recap of {section.title} confirmed by the team after resuming.",
                },
            }
        )
        calls.append({"name": "next_section", "arguments": {}})
        finish_turns.append({"tool_calls": calls})
    finish_turns.append(
        {
            "text": "All done, thanks everyone!",
            "tool_calls": [{"name": "end_interview", "arguments": {"partial": False}}],
        }
    )

    written, outputs = asyncio.run(
        _drive(second, ScriptedLLM(finish_turns), ["we're back"])
    )

    assert second.is_complete()
    # The resumed session continued the SAME session, from the saved cursor.
    assert resumed_state.session_id == state.session_id
    assert len(written) == 10
    # The resume opening re-anchored the conversation.
    assert any("Hello again" in line for line in outputs)

    result = run_validator(out_dir, "--quality-gate", "80")
    assert result.returncode == 0, result.stdout
    identity = (out_dir / "system-identity.md").read_text(encoding="utf-8")
    assert "Microsoft Exchange Online" in identity  # pre-drop answer survived


def test_gated_next_section_steers_scripted_llm_error_path(plan, tmp_path) -> None:
    # If the LLM tries to advance early, it gets a corrective error result and
    # the interview does not advance.
    out_dir = tmp_path / "portfolio"
    state = InterviewState(output_dir=str(out_dir))
    orchestrator = InterviewOrchestrator(plan, state, StateStore(out_dir / "s.json"))
    script = [
        {"tool_calls": [{"name": "next_section", "arguments": {}}]},
        {"text": "Right, I need the mode first. Which mode is it?"},
    ]
    llm = ScriptedLLM(script)
    written, _ = asyncio.run(_drive(orchestrator, llm, ["hello", None]))
    # Never advanced into sections; the hang-up paused without mutating state.
    assert state.mode is None
    assert not state.files[REQUIRED_FILES[0]].fields
    # The portfolio is still rendered (every field as a defensive TBD).
    assert len(written) == 10
