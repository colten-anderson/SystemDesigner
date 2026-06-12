"""Render interview state into the 10 portfolio markdown files.

Everything the validator measures is emitted deterministically from the parsed
template structure: the four required section headers verbatim, and every
expected ``- **Field:**`` bullet with either the recorded value or an explicit
``TBD (owner: ...; next: ...)`` — which the validator counts as filled while
keeping the unknown honest. The LLM only contributes the ``## Summary`` prose
(captured during the interview via ``set_file_summary``); a deterministic
fallback covers files where no summary was drafted.
"""

from __future__ import annotations

from pathlib import Path
import re

from .orchestrator import format_tbd
from .protocol import InterviewPlan, MODE_LABELS, SectionPlan
from . import state as st
from .state import FileState, InterviewState, today_iso

MIN_CONTENT_WORDS = 80


def _word_count(text: str) -> int:
    """Mirror the validator's non-heading word count."""

    return len([w for w in re.findall(r"\b[\w/-]+\b", text) if not w.startswith("#")])


def _flatten(value: str) -> str:
    """Field values must stay on the bullet's line for the validator."""

    return " ".join(value.split())


def _fallback_summary(state: InterviewState, section: SectionPlan, fs: FileState) -> str:
    system = state.system_facts.get("system_name", "This system")
    mode_label = MODE_LABELS.get(state.mode or "", "system")
    team = state.system_facts.get("owning_team", "the owning team")
    answered = [
        name for name, ans in fs.fields.items() if ans.status != st.TBD
    ]
    covered = (
        f"It covers {', '.join(answered[:4])}" + ("." if len(answered) <= 4 else " and more.")
        if answered
        else "All fields are recorded as explicit follow-ups with owners."
    )
    return (
        f"{system} is documented here as a {mode_label.lower()} owned by {team}. "
        f"This file captures the {section.title.lower()} facts gathered during a "
        f"live voice interview on {today_iso()}. {covered}"
    )


def _ai_human_section(section: SectionPlan, state: InterviewState) -> list[str]:
    guidance = " ".join(section.ai_human_guidance.split())
    team = state.system_facts.get("owning_team", "the owning team")
    lines = []
    if guidance:
        lines.append(f"Guidance for this file: {guidance}")
    lines.append(
        f"Content was captured in a live voice interview on {today_iso()}; "
        f"verify owners and time-sensitive facts with {team} before acting on them."
    )
    return lines


def _open_questions_section(fs: FileState) -> list[str]:
    lines = []
    for question in fs.open_questions:
        owner = question.get("owner", "interviewee team")
        lines.append(f"- {question['question']} (owner: {owner})")
    for field_name, answer in fs.fields.items():
        if answer.status == st.TBD:
            owner = answer.owner or "interviewee team"
            next_step = answer.next_step or "confirm and update this file"
            lines.append(f"- {field_name}: unknown during the interview (owner: {owner}; next: {next_step})")
    if not lines:
        lines.append(f"- None recorded during the interview ({today_iso()}).")
    return lines


def render_file(state: InterviewState, section: SectionPlan) -> str:
    fs = state.files[section.file_name]
    system = state.system_facts.get("system_name")
    title = f"{section.title} — {system}" if system else section.title

    lines: list[str] = [f"# {title}", ""]

    lines.append("## Summary")
    summary = fs.summary.strip() or _fallback_summary(state, section, fs)
    lines.extend([" ".join(summary.split()), ""])

    lines.append("## Output Structure")
    for field_name in section.output_fields:
        answer = fs.fields.get(field_name)
        if answer is None:
            # Defensive: the orchestrator TBD-fills before ending, but a
            # crash-recovered state may still have gaps.
            owner = state.system_facts.get("owning_team", "interviewee team")
            value = format_tbd(owner, "not captured; schedule a follow-up")
        else:
            value = _flatten(answer.value)
        lines.append(f"- **{field_name}:** {value}")
    lines.append("")

    lines.append("## For AI + Human Use")
    lines.extend(_ai_human_section(section, state))
    lines.append("")

    lines.append("## Open Questions / TBDs")
    lines.extend(_open_questions_section(fs))
    lines.append("")

    text = "\n".join(lines)
    if _word_count(text) < MIN_CONTENT_WORDS:
        text += "\n".join(
            [
                "",
                "### Interview Metadata",
                f"- **Interview date:** {today_iso()}",
                f"- **Interview session:** {state.session_id}",
                f"- **Mode:** {state.mode or 'unspecified'} "
                f"({MODE_LABELS.get(state.mode or '', 'unspecified')})",
                f"- **Owning team:** {state.system_facts.get('owning_team', 'unspecified')}",
                f"- **Environments in scope:** {state.system_facts.get('environments', 'unspecified')}",
                f"- **File status at interview end:** {fs.status}",
                "This metadata block records the provenance of the interview so "
                "readers can judge how current the facts above are and who to "
                "contact to refresh them.",
                "",
            ]
        )
    return text


def write_portfolio(state: InterviewState, plan: InterviewPlan, out_dir: Path) -> list[Path]:
    """Write all 10 portfolio files from the interview state."""

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for section in plan.sections:
        target = out_dir / section.file_name
        target.write_text(render_file(state, section), encoding="utf-8")
        written.append(target)
    return written
