"""Pipecat voice pipeline: STT -> Claude (with interview tools) -> TTS.

All Pipecat surface area lives here and in the two audio connectors, so a
Pipecat upgrade or a provider swap never touches the orchestrator. The LLM
makes progress only through the orchestrator's tools (registered as Pipecat
function calls); the same handlers back the text mode, so the orchestrator
test suite covers this path's decision logic.

Written against pipecat-ai 1.3 (universal ``LLMContext`` +
``LLMContextAggregatorPair``; interruption handling is built in).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from .config import InterviewConfig
from .connectors.base import JoinTarget, MeetingConnector
from .markdown_writer import write_portfolio
from .orchestrator import InterviewOrchestrator
from .tools import TOOL_DEFINITIONS, dispatch_tool

# Give the TTS time to speak the goodbye before the pipeline shuts down.
END_GRACE_PERIOD_S = 6.0


def _print_progress(tool_name: str, result: dict, orchestrator) -> None:
    """Console progress lines so the operator can follow the call live."""

    if result.get("status") == "error":
        return
    if tool_name in ("next_section", "skip_section"):
        section = result.get("section")
        if section:
            done = orchestrator.state.section_cursor
            total = len(orchestrator.state.section_order)
            print(f"[progress] section {done + 1}/{total}: {section['file']}")
        else:
            print("[progress] all sections complete — wrapping up")
    elif tool_name == "set_mode":
        print(f"[progress] mode selected: {result.get('mode')} ({result.get('mode_label')})")
    elif tool_name == "end_interview":
        print("[progress] interview ended; writing portfolio")
    elif tool_name == "pause_interview":
        print("[progress] interview paused; progress saved")


def _build_tools_schema():
    from pipecat.adapters.schemas.function_schema import FunctionSchema
    from pipecat.adapters.schemas.tools_schema import ToolsSchema

    functions = []
    for definition in TOOL_DEFINITIONS:
        schema = definition["input_schema"]
        functions.append(
            FunctionSchema(
                name=definition["name"],
                description=definition["description"],
                properties=schema.get("properties", {}),
                required=schema.get("required", []),
            )
        )
    return ToolsSchema(standard_tools=functions)


def _register_tools(llm, task, orchestrator: InterviewOrchestrator) -> None:
    from pipecat.frames.frames import EndFrame

    async def _finish_after_grace() -> None:
        await asyncio.sleep(END_GRACE_PERIOD_S)
        await task.queue_frame(EndFrame())

    def make_handler(tool_name: str):
        async def handler(params):  # pipecat FunctionCallParams
            result = dispatch_tool(orchestrator, tool_name, params.arguments or {})
            await params.result_callback(result)
            _print_progress(tool_name, result, orchestrator)
            if orchestrator.is_complete() or orchestrator.pause_requested:
                # Let the goodbye line get spoken, then stop the pipeline.
                # A pause leaves the state file resumable; only end_interview
                # finalizes the interview.
                asyncio.create_task(_finish_after_grace())

        return handler

    for definition in TOOL_DEFINITIONS:
        llm.register_function(definition["name"], make_handler(definition["name"]))


def _build_transcript_loggers(orchestrator: InterviewOrchestrator):
    """Two small frame processors that feed the persisted transcript log.

    The user logger (placed after STT) records final ``TranscriptionFrame``s;
    the assistant logger (placed after the LLM) buffers streamed ``TextFrame``
    chunks into one transcript entry per response.
    """

    from pipecat.frames.frames import (
        LLMFullResponseEndFrame,
        TextFrame,
        TranscriptionFrame,
    )
    from pipecat.processors.frame_processor import FrameProcessor

    class UserTranscriptLogger(FrameProcessor):
        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, TranscriptionFrame) and frame.text.strip():
                orchestrator.on_user_transcript(frame.text.strip())
            await self.push_frame(frame, direction)

    class AssistantTranscriptLogger(FrameProcessor):
        def __init__(self):
            super().__init__()
            self._buffer: list[str] = []

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)
            if isinstance(frame, TranscriptionFrame):
                pass  # user speech echoing through; not assistant output
            elif isinstance(frame, TextFrame):
                self._buffer.append(frame.text)
            elif isinstance(frame, LLMFullResponseEndFrame):
                text = "".join(self._buffer).strip()
                self._buffer.clear()
                if text:
                    orchestrator.on_assistant_text(text)
            await self.push_frame(frame, direction)

    return UserTranscriptLogger(), AssistantTranscriptLogger()


def _build_interview_task(transport, orchestrator: InterviewOrchestrator, config: InterviewConfig):
    """Assemble the STT -> LLM(tools) -> TTS pipeline on any transport.

    Shared by every meeting connector (Daily, Twilio, local audio) — adding a
    platform never duplicates this. Returns ``(task, speak_opening)``.
    """

    from pipecat.frames.frames import TTSSpeakFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import (
        LLMContextAggregatorPair,
    )
    from pipecat.services.anthropic.llm import AnthropicLLMService
    from pipecat.services.cartesia.tts import CartesiaTTSService
    from pipecat.services.deepgram.stt import DeepgramSTTService

    stt = DeepgramSTTService(api_key=config.deepgram_api_key)
    tts = CartesiaTTSService(
        api_key=config.cartesia_api_key, voice_id=config.cartesia_voice_id
    )
    llm = AnthropicLLMService(
        api_key=config.anthropic_api_key,
        model=config.llm_model,
        params=AnthropicLLMService.InputParams(
            # Hour-long interviews re-send the same growing prefix every turn;
            # caching cuts that input cost by ~90% after the first turn.
            enable_prompt_caching=True,
            # Spoken turns are short; this bounds runaway-turn cost.
            max_tokens=config.llm_max_tokens,
        ),
    )

    opening = orchestrator.opening_message()
    context_messages: list[dict] = [
        {"role": "system", "content": orchestrator.system_prompt()},
    ]
    if orchestrator.is_resuming():
        # Re-anchor the model with where the previous call left off.
        from .state import resume_digest

        context_messages.append(
            {
                "role": "user",
                "content": "<session-restored>\n"
                + resume_digest(orchestrator.state, orchestrator.plan)
                + "\n</session-restored>",
            }
        )
    context_messages.append({"role": "assistant", "content": opening})
    context = LLMContext(messages=context_messages, tools=_build_tools_schema())
    context_aggregator = LLMContextAggregatorPair(context)
    user_log, assistant_log = _build_transcript_loggers(orchestrator)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_log,
            context_aggregator.user(),
            llm,
            assistant_log,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(pipeline, params=PipelineParams())
    _register_tools(llm, task, orchestrator)

    spoke_opening = False

    async def speak_opening() -> None:
        nonlocal spoke_opening
        if spoke_opening:
            return
        spoke_opening = True
        orchestrator.on_assistant_text(opening)
        await task.queue_frame(TTSSpeakFrame(opening))

    return task, speak_opening


async def _run_twilio_flow(
    orchestrator: InterviewOrchestrator, config: InterviewConfig, join_target: JoinTarget
) -> None:
    from pipecat.frames.frames import EndFrame
    from pipecat.pipeline.runner import PipelineRunner

    from .connectors.twilio_dialout import TwilioDialOutConnector

    connector = TwilioDialOutConnector(config, join_target)

    async def run_with_transport(transport) -> None:
        task, speak_opening = _build_interview_task(transport, orchestrator, config)

        # The media stream attaches once the call is answered and SendDigits
        # has typed the conference ID; greet shortly after.
        asyncio.get_running_loop().call_later(
            2.0, lambda: asyncio.create_task(speak_opening())
        )

        @transport.event_handler("on_client_disconnected")
        async def on_client_disconnected(transport, client):
            # Caller hung up: keep the session resumable.
            if not orchestrator.is_complete():
                orchestrator.pause_interview()
            await task.queue_frame(EndFrame())

        await PipelineRunner().run(task)

    await connector.serve(run_with_transport)


async def run_voice_interview(
    orchestrator: InterviewOrchestrator,
    config: InterviewConfig,
    *,
    join_target: JoinTarget | None,
    local_audio: bool = False,
) -> list[Path]:
    """Join the meeting, run the interview, and write the portfolio files."""

    if not local_audio and config.telephony_provider == "twilio":
        assert join_target is not None
        await _run_twilio_flow(orchestrator, config, join_target)
        return _write_outputs(orchestrator)

    from pipecat.frames.frames import EndFrame
    from pipecat.pipeline.runner import PipelineRunner

    connector: MeetingConnector
    if local_audio:
        from .connectors.local_audio import LocalAudioConnector

        connector = LocalAudioConnector(config)
    else:
        from .connectors.teams_dialin import TeamsDialInConnector

        assert join_target is not None
        connector = TeamsDialInConnector(config, join_target)

    transport = await connector.create_transport()
    task, speak_opening = _build_interview_task(transport, orchestrator, config)

    if local_audio:
        # No remote participants: greet as soon as the pipeline starts.
        asyncio.get_running_loop().call_later(
            1.0, lambda: asyncio.create_task(speak_opening())
        )
    else:
        # Greet once the dialed call is answered and the DTMF dance is done
        # (the conference-ID entry itself is handled by the connector).
        @transport.event_handler("on_dialout_answered")
        async def greet_on_answer(transport, data):
            await asyncio.sleep(
                config.dtmf_initial_delay_s + config.dtmf_confirm_delay_s + 2.0
            )
            await speak_opening()

        async def on_call_ended(reason: str) -> None:
            # Dropped call: save partial progress and stop; the state file
            # allows continuing later with --resume.
            if not orchestrator.is_complete():
                orchestrator.pause_interview()
            await task.queue_frame(EndFrame())

        connector.on_call_ended = on_call_ended

    runner = PipelineRunner()
    try:
        await connector.connect()
        await runner.run(task)
    finally:
        await connector.disconnect()

    return _write_outputs(orchestrator)


def _write_outputs(orchestrator: InterviewOrchestrator) -> list[Path]:
    # Always produce the portfolio. The writer renders unrecorded fields as
    # TBDs without mutating state, so a dropped or paused call yields a
    # complete partial portfolio AND remains resumable; only an explicit
    # end_interview (by the agent) finalizes the state.
    if not orchestrator.is_complete():
        orchestrator.pause_interview()
    from .report import write_interview_summary

    out_dir = Path(orchestrator.state.output_dir)
    written = write_portfolio(orchestrator.state, orchestrator.plan, out_dir)
    write_interview_summary(orchestrator.state, orchestrator.plan, out_dir)
    return written
