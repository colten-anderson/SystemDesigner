from pathlib import Path
import json
import os
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "run_interview.py"


def run_cli(*args: str, stdin: str = "", env_extra: dict | None = None):
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        input=stdin,
        capture_output=True,
        env=env,
        check=False,
    )


def test_requires_a_mode() -> None:
    result = run_cli()
    assert result.returncode == 2
    assert "--join, --text, --local-audio, or --resume" in result.stdout


def test_join_and_text_are_mutually_exclusive() -> None:
    result = run_cli("--join", "x", "--text")
    assert result.returncode == 2


def test_text_mode_without_key_gives_actionable_error(tmp_path: Path) -> None:
    result = run_cli("--text", "--out", str(tmp_path / "p"))
    assert result.returncode == 2
    assert "ANTHROPIC_API_KEY" in result.stdout


def test_bare_teams_url_rejected(tmp_path: Path) -> None:
    result = run_cli(
        "--join",
        "https://teams.microsoft.com/l/meetup-join/19%3ameeting_x/0",
        "--out",
        str(tmp_path / "p"),
        env_extra={
            "ANTHROPIC_API_KEY": "x",
            "DEEPGRAM_API_KEY": "x",
            "CARTESIA_API_KEY": "x",
            "DAILY_API_KEY": "x",
        },
    )
    assert result.returncode == 2
    assert "Dial in by phone" in result.stdout


def test_voice_mode_without_keys_lists_missing(tmp_path: Path) -> None:
    result = run_cli(
        "--join", "+15551234567,,123#", "--out", str(tmp_path / "p"),
        env_extra={"DEEPGRAM_API_KEY": "", "CARTESIA_API_KEY": "", "DAILY_API_KEY": ""},
    )
    assert result.returncode == 2
    assert "DAILY_API_KEY" in result.stdout


def test_resume_with_missing_state_file(tmp_path: Path) -> None:
    result = run_cli(
        "--resume", str(tmp_path / "nope.json"),
        env_extra={"VOICE_INTERVIEW_FAKE_LLM": "unused"},
    )
    assert result.returncode == 2


def test_text_mode_with_scripted_llm_end_to_end(tmp_path: Path) -> None:
    """Subprocess E2E: scripted LLM drives a partial interview; portfolio is
    written, state persists, and the validator gate passes."""

    script = [
        {"tool_calls": [{"name": "set_mode", "arguments": {"mode": "B"}}]},
        {
            "tool_calls": [
                {"name": "set_system_fact", "arguments": {"key": "system_name", "value": "Billing API"}},
                {"name": "set_system_fact", "arguments": {"key": "owning_team", "value": "Payments"}},
                {"name": "set_system_fact", "arguments": {"key": "criticality_tier", "value": "Tier 1"}},
                {"name": "set_system_fact", "arguments": {"key": "environments", "value": "prod"}},
                {"name": "next_section", "arguments": {}},
            ]
        },
        {
            "text": "What's the official name?",
            "tool_calls": [
                {
                    "name": "record_answer",
                    "arguments": {
                        "file": "system-identity.md",
                        "field": "System name",
                        "value": "Customer Billing API, the revenue-critical billing service.",
                    },
                }
            ],
        },
        {"text": "Tell me about aliases."},
    ]
    script_path = tmp_path / "script.json"
    script_path.write_text(json.dumps(script), encoding="utf-8")
    out_dir = tmp_path / "portfolio"

    result = run_cli(
        "--text",
        "--out",
        str(out_dir),
        stdin="hello\nit is the billing api\n",
        env_extra={"VOICE_INTERVIEW_FAKE_LLM": str(script_path)},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[interviewer]" in result.stdout
    assert "Wrote 10 portfolio files" in result.stdout
    assert "Quality score" in result.stdout
    # Stdin ran out mid-interview, so the run paused (resumable), with a hint.
    assert "--resume" in result.stdout

    assert (out_dir / ".interview-state.json").exists()
    state = json.loads((out_dir / ".interview-state.json").read_text(encoding="utf-8"))
    assert state["phase"] == "SECTIONS"  # paused, not finalized
    assert state["system_facts"]["system_name"] == "Billing API"

    identity = (out_dir / "system-identity.md").read_text(encoding="utf-8")
    assert "Customer Billing API" in identity


def test_text_mode_resume_continues_session(tmp_path: Path) -> None:
    out_dir = tmp_path / "portfolio"

    # First run: select the mode, then hang up immediately (EOF after one line).
    script1 = [
        {"tool_calls": [{"name": "set_mode", "arguments": {"mode": "C"}}]},
        {"text": "What's the system name?"},
    ]
    script1_path = tmp_path / "s1.json"
    script1_path.write_text(json.dumps(script1), encoding="utf-8")
    first = run_cli(
        "--text", "--out", str(out_dir),
        stdin="hello\nshared platform\n",
        env_extra={"VOICE_INTERVIEW_FAKE_LLM": str(script1_path), },
    )
    assert first.returncode == 0, first.stdout + first.stderr

    state_file = out_dir / ".interview-state.json"
    saved = json.loads(state_file.read_text(encoding="utf-8"))
    assert saved["mode"] == "C"
    assert saved["phase"] == "CORE_FACTS"  # paused mid-way, resumable
    session_id = saved["session_id"]

    # Resume: the same session continues with a "welcome back" opening.
    script2 = [{"text": "Welcome back."}]
    script2_path = tmp_path / "s2.json"
    script2_path.write_text(json.dumps(script2), encoding="utf-8")
    second = run_cli(
        "--resume", str(state_file),
        stdin="",
        env_extra={"VOICE_INTERVIEW_FAKE_LLM": str(script2_path)},
    )
    assert second.returncode == 0, second.stdout + second.stderr
    assert "Resuming interview session" in second.stdout
    assert "Hello again" in second.stdout  # resume-aware opening
    resumed = json.loads(state_file.read_text(encoding="utf-8"))
    assert resumed["session_id"] == session_id
    assert resumed["mode"] == "C"  # progress survived the round trip
