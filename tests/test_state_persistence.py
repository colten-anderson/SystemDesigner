from pathlib import Path
import json

import pytest

from voice_interview import state as state_mod
from voice_interview.protocol import REQUIRED_FILES, load_plan
from voice_interview.state import FieldAnswer, InterviewState, StateStore, resume_digest

REPO_ROOT = Path(__file__).resolve().parents[1]


def make_state(tmp_path: Path) -> InterviewState:
    return InterviewState(output_dir=str(tmp_path / "portfolio"))


def test_new_state_has_all_required_files(tmp_path: Path) -> None:
    state = make_state(tmp_path)
    assert set(state.files) == set(REQUIRED_FILES)
    assert state.phase == state_mod.PHASE_MODE_SELECT
    assert state.current_file is None  # not in SECTIONS phase yet


def test_round_trip_serialization(tmp_path: Path) -> None:
    state = make_state(tmp_path)
    state.mode = "B"
    state.phase = state_mod.PHASE_SECTIONS
    state.section_cursor = 2
    state.system_facts["system_name"] = "Billing API"
    fs = state.file_state("system-identity.md")
    fs.status = state_mod.FILE_COMPLETE
    fs.summary = "A billing API."
    fs.fields["System name"] = FieldAnswer(value="Billing API")
    fs.fields["Aliases"] = FieldAnswer(
        value="TBD (owner: Jane; next: confirm by 2026-07-01)",
        status=state_mod.TBD,
        owner="Jane",
        next_step="confirm by 2026-07-01",
    )
    fs.open_questions.append({"question": "EU tenant in scope?", "owner": "PM"})
    state.add_transcript("assistant", "Which mode applies?")
    state.add_transcript("user", "In-house app")

    restored = InterviewState.from_dict(state.to_dict())
    assert restored.to_dict() == state.to_dict()
    assert restored.current_file == REQUIRED_FILES[2]
    assert restored.files["system-identity.md"].fields["Aliases"].owner == "Jane"


def test_store_saves_and_loads(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "out" / ".interview-state.json")
    state = make_state(tmp_path)
    state.system_facts["system_name"] = "Thing"
    store.save(state)

    assert store.path.exists()
    loaded = store.load()
    assert loaded.session_id == state.session_id
    assert loaded.system_facts["system_name"] == "Thing"


def test_save_is_atomic_no_tmp_left_behind(tmp_path: Path) -> None:
    store = StateStore(tmp_path / ".interview-state.json")
    state = make_state(tmp_path)
    store.save(state)
    store.save(state)
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == []
    # The file on disk must always be complete valid JSON.
    json.loads(store.path.read_text(encoding="utf-8"))


def test_unsupported_version_rejected(tmp_path: Path) -> None:
    state = make_state(tmp_path)
    data = state.to_dict()
    data["version"] = 999
    with pytest.raises(ValueError, match="Unsupported state file version"):
        InterviewState.from_dict(data)


def test_resume_digest_summarizes_progress(tmp_path: Path) -> None:
    plan = load_plan(REPO_ROOT)
    state = make_state(tmp_path)
    state.mode = "A"
    state.phase = state_mod.PHASE_SECTIONS
    state.section_cursor = 1
    state.system_facts["system_name"] = "Exchange Online"
    state.files["system-identity.md"].status = state_mod.FILE_COMPLETE
    fs = state.files["business-context.md"]
    fs.status = state_mod.FILE_IN_PROGRESS
    fs.fields["Purpose"] = FieldAnswer(value="Email for everyone")
    state.add_transcript("user", "the purpose is email")

    digest = resume_digest(state, plan)
    assert "Mode: A" in digest
    assert "system_name: Exchange Online" in digest
    assert "Files done: system-identity.md" in digest
    assert "business-context.md" in digest
    assert "Purpose" not in digest.split("remaining fields:")[0]
    assert "remaining fields:" in digest
    assert "the purpose is email" in digest
    # Answered field must not be listed as remaining.
    remaining_part = digest.split("remaining fields:")[1].split(")")[0]
    assert "Purpose" not in remaining_part
