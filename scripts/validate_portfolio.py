#!/usr/bin/env python3
"""Validate a SystemDesigner portfolio folder for required structure and obvious placeholders."""

from __future__ import annotations

import argparse
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    portfolio_path = args.portfolio_path

    if not portfolio_path.exists() or not portfolio_path.is_dir():
        print(f"ERROR: '{portfolio_path}' is not a directory.")
        return 2

    print(f"Validating portfolio: {portfolio_path}")

    missing_files: list[str] = []
    placeholder_hits: list[tuple[str, str]] = []

    for name in REQUIRED_FILES:
        target = portfolio_path / name
        if not target.exists():
            missing_files.append(name)
            continue

        text = target.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern.lower() in lowered:
                placeholder_hits.append((name, pattern))
                break

    if missing_files:
        print("\nMissing required files:")
        for file_name in missing_files:
            print(f"- {file_name}")

    if placeholder_hits:
        print("\nPotential placeholder content detected:")
        for file_name, pattern in placeholder_hits:
            print(f"- {file_name} (matched: {pattern})")

    if missing_files:
        print("\nFAIL: Portfolio is missing required files.")
        return 1

    if placeholder_hits and args.strict:
        print("\nFAIL: Placeholder content found while --strict mode is enabled.")
        return 1

    if placeholder_hits:
        print("\nPASS with warnings: Required files are present, but placeholders were detected.")
        return 0

    print("\nPASS: Portfolio contains all required files and no obvious placeholders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
