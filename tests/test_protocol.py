from pathlib import Path
import importlib.util
import sys

from voice_interview import protocol

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_validator_module():
    spec = importlib.util.spec_from_file_location(
        "validate_portfolio", REPO_ROOT / "scripts" / "validate_portfolio.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_portfolio"] = module
    spec.loader.exec_module(module)
    return module


def test_load_plan_parses_all_required_files() -> None:
    plan = protocol.load_plan(REPO_ROOT)
    assert [section.file_name for section in plan.sections] == protocol.REQUIRED_FILES


def test_every_section_has_prompts_and_fields() -> None:
    plan = protocol.load_plan(REPO_ROOT)
    for section in plan.sections:
        assert section.interview_prompts, f"no prompts parsed for {section.file_name}"
        assert section.output_fields, f"no fields parsed for {section.file_name}"
        assert section.title
        assert section.summary_guidance


def test_field_lists_match_validator_extraction_exactly() -> None:
    validator = _load_validator_module()
    expected = validator.load_expected_fields(REPO_ROOT / "templates")
    plan = protocol.load_plan(REPO_ROOT)
    for section in plan.sections:
        assert section.output_fields == expected[section.file_name], section.file_name


def test_required_files_match_validator() -> None:
    validator = _load_validator_module()
    assert protocol.REQUIRED_FILES == validator.REQUIRED_FILES


def test_mode_emphasis_parsed_for_all_modes() -> None:
    plan = protocol.load_plan(REPO_ROOT)
    for mode in ["A", "B", "C", "D", "Other"]:
        assert mode in plan.mode_emphasis, f"missing emphasis for mode {mode}"
        assert plan.mode_emphasis[mode].strip(), f"empty emphasis for mode {mode}"
    # Spot-check known content from the protocol file.
    assert "tenant setup" in plan.mode_emphasis["A"]
    assert "deploy pipeline" in plan.mode_emphasis["B"]
    assert "tenancy model" in plan.mode_emphasis["C"]
    assert "lineage" in plan.mode_emphasis["D"]


def test_base_system_prompt_contains_protocol_text() -> None:
    plan = protocol.load_plan(REPO_ROOT)
    assert "System Context Interviewer" in plan.base_system_prompt
    assert "Do not continue until a mode is selected" in plan.base_system_prompt
