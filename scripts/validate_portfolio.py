#!/usr/bin/env python3
"""Validate a SystemDesigner portfolio folder for required structure and obvious placeholders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a system portfolio folder for required files and common placeholder text."
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
    return parser.parse_args()


def validate_one_portfolio(portfolio_path: Path) -> dict[str, object]:
    if not portfolio_path.exists() or not portfolio_path.is_dir():
        return {
            "path": str(portfolio_path),
            "error": f"'{portfolio_path}' is not a directory.",
            "missing_files": [],
            "placeholder_hits": [],
            "status": "error",
        }

    missing_files: list[str] = []
    placeholder_hits: list[dict[str, str]] = []

    for name in REQUIRED_FILES:
        target = portfolio_path / name
        if not target.exists():
            missing_files.append(name)
            continue

        text = target.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern.lower() in lowered:
                placeholder_hits.append({"file": name, "pattern": pattern})
                break

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

    if missing_files:
        print("\nMissing required files:")
        for file_name in missing_files:
            print(f"- {file_name}")

    if placeholder_hits:
        print("\nPotential placeholder content detected:")
        for hit in placeholder_hits:
            print(f"- {hit['file']} (matched: {hit['pattern']})")

    print("")


def determine_exit_code(results: list[dict[str, object]], strict: bool) -> int:
    has_errors = any(result["status"] == "error" for result in results)
    has_missing = any(result["missing_files"] for result in results)
    has_placeholders = any(result["placeholder_hits"] for result in results)

    if has_errors:
        return 2
    if has_missing:
        return 1
    if strict and has_placeholders:
        return 1
    return 0


def main() -> int:
    args = parse_args()
    portfolio_paths = collect_portfolios(args.portfolio_path, args.all)
    results = [validate_one_portfolio(path) for path in portfolio_paths]

    exit_code = determine_exit_code(results, args.strict)

    if args.json:
        payload = {
            "strict": args.strict,
            "all": args.all,
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
    if exit_code == 1 and args.strict:
        print("FAIL: Placeholder content found while --strict mode is enabled.")
        return exit_code
    if any(result["placeholder_hits"] for result in results):
        print("PASS with warnings: Required files are present, but placeholders were detected.")
        return 0

    print("PASS: Portfolio contains all required files and no obvious placeholders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
