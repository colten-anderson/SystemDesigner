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
from ..tools import TOOL_DEFINITIONS, dispatch_tool, tool_result_text

# Guards against a misbehaving model looping on tools without ever finishing.
MAX_TOOL_ROUNDS_PER_TURN = 60


async def run_text_interview(
    orchestrator: InterviewOrchestrator,
    llm: InterviewLLM,
    *,
    input_fn: Callable[[], Awaitable[str | None]],
    output_fn: Callable[[str], None],
) -> list[Path]:
    """Run the interview loop until completion or end-of-input.

    ``input_fn`` returns the next user utterance or ``None`` on end-of-input
    (hang-up equivalent). Returns the list of written portfolio files.
    """

    messages: list[dict] = []

    opening = orchestrator.opening_message()
    output_fn(opening)
    orchestrator.on_assistant_text(opening)

    while not orchestrator.is_complete():
        user_text = await input_fn()
        if user_text is None:
            # The "call dropped / user left" path: save partial progress.
            if not orchestrator.is_complete():
                orchestrator.end_interview(partial=True)
            break
        user_text = user_text.strip()
        if not user_text:
            continue
        orchestrator.on_user_transcript(user_text)
        messages.append({"role": "user", "content": user_text})

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

            if orchestrator.is_complete():
                break

    written = write_portfolio(
        orchestrator.state, orchestrator.plan, Path(orchestrator.state.output_dir)
    )
    return written
