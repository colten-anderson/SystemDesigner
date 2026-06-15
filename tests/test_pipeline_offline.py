"""Offline checks of the Pipecat-facing surface (no network, no providers).

These run wherever pipecat-ai core is installed (it is in CI); they are
skipped cleanly elsewhere so the stdlib-only workflow keeps working.
"""

from pathlib import Path

import pytest

pipecat = pytest.importorskip("pipecat")

from voice_interview.orchestrator import InterviewOrchestrator  # noqa: E402
from voice_interview.pipeline import _build_tools_schema, _build_transcript_loggers  # noqa: E402
from voice_interview.protocol import load_plan  # noqa: E402
from voice_interview.state import InterviewState  # noqa: E402
from voice_interview.tools import TOOL_DEFINITIONS  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_tools_schema_matches_definitions() -> None:
    schema = _build_tools_schema()
    functions = schema.standard_tools
    assert [f.name for f in functions] == [d["name"] for d in TOOL_DEFINITIONS]
    by_name = {f.name: f for f in functions}
    for definition in TOOL_DEFINITIONS:
        function = by_name[definition["name"]]
        assert function.description == definition["description"]
        assert function.properties == definition["input_schema"].get("properties", {})
        assert function.required == definition["input_schema"].get("required", [])


def test_universal_context_accepts_our_shapes() -> None:
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
    )

    plan = load_plan(REPO_ROOT)
    state = InterviewState(output_dir="unused")
    orch = InterviewOrchestrator(plan, state, None)
    context = LLMContext(
        messages=[
            {"role": "system", "content": orch.system_prompt()},
            {"role": "assistant", "content": orch.opening_message()},
        ],
        tools=_build_tools_schema(),
    )
    pair = LLMContextAggregatorPair(context)
    assert pair.user() is not None
    assert pair.assistant() is not None


@pytest.mark.parametrize("resuming", [False, True])
def test_transcript_loggers_record_user_and_assistant(tmp_path, resuming) -> None:
    import asyncio

    from pipecat.frames.frames import (
        LLMFullResponseEndFrame,
        TextFrame,
        TranscriptionFrame,
    )
    from pipecat.processors.frame_processor import FrameDirection

    plan = load_plan(REPO_ROOT)
    state = InterviewState(output_dir=str(tmp_path / "p"))
    if resuming:
        state.mode = "B"
    orch = InterviewOrchestrator(plan, state, None)
    user_log, assistant_log = _build_transcript_loggers(orch)

    async def noop_push(frame, direction=FrameDirection.DOWNSTREAM):
        return None

    # Drive the processors directly; pushing is stubbed since there is no
    # pipeline attached.
    user_log.push_frame = noop_push
    assistant_log.push_frame = noop_push

    async def drive():
        await user_log.process_frame(
            TranscriptionFrame(text="we use postgres", user_id="u1", timestamp="t"),
            FrameDirection.DOWNSTREAM,
        )
        # Assistant text streams in chunks, then the response ends.
        await assistant_log.process_frame(TextFrame(text="Got it, "), FrameDirection.DOWNSTREAM)
        await assistant_log.process_frame(TextFrame(text="recording that."), FrameDirection.DOWNSTREAM)
        await assistant_log.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
        # User speech passing the assistant logger must not be logged twice.
        await assistant_log.process_frame(
            TranscriptionFrame(text="echo", user_id="u1", timestamp="t"),
            FrameDirection.DOWNSTREAM,
        )

    asyncio.run(drive())

    entries = [(t["role"], t["text"]) for t in state.transcript]
    assert ("user", "we use postgres") in entries
    assert ("assistant", "Got it, recording that.") in entries
    # The user speech echoing through the assistant logger was not re-logged:
    # exactly one user and one assistant entry exist.
    assert len(state.transcript) == 2
    assert all(text != "echo" for _, text in entries)
