"""Text-console interview loop: same orchestrator and tools, no audio stack.

Used for development (``--text``), demos without telephony, and the offline
end-to-end tests (with a ScriptedLLM). The loop mirrors the voice path: the
agent leads, every piece of progress goes through the orchestrator tools, and
ending early (EOF / Ctrl-D) saves partial progress and still writes the
portfolio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Awaitable, Callable

from ..llm import InterviewLLM
from ..markdown_writer import write_portfolio
from ..orchestrator import InterviewOrchestrator
from ..report import write_interview_summary
from ..state import resume_digest
from ..tools import TOOL_DEFINITIONS, dispatch_tool, tool_result_text

# Guards against a misbehaving model looping on tools without ever finishing.
MAX_TOOL_ROUNDS_PER_TURN = 60

# Keep full tool-result JSON only for the most recent rounds; older results
# are already captured in the state file, so eliding them saves real input
# tokens on every subsequent turn of a long interview.
TOOL_RESULT_KEEP_ROUNDS = 3
ELIDED_TOOL_RESULT = '{"status": "ok", "note": "elided; recorded in interview state"}'


def prune_old_tool_results(messages: list[dict], keep_rounds: int = TOOL_RESULT_KEEP_ROUNDS) -> None:
    """Replace the content of all but the last N tool-result rounds in place.

    The message structure (tool_use/tool_result pairing) is preserved — only
    the result payload text is shortened, which is safe for the API.
    """

    result_rounds = [
        message
        for message in messages
        if message["role"] == "user"
        and isinstance(message["content"], list)
        and any(block.get("type") == "tool_result" for block in message["content"])
    ]
    for message in result_rounds[:-keep_rounds] if keep_rounds else result_rounds:
        for block in message["content"]:
            if block.get("type") == "tool_result":
                block["content"] = ELIDED_TOOL_RESULT


async def run_text_interview(
    orchestrator: InterviewOrchestrator,
    llm: InterviewLLM,
    *,
    input_fn: Callable[[], Awaitable[str | None]],
    output_fn: Callable[[str], None],
) -> list[Path]:
    """Run the interview loop until completion, pause, or end-of-input.

    ``input_fn`` returns the next user utterance or ``None`` on end-of-input.
    End-of-input and the pause_interview tool leave the state RESUMABLE (only
    an explicit end_interview finalizes it); the partial portfolio is written
    either way. Returns the list of written portfolio files.
    """

    messages: list[dict] = []
    if orchestrator.is_resuming():
        # Re-anchor the model with where the previous call left off.
        messages.append(
            {
                "role": "user",
                "content": "<session-restored>\n"
                + resume_digest(orchestrator.state, orchestrator.plan)
                + "\n</session-restored>",
            }
        )

    opening = orchestrator.opening_message()
    output_fn(opening)
    orchestrator.on_assistant_text(opening)
    if messages:
        # Resume path: the digest (a user message) comes first, so the spoken
        # opening can be part of the history. Fresh runs must start with a
        # user message, so the opening stays out of the API history there.
        messages.append({"role": "assistant", "content": opening})

    while not orchestrator.is_complete() and not orchestrator.pause_requested:
        user_text = await input_fn()
        if user_text is None:
            # Call dropped / user left: keep the state resumable.
            orchestrator.pause_requested = True
            break
        user_text = user_text.strip()
        if not user_text:
            continue
        orchestrator.on_user_transcript(user_text)
        messages.append({"role": "user", "content": user_text})
        prune_old_tool_results(messages)

        for _ in range(MAX_TOOL_ROUNDS_PER_TURN):
            turn = await llm.step(orchestrator.system_prompt(), messages, TOOL_DEFINITIONS)

            assistant_content: list[dict] = []
            if turn.text:
                output_fn(turn.text)
                orchestrator.on_assistant_text(turn.text)
                assistant_content.append({"type": "text", "text": turn.text})
            for call in turn.tool_calls:
                assistant_content.append(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.arguments,
                    }
                )
            if assistant_content:
                messages.append({"role": "assistant", "content": assistant_content})

            if not turn.tool_calls:
                break

            results = []
            for call in turn.tool_calls:
                result = dispatch_tool(orchestrator, call.name, call.arguments)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": tool_result_text(result),
                    }
                )
            messages.append({"role": "user", "content": results})

            if orchestrator.is_complete() or orchestrator.pause_requested:
                break

    # The writer renders unrecorded fields as TBDs without mutating state, so
    # a paused interview produces a complete partial portfolio AND remains
    # resumable from the saved state file.
    out_dir = Path(orchestrator.state.output_dir)
    written = write_portfolio(orchestrator.state, orchestrator.plan, out_dir)
    write_interview_summary(orchestrator.state, orchestrator.plan, out_dir)
    return written
