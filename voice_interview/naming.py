"""Friendly output-directory naming.

When the user didn't pick an output directory, the interview starts in a
timestamped folder (the system name isn't known yet). Once the interview has
captured the system name, the folder is renamed to a readable slug —
``portfolios/customer-billing-api`` instead of ``portfolios/interview-...`` —
and the state file moves with it so ``--resume`` keeps working.
"""

from __future__ import annotations

from pathlib import Path
import re

from .state import STATE_FILE_NAME, InterviewState, StateStore


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:60]


def finalize_output_dir(
    state: InterviewState, store: StateStore, *, auto_named: bool
) -> Path:
    """Rename an auto-named output dir to the captured system name.

    Returns the (possibly unchanged) output directory. Never raises: if the
    rename can't happen safely, the timestamped directory stays.
    """

    current = Path(state.output_dir)
    if not auto_named:
        return current

    system_name = state.system_facts.get("system_name", "")
    slug = slugify(system_name)
    if not slug or not current.is_dir():
        return current

    target = current.with_name(slug)
    if target == current:
        return current
    if target.exists():
        # Don't clobber an earlier interview of the same system; suffix it.
        for suffix in range(2, 100):
            candidate = current.with_name(f"{slug}-{suffix}")
            if not candidate.exists():
                target = candidate
                break
        else:
            return current

    try:
        current.rename(target)
    except OSError:
        return current

    state.output_dir = str(target)
    store.path = target / STATE_FILE_NAME
    store.save(state)
    return target
