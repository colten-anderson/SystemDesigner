"""Post-interview summary: what was captured, what's still owed, and by whom.

Written next to the portfolio as ``interview-summary.md`` after every run
(complete or paused). This is the actionable follow-up list — owners can scan
it instead of grepping ten files for TBDs.
"""

from __future__ import annotations

from pathlib import Path

from .protocol import InterviewPlan, MODE_LABELS
from . import state as st
from .state import InterviewState, today_iso

SUMMARY_FILE_NAME = "interview-summary.md"


def build_interview_summary(state: InterviewState, plan: InterviewPlan) -> str:
    system = state.system_facts.get("system_name", "(system name not captured)")
    mode_label = MODE_LABELS.get(state.mode or "", "not selected")
    finished = state.phase == st.PHASE_ENDED

    lines = [
        f"# Interview Summary — {system}",
        "",
        f"- **Date:** {today_iso()}",
        f"- **Mode:** {state.mode or '-'} ({mode_label})",
        f"- **Owning team:** {state.system_facts.get('owning_team', '-')}",
        f"- **Status:** {'completed' if finished else 'paused — resumable'}",
        f"- **Session:** {state.session_id}",
        "",
        "## Coverage",
        "",
        "| File | Status | Fields recorded | Unknowns (TBD) |",
        "|---|---|---|---|",
    ]

    follow_ups: list[tuple[str, str, str, str]] = []  # file, field, owner, next
    open_questions: list[tuple[str, str, str]] = []  # file, question, owner

    for section in plan.sections:
        fs = state.files[section.file_name]
        total = len(section.output_fields)
        recorded = sum(1 for f in section.output_fields if f in fs.fields)
        tbd_fields = [
            (name, answer)
            for name, answer in fs.fields.items()
            if answer.status == st.TBD
        ]
        lines.append(
            f"| {section.file_name} | {fs.status} | {recorded}/{total} | {len(tbd_fields)} |"
        )
        for name, answer in tbd_fields:
            follow_ups.append(
                (
                    section.file_name,
                    name,
                    answer.owner or "interviewee team",
                    answer.next_step or "confirm and update",
                )
            )
        for question in fs.open_questions:
            open_questions.append(
                (
                    section.file_name,
                    question.get("question", ""),
                    question.get("owner", "interviewee team"),
                )
            )

    lines.append("")
    lines.append("## Follow-ups owed")
    lines.append("")
    if follow_ups:
        lines.append("| File | Field | Owner | Next step |")
        lines.append("|---|---|---|---|")
        for file_name, field, owner, next_step in follow_ups:
            lines.append(f"| {file_name} | {field} | {owner} | {next_step} |")
    else:
        lines.append("None — every field was answered during the interview.")

    lines.append("")
    lines.append("## Open questions raised")
    lines.append("")
    if open_questions:
        for file_name, question, owner in open_questions:
            lines.append(f"- {question} (owner: {owner}; file: {file_name})")
    else:
        lines.append("None recorded.")

    if not finished:
        lines.extend(
            [
                "",
                "## Resuming",
                "",
                "This interview was paused, not finished. Continue with:",
                "",
                "```bash",
                f"python scripts/run_interview.py --resume {state.output_dir}/{st.STATE_FILE_NAME}",
                "```",
            ]
        )

    lines.append("")
    return "\n".join(lines)


def write_interview_summary(
    state: InterviewState, plan: InterviewPlan, out_dir: Path
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / SUMMARY_FILE_NAME
    target.write_text(build_interview_summary(state, plan), encoding="utf-8")
    return target
