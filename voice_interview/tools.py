"""Tool schemas and dispatch for the interview orchestrator.

These tools are the only way the LLM can make interview progress. They are the
recording API, not the questions — questions come from the protocol files via
``protocol.load_plan``. The schemas are plain Anthropic-format dicts so both
the text console path and the Pipecat voice path can consume them.
"""

from __future__ import annotations

import json

from .orchestrator import InterviewOrchestrator

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "set_mode",
        "description": (
            "Record the interview mode once the team has chosen it. Must be "
            "called before anything else can proceed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["A", "B", "C", "D", "Other"],
                    "description": "A=Configured enterprise SaaS, B=In-house application, "
                    "C=Shared platform / infrastructure service, D=Data system, "
                    "Other=Other / mixed",
                }
            },
            "required": ["mode"],
        },
    },
    {
        "name": "set_system_fact",
        "description": "Record one of the core facts collected right after mode selection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "enum": ["system_name", "owning_team", "criticality_tier", "environments"],
                },
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "record_answer",
        "description": (
            "Record the team's answer for one output field of the current "
            "portfolio file. Paraphrase into a concrete, specific value with "
            "names, numbers, and owners. Call this immediately after each "
            "substantive answer."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Portfolio file, e.g. 'system-identity.md'"},
                "field": {"type": "string", "description": "Exact output field name from the section payload"},
                "value": {"type": "string"},
            },
            "required": ["file", "field", "value"],
        },
    },
    {
        "name": "mark_unknown",
        "description": (
            "Record that the team does not know a field's value. Requires a "
            "named owner and a concrete next step so the unknown is actionable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "field": {"type": "string"},
                "owner": {"type": "string", "description": "Person or team who will find out"},
                "next_step": {"type": "string", "description": "What they will do, ideally with a date"},
            },
            "required": ["file", "field", "owner", "next_step"],
        },
    },
    {
        "name": "record_open_question",
        "description": "Record a side question that came up and should be followed up after the call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "question": {"type": "string"},
                "owner": {"type": "string"},
            },
            "required": ["file", "question", "owner"],
        },
    },
    {
        "name": "set_file_summary",
        "description": (
            "Store the 2-4 sentence summary of the current file after recapping "
            "it aloud and getting the team's confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["file", "summary"],
        },
    },
    {
        "name": "section_status",
        "description": "Check completion progress (remaining fields) for one file or all files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "Optional; omit for all files"},
            },
        },
    },
    {
        "name": "next_section",
        "description": (
            "Advance to the next portfolio file. Refuses (with the list of "
            "missing fields) until the current file is fully recorded and has a "
            "summary."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "skip_section",
        "description": "Skip the current file at the team's request; remaining fields become TBDs.",
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
    {
        "name": "repeat_context",
        "description": "Re-fetch the current section's prompts when the conversation needs re-anchoring.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "pause_interview",
        "description": "Save progress so the team can resume later; use when they need to pause.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "end_interview",
        "description": (
            "End the interview and write the portfolio files. Set partial=true "
            "when ending early so remaining fields are saved as explicit TBDs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"partial": {"type": "boolean", "default": False}},
        },
    },
]


def dispatch_tool(orchestrator: InterviewOrchestrator, name: str, arguments: dict) -> dict:
    """Route one tool call to the orchestrator. Always returns a JSON-able dict."""

    try:
        if name == "set_mode":
            return orchestrator.set_mode(arguments["mode"])
        if name == "set_system_fact":
            return orchestrator.set_system_fact(arguments["key"], arguments["value"])
        if name == "record_answer":
            return orchestrator.record_answer(
                arguments["file"], arguments["field"], arguments["value"]
            )
        if name == "mark_unknown":
            return orchestrator.mark_unknown(
                arguments["file"],
                arguments["field"],
                arguments["owner"],
                arguments["next_step"],
            )
        if name == "record_open_question":
            return orchestrator.record_open_question(
                arguments["file"], arguments["question"], arguments.get("owner", "")
            )
        if name == "set_file_summary":
            return orchestrator.set_file_summary(arguments["file"], arguments["summary"])
        if name == "section_status":
            return orchestrator.section_status(arguments.get("file"))
        if name == "next_section":
            return orchestrator.next_section()
        if name == "skip_section":
            return orchestrator.skip_section(arguments.get("reason", ""))
        if name == "repeat_context":
            return orchestrator.repeat_context()
        if name == "pause_interview":
            return orchestrator.pause_interview()
        if name == "end_interview":
            return orchestrator.end_interview(partial=bool(arguments.get("partial", False)))
    except KeyError as error:
        return {"status": "error", "message": f"Missing required argument: {error}"}
    return {"status": "error", "message": f"Unknown tool: {name}"}


def tool_result_text(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False)
