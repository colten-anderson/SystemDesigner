"""LLM boundary for the text-mode interview loop.

The voice path drives Claude through Pipecat's AnthropicLLMService; this
module covers the ``--text`` console mode and tests. Both paths share the same
orchestrator tool handlers, so orchestrator tests cover the voice path's
decision logic too. ``ScriptedLLM`` replays a canned turn sequence and is the
offline test double (also reachable from the CLI via the
``VOICE_INTERVIEW_FAKE_LLM`` env hook).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
import json


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass(frozen=True)
class LLMTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class InterviewLLM(Protocol):
    async def step(self, system: str, messages: list[dict], tools: list[dict]) -> LLMTurn:
        """Run one model turn over the Anthropic-format message history."""
        ...


class AnthropicInterviewLLM:
    """Real Claude-backed implementation (lazy import; needs ANTHROPIC_API_KEY)."""

    def __init__(self, model: str, api_key: str | None = None, max_tokens: int = 1024):
        try:
            import anthropic
        except ImportError as error:  # pragma: no cover - environment-dependent
            raise RuntimeError(
                "The 'anthropic' package is required for text mode. "
                "Install it with: pip install -e '.[text]'"
            ) from error
        kwargs = {"api_key": api_key} if api_key else {}
        self._client = anthropic.AsyncAnthropic(**kwargs)
        self.model = model
        self.max_tokens = max_tokens

    async def step(self, system: str, messages: list[dict], tools: list[dict]) -> LLMTurn:
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system,
                    # The system prompt is stable for the whole interview.
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=tools,
            messages=messages,
        )
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
        return LLMTurn(text=" ".join(text_parts).strip(), tool_calls=tool_calls)


class ScriptedLLM:
    """Replays a fixed sequence of turns. Used by tests and the CLI fake hook.

    Script format (JSON list):
        [{"text": "...", "tool_calls": [{"name": "...", "arguments": {...}}]}, ...]
    """

    def __init__(self, turns: list[dict]):
        self._turns = list(turns)
        self._cursor = 0

    @classmethod
    def from_file(cls, path: Path) -> "ScriptedLLM":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    async def step(self, system: str, messages: list[dict], tools: list[dict]) -> LLMTurn:
        if self._cursor >= len(self._turns):
            return LLMTurn(text="(script exhausted)")
        raw = self._turns[self._cursor]
        self._cursor += 1
        return LLMTurn(
            text=raw.get("text", ""),
            tool_calls=[
                ToolCall(
                    id=f"scripted-{self._cursor}-{index}",
                    name=call["name"],
                    arguments=call.get("arguments", {}),
                )
                for index, call in enumerate(raw.get("tool_calls", []))
            ],
        )
