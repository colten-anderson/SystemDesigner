from pathlib import Path

import pytest

from voice_interview.naming import finalize_output_dir, slugify
from voice_interview.state import STATE_FILE_NAME, InterviewState, StateStore


def test_slugify() -> None:
    assert slugify("Customer Billing API") == "customer-billing-api"
    assert slugify("  Exchange Online (US tenant) ") == "exchange-online-us-tenant"
    assert slugify("___") == ""
    assert len(slugify("x" * 200)) <= 60


def make_session(tmp_path: Path, dir_name: str, system_name: str | None):
    out_dir = tmp_path / "portfolios" / dir_name
    out_dir.mkdir(parents=True)
    (out_dir / "system-identity.md").write_text("content", encoding="utf-8")
    state = InterviewState(output_dir=str(out_dir))
    if system_name:
        state.system_facts["system_name"] = system_name
    store = StateStore(out_dir / STATE_FILE_NAME)
    store.save(state)
    return state, store, out_dir


def test_auto_named_dir_renamed_to_system_slug(tmp_path: Path) -> None:
    state, store, out_dir = make_session(tmp_path, "interview-20260612-1", "Billing API")

    final = finalize_output_dir(state, store, auto_named=True)

    assert final.name == "billing-api"
    assert not out_dir.exists()
    assert (final / "system-identity.md").exists()
    # The state file moved and was re-saved with the new location.
    assert store.path == final / STATE_FILE_NAME
    assert store.load().output_dir == str(final)


def test_explicit_out_dir_never_renamed(tmp_path: Path) -> None:
    state, store, out_dir = make_session(tmp_path, "my-chosen-name", "Billing API")
    final = finalize_output_dir(state, store, auto_named=False)
    assert final == out_dir
    assert out_dir.exists()


def test_no_system_name_keeps_timestamp_dir(tmp_path: Path) -> None:
    state, store, out_dir = make_session(tmp_path, "interview-20260612-1", None)
    final = finalize_output_dir(state, store, auto_named=True)
    assert final == out_dir


def test_existing_target_gets_suffix(tmp_path: Path) -> None:
    (tmp_path / "portfolios" / "billing-api").mkdir(parents=True)
    state, store, _ = make_session(tmp_path, "interview-20260612-2", "Billing API")
    final = finalize_output_dir(state, store, auto_named=True)
    assert final.name == "billing-api-2"
    assert store.load().output_dir == str(final)


@pytest.mark.parametrize("auto_named", [True, False])
def test_missing_dir_is_a_noop(tmp_path: Path, auto_named: bool) -> None:
    state = InterviewState(output_dir=str(tmp_path / "never-created"))
    state.system_facts["system_name"] = "X"
    store = StateStore(tmp_path / "never-created" / STATE_FILE_NAME)
    final = finalize_output_dir(state, store, auto_named=auto_named)
    assert final == tmp_path / "never-created"
