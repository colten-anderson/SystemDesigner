"""Interview orchestrator: the deterministic authority over the interview.

The LLM leads the *conversation* (phrasing, follow-ups, handling cross-talk);
the orchestrator owns *what counts as done* and *what comes next*. It exposes
tool handlers the LLM must call to record anything, and ``next_section`` is
gated: the LLM cannot advance until every output field of the current file is
either answered or explicitly recorded as a TBD with an owner. Each successful
``next_section`` result hands back the next file's interview prompts parsed
from the templates, so the protocol files remain the single source of truth.

Every mutating handler persists state via the :class:`StateStore`, so a
dropped call loses at most the in-flight utterance.
"""

from __future__ import annotations

import re

from .protocol import InterviewPlan, MODE_LABELS
from . import state as st
from .state import FieldAnswer, InterviewState, StateStore

CORE_FACT_KEYS = ["system_name", "owning_team", "criticality_tier", "environments"]

_VAGUE_PATTERNS = re.compile(
    r"\b(not sure|no idea|don'?t know|i think|maybe|probably|somehow|whatever)\b",
    re.IGNORECASE,
)


def format_tbd(owner: str, next_step: str) -> str:
    """Render an explicit unknown. The parenthetical makes the validator count
    the field as filled while keeping the unknown honest and actionable."""

    return f"TBD (owner: {owner}; next: {next_step})"


class InterviewOrchestrator:
    def __init__(
        self,
        plan: InterviewPlan,
        state: InterviewState,
        store: StateStore | None = None,
        *,
        thin_answer_min_words: int = 4,
    ):
        self.plan = plan
        self.state = state
        self.store = store
        self.thin_answer_min_words = thin_answer_min_words

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self) -> None:
        if self.store is not None:
            self.store.save(self.state)

    def _error(self, message: str) -> dict:
        return {"status": "error", "message": message}

    def _resolve_file(self, file_name: str) -> str | None:
        """Accept 'system-identity', 'system-identity.md', or the title."""

        candidate = file_name.strip()
        if not candidate.endswith(".md"):
            candidate += ".md"
        if candidate in self.state.files:
            return candidate
        lowered = file_name.strip().lower()
        for section in self.plan.sections:
            if section.title.lower() == lowered:
                return section.file_name
        return None

    def _resolve_field(self, file_name: str, field: str) -> str | None:
        section = self.plan.section_for(file_name)
        for expected in section.output_fields:
            if expected.lower() == field.strip().lower().rstrip(":"):
                return expected
        return None

    def _missing_fields(self, file_name: str) -> list[str]:
        section = self.plan.section_for(file_name)
        recorded = self.state.file_state(file_name).fields
        return [f for f in section.output_fields if f not in recorded]

    def _provisional_fields(self, file_name: str) -> list[str]:
        recorded = self.state.file_state(file_name).fields
        return [name for name, ans in recorded.items() if ans.status == st.PROVISIONAL]

    def _state_digest(self) -> str:
        done = sum(
            1
            for f in self.state.section_order
            if self.state.files[f].status in (st.FILE_COMPLETE, st.FILE_SKIPPED)
        )
        current = self.state.current_file or "-"
        return (
            f"phase={self.state.phase} mode={self.state.mode or '?'} "
            f"file {done + (1 if self.state.phase == st.PHASE_SECTIONS else 0)}"
            f"/{len(self.state.section_order)} current={current}"
        )

    def _section_payload(self, file_name: str) -> dict:
        section = self.plan.section_for(file_name)
        payload = {
            "file": section.file_name,
            "title": section.title,
            "interview_prompts": section.interview_prompts,
            "output_fields": section.output_fields,
            "summary_guidance": section.summary_guidance,
        }
        if self.state.mode and self.state.mode in self.plan.mode_emphasis:
            payload["mode_emphasis"] = self.plan.mode_emphasis[self.state.mode]
        payload["state_digest"] = self._state_digest()
        return payload

    def _is_thin(self, value: str) -> str | None:
        words = value.split()
        if len(words) < self.thin_answer_min_words:
            return "answer is very short"
        if _VAGUE_PATTERNS.search(value):
            return "answer sounds uncertain or vague"
        return None

    # ------------------------------------------------------------------
    # Tool handlers (deterministic; return JSON-able dicts fed to the LLM)
    # ------------------------------------------------------------------

    def set_mode(self, mode: str) -> dict:
        normalized = mode.strip()
        upper = normalized.upper()
        if upper in MODE_LABELS:
            normalized = upper
        elif normalized.lower() in ("other", "mixed", "other / mixed", "other/mixed"):
            normalized = "Other"
        else:
            return self._error(
                f"Unknown mode {mode!r}. Valid modes: A, B, C, D, Other."
            )

        self.state.mode = normalized
        if self.state.phase == st.PHASE_MODE_SELECT:
            self.state.phase = st.PHASE_CORE_FACTS
        self._save()
        missing_facts = [k for k in CORE_FACT_KEYS if k not in self.state.system_facts]
        return {
            "status": "ok",
            "mode": normalized,
            "mode_label": MODE_LABELS[normalized],
            "mode_emphasis": self.plan.mode_emphasis.get(normalized, ""),
            "next": (
                "Collect the core facts before the sections: "
                + ", ".join(missing_facts)
                if missing_facts
                else "Core facts already collected; call next_section to begin."
            ),
            "state_digest": self._state_digest(),
        }

    def set_system_fact(self, key: str, value: str) -> dict:
        normalized = key.strip().lower().replace(" ", "_").replace("-", "_")
        if normalized not in CORE_FACT_KEYS:
            return self._error(
                f"Unknown fact {key!r}. Valid keys: {', '.join(CORE_FACT_KEYS)}."
            )
        self.state.system_facts[normalized] = value.strip()
        self._save()
        missing = [k for k in CORE_FACT_KEYS if k not in self.state.system_facts]
        return {
            "status": "ok",
            "recorded": {normalized: value.strip()},
            "missing_core_facts": missing,
            "next": (
                "Ask for: " + ", ".join(missing)
                if missing
                else "All core facts collected. Call next_section to start the first section."
            ),
        }

    def record_answer(self, file: str, field: str, value: str) -> dict:
        file_name = self._resolve_file(file)
        if file_name is None:
            return self._error(f"Unknown portfolio file {file!r}.")
        field_name = self._resolve_field(file_name, field)
        if field_name is None:
            section = self.plan.section_for(file_name)
            return self._error(
                f"Unknown field {field!r} for {file_name}. "
                f"Valid fields: {'; '.join(section.output_fields)}."
            )
        value = value.strip()
        if not value:
            return self._error("Empty value. Record the substance of the answer.")

        thin_reason = self._is_thin(value)
        fs = self.state.file_state(file_name)
        if fs.status == st.FILE_PENDING:
            fs.status = st.FILE_IN_PROGRESS
        fs.fields[field_name] = FieldAnswer(
            value=value,
            status=st.PROVISIONAL if thin_reason else st.ANSWERED,
        )
        self._save()

        remaining = self._missing_fields(file_name)
        result: dict = {
            "status": "recorded_provisional" if thin_reason else "recorded",
            "file": file_name,
            "field": field_name,
            "remaining_fields": remaining,
        }
        if thin_reason:
            result["follow_up_hint"] = (
                f"The {field_name!r} answer seems thin ({thin_reason}). Ask one "
                "concrete follow-up (names, owners, numbers, links) and re-record "
                "with record_answer, or capture it explicitly with mark_unknown."
            )
        return result

    def mark_unknown(self, file: str, field: str, owner: str, next_step: str) -> dict:
        file_name = self._resolve_file(file)
        if file_name is None:
            return self._error(f"Unknown portfolio file {file!r}.")
        field_name = self._resolve_field(file_name, field)
        if field_name is None:
            section = self.plan.section_for(file_name)
            return self._error(
                f"Unknown field {field!r} for {file_name}. "
                f"Valid fields: {'; '.join(section.output_fields)}."
            )
        owner = owner.strip() or "interviewee team"
        next_step = next_step.strip() or "confirm and update this file"

        fs = self.state.file_state(file_name)
        if fs.status == st.FILE_PENDING:
            fs.status = st.FILE_IN_PROGRESS
        fs.fields[field_name] = FieldAnswer(
            value=format_tbd(owner, next_step),
            status=st.TBD,
            owner=owner,
            next_step=next_step,
        )
        self._save()
        return {
            "status": "recorded_unknown",
            "file": file_name,
            "field": field_name,
            "remaining_fields": self._missing_fields(file_name),
        }

    def record_open_question(self, file: str, question: str, owner: str) -> dict:
        file_name = self._resolve_file(file)
        if file_name is None:
            return self._error(f"Unknown portfolio file {file!r}.")
        self.state.file_state(file_name).open_questions.append(
            {"question": question.strip(), "owner": owner.strip() or "interviewee team"}
        )
        self._save()
        return {"status": "ok", "file": file_name}

    def set_file_summary(self, file: str, summary: str) -> dict:
        file_name = self._resolve_file(file)
        if file_name is None:
            return self._error(f"Unknown portfolio file {file!r}.")
        self.state.file_state(file_name).summary = summary.strip()
        self._save()
        return {"status": "ok", "file": file_name}

    def section_status(self, file: str | None = None) -> dict:
        if file:
            file_name = self._resolve_file(file)
            if file_name is None:
                return self._error(f"Unknown portfolio file {file!r}.")
            targets = [file_name]
        else:
            targets = list(self.state.section_order)

        per_file = {}
        for file_name in targets:
            section = self.plan.section_for(file_name)
            fs = self.state.file_state(file_name)
            total = len(section.output_fields)
            recorded = sum(1 for f in section.output_fields if f in fs.fields)
            per_file[file_name] = {
                "status": fs.status,
                "fields_recorded": recorded,
                "fields_total": total,
                "remaining_fields": self._missing_fields(file_name),
                "provisional_fields": self._provisional_fields(file_name),
                "has_summary": bool(fs.summary),
            }
        return {
            "status": "ok",
            "files": per_file,
            "state_digest": self._state_digest(),
        }

    def next_section(self) -> dict:
        if self.state.phase == st.PHASE_MODE_SELECT:
            return self._error(
                "A mode must be selected first. Ask the mode-picker question and "
                "call set_mode."
            )
        if self.state.phase == st.PHASE_CORE_FACTS:
            missing = [k for k in CORE_FACT_KEYS if k not in self.state.system_facts]
            if missing:
                return self._error(
                    "Core facts still missing: " + ", ".join(missing)
                    + ". Collect them with set_system_fact first."
                )
            self.state.phase = st.PHASE_SECTIONS
            self.state.section_cursor = 0
            file_name = self.state.section_order[0]
            self.state.file_state(file_name).status = st.FILE_IN_PROGRESS
            self._save()
            return {"status": "ok", "section": self._section_payload(file_name)}

        if self.state.phase == st.PHASE_SECTIONS:
            current = self.state.current_file
            assert current is not None
            missing = self._missing_fields(current)
            if missing:
                return self._error(
                    f"Cannot advance: {current} still has unrecorded fields: "
                    + ", ".join(missing)
                    + ". Record each with record_answer or mark_unknown "
                    "(use skip_section only if the team wants to skip this topic)."
                )
            fs = self.state.file_state(current)
            if not fs.summary:
                return self._error(
                    f"Cannot advance: draft a 2-4 sentence summary of {current} from "
                    "what you heard, confirm it aloud, and record it with "
                    "set_file_summary."
                )
            fs.status = st.FILE_COMPLETE
            self.state.section_cursor += 1
            if self.state.section_cursor >= len(self.state.section_order):
                self.state.phase = st.PHASE_WRAP_UP
                self._save()
                return {
                    "status": "ok",
                    "section": None,
                    "next": (
                        "All sections complete. Recap the open questions and TBDs "
                        "aloud, thank the team, then call end_interview."
                    ),
                    "state_digest": self._state_digest(),
                }
            next_file = self.state.current_file
            assert next_file is not None
            self.state.file_state(next_file).status = st.FILE_IN_PROGRESS
            self._save()
            return {"status": "ok", "section": self._section_payload(next_file)}

        if self.state.phase == st.PHASE_WRAP_UP:
            return self._error(
                "All sections are already complete. Call end_interview to finish."
            )
        return self._error("The interview has ended.")

    def skip_section(self, reason: str) -> dict:
        if self.state.phase != st.PHASE_SECTIONS or self.state.current_file is None:
            return self._error("No active section to skip.")
        current = self.state.current_file
        owner = self.state.system_facts.get("owning_team", "interviewee team")
        reason = reason.strip() or "section skipped during live interview"
        for field_name in self._missing_fields(current):
            self.mark_unknown(
                current,
                field_name,
                owner=owner,
                next_step=f"fill in after the interview ({reason})",
            )
        fs = self.state.file_state(current)
        if not fs.summary:
            fs.summary = ""
        fs.status = st.FILE_SKIPPED
        self.state.section_cursor += 1
        if self.state.section_cursor >= len(self.state.section_order):
            self.state.phase = st.PHASE_WRAP_UP
            self._save()
            return {
                "status": "ok",
                "skipped": current,
                "section": None,
                "next": "All sections handled. Recap and call end_interview.",
            }
        next_file = self.state.current_file
        assert next_file is not None
        self.state.file_state(next_file).status = st.FILE_IN_PROGRESS
        self._save()
        return {
            "status": "ok",
            "skipped": current,
            "section": self._section_payload(next_file),
        }

    def repeat_context(self) -> dict:
        if self.state.phase == st.PHASE_MODE_SELECT:
            return {"status": "ok", "repeat": self.opening_message()}
        if self.state.phase == st.PHASE_CORE_FACTS:
            missing = [k for k in CORE_FACT_KEYS if k not in self.state.system_facts]
            return {
                "status": "ok",
                "repeat": "Collecting core facts. Still needed: " + ", ".join(missing)
                if missing
                else "Core facts are all collected; call next_section.",
            }
        current = self.state.current_file
        if current is None:
            return {"status": "ok", "repeat": "Wrap-up: recap TBDs and end_interview."}
        return {"status": "ok", "section": self._section_payload(current)}

    def pause_interview(self) -> dict:
        self._save()
        return {
            "status": "ok",
            "message": (
                "Progress saved. Tell the team they can resume any time with "
                "`python scripts/run_interview.py --resume "
                f"{self.state.output_dir}/{st.STATE_FILE_NAME}` and say goodbye "
                "for now if they are done."
            ),
        }

    def end_interview(self, partial: bool = False) -> dict:
        if self.state.phase == st.PHASE_SECTIONS and not partial:
            remaining = [
                f
                for f in self.state.section_order
                if self.state.files[f].status
                in (st.FILE_PENDING, st.FILE_IN_PROGRESS)
            ]
            if remaining:
                return self._error(
                    "Sections still open: " + ", ".join(remaining)
                    + ". Either continue, or call end_interview with partial=true "
                    "to save what exists."
                )
        owner = self.state.system_facts.get("owning_team", "interviewee team")
        if partial:
            for file_name in self.state.section_order:
                for field_name in self._missing_fields(file_name):
                    self.mark_unknown(
                        file_name,
                        field_name,
                        owner=owner,
                        next_step="not reached during the live interview; "
                        "schedule a follow-up session",
                    )
                fs = self.state.file_state(file_name)
                if fs.status in (st.FILE_PENDING, st.FILE_IN_PROGRESS):
                    fs.status = st.FILE_SKIPPED
        self.state.phase = st.PHASE_ENDED
        self._save()
        return {
            "status": "ok",
            "partial": partial,
            "message": "Interview ended. The portfolio files will be written now.",
        }

    # ------------------------------------------------------------------
    # Non-tool API
    # ------------------------------------------------------------------

    def is_complete(self) -> bool:
        return self.state.phase == st.PHASE_ENDED

    def on_user_transcript(self, text: str) -> None:
        self.state.add_transcript("user", text)
        self._save()

    def on_assistant_text(self, text: str) -> None:
        self.state.add_transcript("assistant", text)
        self._save()

    def opening_message(self) -> str:
        mode_lines = "; ".join(
            f"{key}: {label}" for key, label in MODE_LABELS.items()
        )
        return (
            "Hello! I'm the SystemDesigner interviewer. I'll lead a structured "
            "interview about one IT system and turn your answers into a complete "
            "documentation portfolio. First question: which mode best describes "
            f"the system? {mode_lines}."
        )

    def system_prompt(self) -> str:
        """Assemble the LLM system prompt: protocol text + voice/tool rules."""

        parts = [
            self.plan.base_system_prompt,
            VOICE_RULES,
        ]
        if self.state.mode:
            emphasis = self.plan.mode_emphasis.get(self.state.mode)
            if emphasis:
                parts.append(
                    f"## Selected Mode: {self.state.mode} "
                    f"({MODE_LABELS[self.state.mode]})\nEmphasize:\n{emphasis}"
                )
        return "\n\n".join(parts)


VOICE_RULES = """\
## Live Voice Interview Rules (tool contract)

You are running this interview live, by voice, in a meeting. You LEAD the
conversation; never wait silently to be prompted.

- Everything you say is spoken aloud: keep each turn to one or two short
  spoken sentences, no markdown, no bullet lists, no headings.
- Ask ONE question at a time (the written protocol's 5-8 question batches do
  not apply to voice).
- You can only make progress through tools. Record EVERY substantive answer
  immediately with record_answer(file, field, value) — paraphrase the answer
  into a concrete, specific value with names, numbers, and owners.
- When the team genuinely doesn't know something, do not leave it blank: call
  mark_unknown(file, field, owner, next_step) with a named owner.
- Side questions that come up go to record_open_question.
- Before moving on from a file, say a 2-4 sentence recap aloud, ask the team
  to confirm, then store it with set_file_summary.
- Call next_section to advance. If it refuses, it tells you exactly which
  fields are still missing — ask about those.
- People talk over each other and ask you to repeat: use repeat_context to
  re-anchor, answer briefly, and continue.
- If the team asks to skip a topic, confirm aloud and call skip_section.
- If the team needs to pause or leave early, call pause_interview, or
  end_interview with partial=true so progress is saved.
- When every section is done, recap the open questions and TBDs aloud, thank
  the team, and call end_interview.
"""
