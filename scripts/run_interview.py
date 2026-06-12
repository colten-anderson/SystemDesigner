#!/usr/bin/env python3
"""Run a live SystemDesigner voice interview.

One command, one process:

    # Join a Microsoft Teams meeting (paste the invite's dial-in block):
    python scripts/run_interview.py --join "Dial in by phone +1 555-123-4567 ... Phone Conference ID: 123 456 789#"

    # Or with explicit flags / a dial string:
    python scripts/run_interview.py --join "+15551234567,,123456789#"
    python scripts/run_interview.py --join meeting --dial-number "+15551234567" --conference-id 123456789

    # Development modes (no telephony):
    python scripts/run_interview.py --text                 # type instead of talk
    python scripts/run_interview.py --local-audio          # local mic/speaker

    # Resume a dropped interview:
    python scripts/run_interview.py --resume portfolios/my-system/.interview-state.json

Provider keys live in the environment or a .env file (see .env.example).
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from voice_interview.config import InterviewConfig  # noqa: E402
from voice_interview.connectors.invite_parser import InviteParseError, parse_join_target  # noqa: E402
from voice_interview.orchestrator import InterviewOrchestrator  # noqa: E402
from voice_interview.protocol import load_plan  # noqa: E402
from voice_interview.state import (  # noqa: E402
    STATE_FILE_NAME,
    InterviewState,
    StateStore,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a SystemDesigner portfolio interview as a voice (or text) agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("\n\n", 1)[1],
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument(
        "--join",
        metavar="MEETING",
        help=(
            "Teams meeting to join: pasted invite text (the 'Dial in by phone' "
            "block) or a dial string like '+15551234567,,123456789#'."
        ),
    )
    target.add_argument("--text", action="store_true", help="Text console mode (no audio).")
    target.add_argument(
        "--local-audio", action="store_true", help="Local microphone/speaker mode."
    )
    parser.add_argument(
        "--resume",
        metavar="STATE_FILE",
        type=Path,
        help=f"Resume from a saved {STATE_FILE_NAME} state file.",
    )
    parser.add_argument(
        "--out",
        metavar="DIR",
        type=Path,
        help="Output portfolio directory (default: portfolios/interview-<timestamp>).",
    )
    parser.add_argument("--dial-number", help="Teams dial-in phone number (overrides parsing).")
    parser.add_argument("--conference-id", help="Teams phone conference ID (overrides parsing).")
    parser.add_argument(
        "--env-file", type=Path, help="Path to a .env file (default: ./.env if present)."
    )
    parser.add_argument(
        "--quality-gate",
        type=int,
        default=80,
        help="Validate the finished portfolio at this gate (default: 80; -1 to skip).",
    )
    return parser.parse_args(argv)


def default_out_dir() -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return REPO_ROOT / "portfolios" / f"interview-{stamp}"


def build_orchestrator(args: argparse.Namespace, config: InterviewConfig):
    plan = load_plan(REPO_ROOT)
    if args.resume:
        if not args.resume.is_file():
            print(f"ERROR: state file not found: {args.resume}")
            raise SystemExit(2)
        store = StateStore(args.resume)
        state = store.load()
        print(f"Resuming interview session {state.session_id} (phase: {state.phase}).")
    else:
        out_dir = args.out or default_out_dir()
        state = InterviewState(output_dir=str(out_dir))
        state.config_snapshot = config.snapshot()
        store = StateStore(Path(out_dir) / STATE_FILE_NAME)
        store.save(state)
    return plan, InterviewOrchestrator(plan, state, store)


def print_resume_hint_if_paused(orchestrator) -> int:
    if orchestrator.is_complete():
        return 0
    state_file = Path(orchestrator.state.output_dir) / STATE_FILE_NAME
    print(
        "\nThe interview was paused, not finished — every answer so far is "
        "saved. Continue any time with:\n"
        f"  python scripts/run_interview.py --resume {state_file}"
    )
    return 0


def validate_output(out_dir: Path, quality_gate: int) -> int:
    if quality_gate < 0:
        return 0
    print(f"\nValidating portfolio at quality gate {quality_gate}...")
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "validate_portfolio.py"),
            str(out_dir),
            "--quality-gate",
            str(quality_gate),
        ],
        cwd=REPO_ROOT,
    )
    return result.returncode


async def run_text_mode(args: argparse.Namespace, config: InterviewConfig) -> int:
    import os

    from voice_interview.connectors.console_text import run_text_interview
    from voice_interview.llm import AnthropicInterviewLLM, ScriptedLLM

    fake_script = os.environ.get("VOICE_INTERVIEW_FAKE_LLM")
    if fake_script:
        llm = ScriptedLLM.from_file(Path(fake_script))
    else:
        missing = config.missing_for_text()
        if missing:
            print(f"ERROR: text mode needs {', '.join(missing)} (see .env.example).")
            return 2
        try:
            llm = AnthropicInterviewLLM(model=config.llm_model)
        except RuntimeError as error:
            print(f"ERROR: {error}")
            return 2

    plan, orchestrator = build_orchestrator(args, config)
    orchestrator.state.join_target = {"kind": "console"}

    loop = asyncio.get_running_loop()

    async def input_fn() -> str | None:
        try:
            line = await loop.run_in_executor(None, lambda: sys.stdin.readline())
        except (EOFError, KeyboardInterrupt):
            return None
        if line == "":  # EOF
            return None
        return line.rstrip("\n")

    def output_fn(text: str) -> None:
        print(f"\n[interviewer] {text}\n> ", end="", flush=True)

    written = await run_text_interview(
        orchestrator, llm, input_fn=input_fn, output_fn=output_fn
    )
    out_dir = Path(orchestrator.state.output_dir)
    print(f"\n\nWrote {len(written)} portfolio files to {out_dir}")
    print_resume_hint_if_paused(orchestrator)
    return validate_output(out_dir, args.quality_gate)


async def run_voice_mode(args: argparse.Namespace, config: InterviewConfig, local: bool) -> int:
    missing = config.missing_for_local_audio() if local else config.missing_for_voice()
    if missing:
        print(
            "ERROR: voice mode needs these environment variables: "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill them in."
        )
        return 2

    join_target = None
    if not local:
        raw = args.join or (
            # On resume, fall back to the join target saved in the state file.
            None
        )
        if args.resume and not args.join:
            store = StateStore(args.resume)
            saved = store.load().join_target
            if saved.get("kind") == "teams_pstn" and saved.get("dial_number"):
                from voice_interview.connectors.base import JoinTarget

                join_target = JoinTarget(
                    kind="teams_pstn",
                    dial_number=saved["dial_number"],
                    conference_id=saved.get("conference_id"),
                )
        if join_target is None:
            try:
                join_target = parse_join_target(
                    raw or "",
                    dial_number=args.dial_number,
                    conference_id=args.conference_id,
                )
            except InviteParseError as error:
                print(f"ERROR: {error}")
                return 2

    try:
        from voice_interview.pipeline import run_voice_interview
    except ImportError as error:
        extra = "local-audio" if local else "voice"
        print(
            f"ERROR: voice dependencies are not installed ({error}).\n"
            f"Install them with: pip install -e '.[{extra}]'"
        )
        return 2

    plan, orchestrator = build_orchestrator(args, config)
    if join_target is not None:
        orchestrator.state.join_target = join_target.to_dict()
    else:
        orchestrator.state.join_target = {"kind": "local_audio"}

    written = await run_voice_interview(
        orchestrator, config, join_target=join_target, local_audio=local
    )
    out_dir = Path(orchestrator.state.output_dir)
    print(f"\nWrote {len(written)} portfolio files to {out_dir}")
    print_resume_hint_if_paused(orchestrator)
    return validate_output(out_dir, args.quality_gate)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not any([args.join, args.text, args.local_audio, args.resume]):
        print("ERROR: choose one of --join, --text, --local-audio, or --resume.")
        return 2

    config = InterviewConfig.from_env(args.env_file)

    if args.text:
        return asyncio.run(run_text_mode(args, config))

    if args.resume and not (args.join or args.local_audio):
        # Resume in the mode the interview was started in.
        saved_kind = ""
        if args.resume.is_file():
            saved_kind = StateStore(args.resume).load().join_target.get("kind", "")
        if saved_kind == "console":
            return asyncio.run(run_text_mode(args, config))
        return asyncio.run(run_voice_mode(args, config, local=saved_kind == "local_audio"))

    return asyncio.run(run_voice_mode(args, config, local=args.local_audio))


if __name__ == "__main__":
    sys.exit(main())
