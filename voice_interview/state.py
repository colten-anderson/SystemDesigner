"""Interview state: continuously persisted, resumable after a dropped call.

The state file is plain JSON written atomically (temp file + ``os.replace``)
after every recorded answer, so a crash or dropped call loses at most the
in-flight utterance. ``--resume`` reloads it and continues where it left off.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import json
import os
import uuid

from .protocol import InterviewPlan, REQUIRED_FILES

STATE_VERSION = 1
STATE_FILE_NAME = ".interview-state.json"

# Interview phases, in order.
PHASE_MODE_SELECT = "MODE_SELECT"
PHASE_CORE_FACTS = "CORE_FACTS"
PHASE_SECTIONS = "SECTIONS"
PHASE_WRAP_UP = "WRAP_UP"
PHASE_ENDED = "ENDED"

# Field answer statuses.
ANSWERED = "answered"
PROVISIONAL = "provisional"
TBD = "tbd"

# File statuses.
FILE_PENDING = "pending"
FILE_IN_PROGRESS = "in_progress"
FILE_COMPLETE = "complete"
FILE_SKIPPED = "skipped"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


@dataclass
class FieldAnswer:
    value: str
    status: str = ANSWERED
    owner: str | None = None
    next_step: str | None = None
    answered_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        data = {"value": self.value, "status": self.status, "answered_at": self.answered_at}
        if self.owner is not None:
            data["owner"] = self.owner
        if self.next_step is not None:
            data["next_step"] = self.next_step
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "FieldAnswer":
        return cls(
            value=data["value"],
            status=data.get("status", ANSWERED),
            owner=data.get("owner"),
            next_step=data.get("next_step"),
            answered_at=data.get("answered_at", _now()),
        )


@dataclass
class FileState:
    status: str = FILE_PENDING
    summary: str = ""
    fields: dict[str, FieldAnswer] = field(default_factory=dict)
    open_questions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "summary": self.summary,
            "fields": {name: answer.to_dict() for name, answer in self.fields.items()},
            "open_questions": self.open_questions,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileState":
        return cls(
            status=data.get("status", FILE_PENDING),
            summary=data.get("summary", ""),
            fields={
                name: FieldAnswer.from_dict(raw)
                for name, raw in data.get("fields", {}).items()
            },
            open_questions=list(data.get("open_questions", [])),
        )


@dataclass
class InterviewState:
    output_dir: str
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    phase: str = PHASE_MODE_SELECT
    mode: str | None = None
    system_facts: dict[str, str] = field(default_factory=dict)
    section_cursor: int = 0
    section_order: list[str] = field(default_factory=lambda: list(REQUIRED_FILES))
    files: dict[str, FileState] = field(default_factory=dict)
    transcript: list[dict] = field(default_factory=list)
    join_target: dict = field(default_factory=dict)
    config_snapshot: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        for file_name in self.section_order:
            self.files.setdefault(file_name, FileState())

    # -- accessors -----------------------------------------------------

    @property
    def current_file(self) -> str | None:
        if self.phase != PHASE_SECTIONS:
            return None
        if 0 <= self.section_cursor < len(self.section_order):
            return self.section_order[self.section_cursor]
        return None

    def file_state(self, file_name: str) -> FileState:
        return self.files[file_name]

    def add_transcript(self, role: str, text: str) -> None:
        self.transcript.append({"t": _now(), "role": role, "text": text})

    # -- serialization -------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "version": STATE_VERSION,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "phase": self.phase,
            "mode": self.mode,
            "system_facts": self.system_facts,
            "section_cursor": self.section_cursor,
            "section_order": self.section_order,
            "files": {name: fs.to_dict() for name, fs in self.files.items()},
            "transcript": self.transcript,
            "join_target": self.join_target,
            "output_dir": self.output_dir,
            "config_snapshot": self.config_snapshot,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "InterviewState":
        if data.get("version") != STATE_VERSION:
            raise ValueError(
                f"Unsupported state file version: {data.get('version')!r} "
                f"(expected {STATE_VERSION})"
            )
        state = cls(
            output_dir=data["output_dir"],
            session_id=data["session_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            phase=data["phase"],
            mode=data.get("mode"),
            system_facts=dict(data.get("system_facts", {})),
            section_cursor=data.get("section_cursor", 0),
            section_order=list(data.get("section_order", REQUIRED_FILES)),
            files={},
            transcript=list(data.get("transcript", [])),
            join_target=dict(data.get("join_target", {})),
            config_snapshot=dict(data.get("config_snapshot", {})),
        )
        state.files = {
            name: FileState.from_dict(raw) for name, raw in data.get("files", {}).items()
        }
        for file_name in state.section_order:
            state.files.setdefault(file_name, FileState())
        return state


class StateStore:
    """Atomic JSON persistence for an :class:`InterviewState`."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def save(self, state: InterviewState) -> None:
        state.updated_at = _now()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(state.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(tmp_path, self.path)

    def load(self) -> InterviewState:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return InterviewState.from_dict(data)


def resume_digest(state: InterviewState, plan: InterviewPlan, *, transcript_turns: int = 10) -> str:
    """Compact textual digest used to rebuild LLM context on resume."""

    lines = [
        f"Resuming interview session {state.session_id} (phase: {state.phase}).",
        f"Mode: {state.mode or 'not selected yet'}.",
    ]
    if state.system_facts:
        facts = "; ".join(f"{key}: {value}" for key, value in state.system_facts.items())
        lines.append(f"System facts so far: {facts}.")

    completed, in_progress, pending = [], [], []
    for file_name in state.section_order:
        fs = state.files[file_name]
        if fs.status in (FILE_COMPLETE, FILE_SKIPPED):
            completed.append(file_name)
        elif fs.status == FILE_IN_PROGRESS:
            section = plan.section_for(file_name)
            remaining = [f for f in section.output_fields if f not in fs.fields]
            in_progress.append(f"{file_name} (remaining fields: {', '.join(remaining) or 'none'})")
        else:
            pending.append(file_name)
    if completed:
        lines.append(f"Files done: {', '.join(completed)}.")
    if in_progress:
        lines.append(f"File in progress: {'; '.join(in_progress)}.")
    if pending:
        lines.append(f"Files still pending: {', '.join(pending)}.")

    recent = state.transcript[-transcript_turns:]
    if recent:
        lines.append("Recent conversation:")
        for turn in recent:
            lines.append(f"  [{turn['role']}] {turn['text']}")
    return "\n".join(lines)
