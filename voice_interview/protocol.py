"""Parse the interview protocol from the repository's source-of-truth files.

The questions asked during a voice interview are never duplicated in code:
they are parsed at runtime from ``templates/*.md`` ("Interview Prompts" and
"Output Structure" sections) and ``interview-protocol/agent-system-prompt.md``
(mission, hard rules, and per-mode emphasis). The field regex matches the one
in ``scripts/validate_portfolio.py`` so the question plan and the validator
cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

# Must stay in sync with scripts/validate_portfolio.py (tested in
# tests/test_protocol.py by comparing against the validator's own extraction).
REQUIRED_FILES = [
    "system-identity.md",
    "business-context.md",
    "architecture.md",
    "tech-stack.md",
    "dependencies-and-integrations.md",
    "data.md",
    "security-and-access.md",
    "operations.md",
    "known-issues-and-constraints.md",
    "decisions-and-history.md",
]

REQUIRED_SECTIONS = [
    "Summary",
    "Output Structure",
    "For AI + Human Use",
    "Open Questions / TBDs",
]

OUTPUT_FIELD_REGEX = re.compile(r"^-\s+\*\*(.+?):\*\*", re.MULTILINE)

MODE_LABELS = {
    "A": "Configured enterprise SaaS",
    "B": "In-house application",
    "C": "Shared platform / infrastructure service",
    "D": "Data system",
    "Other": "Other / mixed",
}


@dataclass(frozen=True)
class SectionPlan:
    """One portfolio file's slice of the interview, parsed from its template."""

    file_name: str
    title: str
    summary_guidance: str
    interview_prompts: list[str]
    output_fields: list[str]
    ai_human_guidance: str


@dataclass(frozen=True)
class InterviewPlan:
    """The full interview, assembled from the protocol files at runtime."""

    sections: list[SectionPlan]
    base_system_prompt: str
    mode_emphasis: dict[str, str] = field(default_factory=dict)

    def section_for(self, file_name: str) -> SectionPlan:
        for section in self.sections:
            if section.file_name == file_name:
                return section
        raise KeyError(file_name)


def _split_markdown_sections(text: str) -> dict[str, str]:
    """Map ``## Heading`` -> body text (until the next ``##`` heading)."""

    sections: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            if current is not None:
                sections[current] = "\n".join(body).strip()
            current = match.group(1)
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        sections[current] = "\n".join(body).strip()
    return sections


def _bullets(text: str) -> list[str]:
    return [
        re.sub(r"^-\s+", "", line.strip())
        for line in text.splitlines()
        if line.strip().startswith("- ")
    ]


def parse_template(path: Path) -> SectionPlan:
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    title = title_match.group(1) if title_match else path.stem
    sections = _split_markdown_sections(text)

    return SectionPlan(
        file_name=path.name,
        title=title,
        summary_guidance=sections.get("Summary", ""),
        interview_prompts=_bullets(sections.get("Interview Prompts", "")),
        output_fields=OUTPUT_FIELD_REGEX.findall(sections.get("Output Structure", "")),
        ai_human_guidance=sections.get("For AI + Human Use", ""),
    )


def _parse_mode_emphasis(prompt_text: str) -> dict[str, str]:
    """Extract the ``### A) ...`` .. ``### Other / mixed`` emphasis blocks."""

    emphasis: dict[str, str] = {}
    blocks = re.split(r"^###\s+", prompt_text, flags=re.MULTILINE)
    for block in blocks[1:]:
        header, _, body = block.partition("\n")
        # Stop at the next ## heading if the split leaked past the section.
        body = body.split("\n## ")[0].strip()
        key_match = re.match(r"([A-D])\)", header.strip())
        if key_match:
            emphasis[key_match.group(1)] = body
        elif header.strip().lower().startswith("other"):
            emphasis["Other"] = body
    return emphasis


def load_plan(repo_root: Path) -> InterviewPlan:
    """Load the interview plan from the repository protocol files."""

    templates_dir = repo_root / "templates"
    prompt_path = repo_root / "interview-protocol" / "agent-system-prompt.md"

    if not templates_dir.is_dir():
        raise ValueError(f"Templates directory not found: {templates_dir}")
    if not prompt_path.is_file():
        raise ValueError(f"Interview protocol file not found: {prompt_path}")

    sections = []
    for file_name in REQUIRED_FILES:
        template_path = templates_dir / file_name
        if not template_path.is_file():
            raise ValueError(f"Template missing for required file: {template_path}")
        sections.append(parse_template(template_path))

    prompt_text = prompt_path.read_text(encoding="utf-8")

    return InterviewPlan(
        sections=sections,
        base_system_prompt=prompt_text,
        mode_emphasis=_parse_mode_emphasis(prompt_text),
    )
