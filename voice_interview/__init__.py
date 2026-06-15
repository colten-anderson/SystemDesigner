"""Voice-agent interview layer for SystemDesigner.

Three layers, connected by narrow interfaces:

1. Interview orchestrator (``orchestrator``) — deterministic state machine that
   walks the 10-file portfolio schema, parsed at runtime from ``templates/`` and
   ``interview-protocol/agent-system-prompt.md`` (the single source of truth).
2. Voice I/O (``pipeline``) — a Pipecat STT -> LLM -> TTS pipeline. Imported
   lazily; the core package is stdlib-only.
3. Meeting connectors (``connectors``) — thin adapters that get the agent into a
   call (Teams via Daily PSTN dial-out, local audio, or text console).
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
