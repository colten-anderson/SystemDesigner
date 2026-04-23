#!/usr/bin/env python3
"""Validate a SystemDesigner portfolio for structure, placeholders, and content quality."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
import re
import sys

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

PLACEHOLDER_PATTERNS = [
    "TODO",
    "TBD",
    "[insert",
    "<insert",
    "lorem ipsum",
]

OUTPUT_FIELD_REGEX = re.compile(r"^-\s+\*\*(.+?):\*\*", re.MULTILINE)
HEADER_REGEX = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class QualityIssue:
    """Represents a quality finding discovered in a portfolio file."""

    file: str
    category: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a system portfolio folder for required files, placeholder text, "
            "and content-completeness quality checks."
        )
    )
    parser.add_argument(
        "portfolio_path",
        type=Path,
        help="Path to a portfolio directory (for example: examples/exchange-online)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when placeholder text is detected.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=(
            "Treat portfolio_path as a parent directory and validate all immediate "
            "subdirectories as portfolios."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )
    parser.add_argument(
        "--quality-gate",
        type=int,
        metavar="MIN_SCORE",
        help=(
            "Fail when computed quality score is below MIN_SCORE (0-100). "
            "Useful for CI enforcement."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Write a markdown quality report to the given file path.",
    )
    return parser.parse_args()


def list_template_files(templates_dir: Path) -> list[Path]:
    if not templates_dir.exists() or not templates_dir.is_dir():
        raise ValueError(f"Template directory not found: {templates_dir}")

    files = sorted(path for path in templates_dir.glob("*.md") if path.is_file())
    if not files:
        raise ValueError(f"No markdown template files found in: {templates_dir}")

    return files


def load_expected_fields(templates_dir: Path) -> dict[str, list[str]]:
    expected: dict[str, list[str]] = {}
    for template_path in list_template_files(templates_dir):
        text = template_path.read_text(encoding="utf-8", errors="ignore")
        expected[template_path.name] = OUTPUT_FIELD_REGEX.findall(text)
    return expected


def extract_headers(text: str) -> list[str]:
    return HEADER_REGEX.findall(text)


def extract_filled_output_fields(text: str, expected_fields: list[str]) -> dict[str, bool]:
    filled_map = {field: False for field in expected_fields}

    lines = text.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("- **"):
            continue

        for field in expected_fields:
            prefix = f"- **{field}:**"
            if not stripped.startswith(prefix):
                continue

            remainder = stripped[len(prefix) :].strip()
            has_inline_value = bool(remainder and remainder not in {"-", "N/A", "TBD"})
            if has_inline_value:
                filled_map[field] = True
                break

            next_non_empty = ""
            for next_line in lines[index + 1 :]:
                candidate = next_line.strip()
                if not candidate:
                    continue
                next_non_empty = candidate
                break

            if next_non_empty and not next_non_empty.startswith("-") and not next_non_empty.startswith("##"):
                if next_non_empty.upper() not in {"TBD", "TODO", "N/A"}:
                    filled_map[field] = True
            break

    return filled_map


def find_placeholder_hits(text: str) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for pattern in PLACEHOLDER_PATTERNS:
        if pattern.lower() in lowered:
            hits.append(pattern)
    return hits


def evaluate_quality(
    portfolio_path: Path,
    expected_fields_by_file: dict[str, list[str]],
) -> tuple[int, list[QualityIssue], dict[str, dict[str, object]]]:
    issues: list[QualityIssue] = []
    details: dict[str, dict[str, object]] = {}

    required_sections = {"Summary", "Output Structure", "For AI + Human Use", "Open Questions / TBDs"}
    file_scores: list[float] = []

    for file_name, expected_fields in expected_fields_by_file.items():
        target = portfolio_path / file_name
        if not target.exists():
            continue

        text = target.read_text(encoding="utf-8", errors="ignore")
        headers = set(extract_headers(text))
        missing_sections = sorted(required_sections - headers)

        for section in missing_sections:
            issues.append(
                QualityIssue(
                    file=file_name,
                    category="missing-section",
                    message=f"Missing section header: '{section}'.",
                )
            )

        filled_fields = extract_filled_output_fields(text, expected_fields)
        filled_count = sum(1 for is_filled in filled_fields.values() if is_filled)

        for field_name, is_filled in filled_fields.items():
            if not is_filled:
                issues.append(
                    QualityIssue(
                        file=file_name,
                        category="incomplete-output-field",
                        message=f"Output field has no clear value: '{field_name}'.",
                    )
                )

        non_heading_words = len(
            [word for word in re.findall(r"\b[\w/-]+\b", text) if not word.startswith("#")]
        )
        length_coverage = min(non_heading_words / 80, 1.0)
        section_coverage = (
            (len(required_sections) - len(missing_sections)) / len(required_sections)
            if required_sections
            else 1.0
        )
        field_coverage = (filled_count / len(expected_fields)) if expected_fields else 1.0
        file_score = (field_coverage * 50) + (section_coverage * 30) + (length_coverage * 20)
        file_scores.append(file_score)

        details[file_name] = {
            "expected_output_fields": len(expected_fields),
            "filled_output_fields": filled_count,
            "missing_sections": missing_sections,
            "field_coverage": round(field_coverage * 100, 1),
            "section_coverage": round(section_coverage * 100, 1),
            "content_word_count": non_heading_words,
            "length_coverage": round(length_coverage * 100, 1),
            "file_quality_score": round(file_score, 1),
        }

    quality_score = round(sum(file_scores) / len(file_scores)) if file_scores else 0

    return quality_score, issues, details


def validate_one_portfolio(
    portfolio_path: Path,
    expected_fields_by_file: dict[str, list[str]],
) -> dict[str, object]:
    if not portfolio_path.exists() or not portfolio_path.is_dir():
        return {
            "path": str(portfolio_path),
            "error": f"'{portfolio_path}' is not a directory.",
            "missing_files": [],
            "placeholder_hits": [],
            "status": "error",
            "quality_score": 0,
            "quality_issues": [],
            "quality_details": {},
        }

    missing_files: list[str] = []
    placeholder_hits: list[dict[str, object]] = []

    for name in REQUIRED_FILES:
        target = portfolio_path / name
        if not target.exists():
            missing_files.append(name)
            continue

        text = target.read_text(encoding="utf-8", errors="ignore")
        hits = find_placeholder_hits(text)
        if hits:
            placeholder_hits.append({"file": name, "patterns": hits})

    quality_score, quality_issues, quality_details = evaluate_quality(
        portfolio_path=portfolio_path,
        expected_fields_by_file=expected_fields_by_file,
    )

    status = "pass"
    if missing_files:
        status = "fail"
    elif placeholder_hits:
        status = "warning"

    return {
        "path": str(portfolio_path),
        "missing_files": missing_files,
        "placeholder_hits": placeholder_hits,
        "status": status,
        "quality_score": quality_score,
        "quality_issues": [issue.__dict__ for issue in quality_issues],
        "quality_details": quality_details,
    }


def collect_portfolios(base_path: Path, validate_all: bool) -> list[Path]:
    if not validate_all:
        return [base_path]

    return sorted(path for path in base_path.iterdir() if path.is_dir())


def print_human_report(result: dict[str, object]) -> None:
    print(f"Validating portfolio: {result['path']}")

    if result.get("error"):
        print(f"ERROR: {result['error']}\n")
        return

    missing_files = result["missing_files"]
    placeholder_hits = result["placeholder_hits"]
    quality_issues = result["quality_issues"]

    if missing_files:
        print("\nMissing required files:")
        for file_name in missing_files:
            print(f"- {file_name}")

    if placeholder_hits:
        print("\nPotential placeholder content detected:")
        for hit in placeholder_hits:
            pattern_list = ", ".join(hit["patterns"])
            print(f"- {hit['file']} (matched: {pattern_list})")

    print(f"\nQuality score: {result['quality_score']}/100")

    if quality_issues:
        print("Top quality gaps:")
        for issue in quality_issues[:8]:
            print(f"- [{issue['file']}] {issue['message']}")
        if len(quality_issues) > 8:
            print(f"- ...and {len(quality_issues) - 8} more")

    print("")


def determine_exit_code(results: list[dict[str, object]], strict: bool, quality_gate: int | None) -> int:
    has_errors = any(result["status"] == "error" for result in results)
    has_missing = any(result["missing_files"] for result in results)
    has_placeholders = any(result["placeholder_hits"] for result in results)

    if has_errors:
        return 2
    if has_missing:
        return 1
    if strict and has_placeholders:
        return 1
    if quality_gate is not None and any(result["quality_score"] < quality_gate for result in results):
        return 1
    return 0


def build_markdown_report(results: list[dict[str, object]], strict: bool, quality_gate: int | None) -> str:
    lines = [
        "# Portfolio Validation Report",
        "",
        f"- Strict placeholder mode: {'enabled' if strict else 'disabled'}",
        f"- Quality gate: {quality_gate if quality_gate is not None else 'not set'}",
        "",
    ]

    for result in results:
        lines.append(f"## {result['path']}")
        if result.get("error"):
            lines.extend([f"- Status: error", f"- Error: {result['error']}", ""])
            continue

        lines.append(f"- Status: {result['status']}")
        lines.append(f"- Quality score: {result['quality_score']}/100")

        if result["missing_files"]:
            lines.append("- Missing files:")
            for file_name in result["missing_files"]:
                lines.append(f"  - {file_name}")

        if result["placeholder_hits"]:
            lines.append("- Placeholder hits:")
            for hit in result["placeholder_hits"]:
                pattern_list = ", ".join(hit["patterns"])
                lines.append(f"  - {hit['file']}: {pattern_list}")

        if result["quality_issues"]:
            lines.append("- Quality issues:")
            for issue in result["quality_issues"][:15]:
                lines.append(f"  - [{issue['file']}] {issue['message']}")
            if len(result["quality_issues"]) > 15:
                lines.append(f"  - ...and {len(result['quality_issues']) - 15} more")

        lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    if args.quality_gate is not None and not 0 <= args.quality_gate <= 100:
        print("ERROR: --quality-gate must be between 0 and 100.")
        return 2

    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    expected_fields_by_file = load_expected_fields(templates_dir)

    portfolio_paths = collect_portfolios(args.portfolio_path, args.all)
    results = [
        validate_one_portfolio(path, expected_fields_by_file=expected_fields_by_file)
        for path in portfolio_paths
    ]

    exit_code = determine_exit_code(results, args.strict, args.quality_gate)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            build_markdown_report(results, strict=args.strict, quality_gate=args.quality_gate),
            encoding="utf-8",
        )

    if args.json:
        payload = {
            "strict": args.strict,
            "all": args.all,
            "quality_gate": args.quality_gate,
            "results": results,
            "summary": {
                "total": len(results),
                "errors": sum(1 for result in results if result["status"] == "error"),
                "failed": sum(1 for result in results if result["missing_files"]),
                "warnings": sum(1 for result in results if result["placeholder_hits"]),
                "passed": sum(
                    1
                    for result in results
                    if not result["missing_files"] and not result["placeholder_hits"]
                ),
                "below_quality_gate": (
                    sum(
                        1
                        for result in results
                        if args.quality_gate is not None and result["quality_score"] < args.quality_gate
                    )
                ),
                "average_quality_score": (
                    round(sum(result["quality_score"] for result in results) / len(results), 1)
                    if results
                    else 0.0
                ),
            },
        }
        print(json.dumps(payload, indent=2))
        return exit_code

    for result in results:
        print_human_report(result)

    if exit_code == 2:
        print("FAIL: One or more target directories could not be read as portfolios.")
        return exit_code
    if exit_code == 1 and any(result["missing_files"] for result in results):
        print("FAIL: One or more portfolios are missing required files.")
        return exit_code
    if exit_code == 1 and args.strict and any(result["placeholder_hits"] for result in results):
        print("FAIL: Placeholder content found while --strict mode is enabled.")
        return exit_code
    if exit_code == 1 and args.quality_gate is not None:
        print(f"FAIL: One or more portfolios scored below quality gate ({args.quality_gate}).")
        return exit_code
    if any(result["placeholder_hits"] for result in results):
        print("PASS with warnings: Required files are present, but placeholders were detected.")
        return 0

    print("PASS: Portfolio contains all required files and passed quality checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
