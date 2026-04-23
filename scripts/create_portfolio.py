#!/usr/bin/env python3
"""Scaffold a new SystemDesigner portfolio from templates."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

DEFAULT_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a new portfolio directory by copying template files."
    )
    parser.add_argument(
        "destination",
        type=Path,
        help="Path to create for the new portfolio (for example: ./my-system)",
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=DEFAULT_TEMPLATES_DIR,
        help="Directory containing template markdown files (defaults to repository templates/).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files in the destination directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied or skipped without writing files.",
    )
    return parser.parse_args()


def list_template_files(templates_dir: Path) -> list[Path]:
    if not templates_dir.exists() or not templates_dir.is_dir():
        raise ValueError(f"Template directory not found: {templates_dir}")

    template_files = sorted(path for path in templates_dir.glob("*.md") if path.is_file())
    if not template_files:
        raise ValueError(f"No markdown template files found in: {templates_dir}")

    return template_files


def create_portfolio(
    destination: Path,
    templates_dir: Path,
    force: bool,
    dry_run: bool,
) -> tuple[int, int]:
    template_files = list_template_files(templates_dir)
    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)

    copied_count = 0
    skipped_count = 0

    for source in template_files:
        target = destination / source.name

        if target.exists() and not force:
            skipped_count += 1
            prefix = "WOULD SKIP" if dry_run else "SKIP"
            print(f"{prefix}: {target} already exists (use --force to overwrite)")
            continue

        if dry_run:
            print(f"WOULD COPY: {source.name} -> {target}")
        else:
            shutil.copy2(source, target)
            print(f"COPY: {source.name} -> {target}")
        copied_count += 1

    return copied_count, skipped_count


def main() -> int:
    args = parse_args()

    try:
        copied_count, skipped_count = create_portfolio(
            destination=args.destination,
            templates_dir=args.templates_dir,
            force=args.force,
            dry_run=args.dry_run,
        )
    except ValueError as error:
        print(f"ERROR: {error}")
        return 2

    print(
        f"\nDone. {'Would copy' if args.dry_run else 'Copied'} {copied_count} file(s)"
        + (f", skipped {skipped_count} existing file(s)." if skipped_count else ".")
    )

    if copied_count == 0 and not args.dry_run:
        print("No files were copied.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
