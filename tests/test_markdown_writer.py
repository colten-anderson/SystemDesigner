from pathlib import Path
import importlib.util
import sys

import pytest

from voice_interview.markdown_writer import MIN_CONTENT_WORDS, render_file, write_portfolio
from voice_interview.orchestrator import InterviewOrchestrator
from voice_interview.protocol import REQUIRED_FILES, REQUIRED_SECTIONS, load_plan
from voice_interview.state import InterviewState

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_validator_module():
    spec = importlib.util.spec_from_file_location(
        "validate_portfolio_writer_test", REPO_ROOT / "scripts" / "validate_portfolio.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_portfolio_writer_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def plan():
    return load_plan(REPO_ROOT)


def build_completed_orchestrator(plan, tmp_path: Path) -> InterviewOrchestrator:
    state = InterviewState(output_dir=str(tmp_path / "portfolio"))
    orch = InterviewOrchestrator(plan, state, None)
    orch.set_mode("B")
    orch.set_system_fact("system_name", "Customer Billing API")
    orch.set_system_fact("owning_team", "Payments Platform")
    orch.set_system_fact("criticality_tier", "Tier 1")
    orch.set_system_fact("environments", "dev, staging, prod (AWS us-east-1)")
    result = orch.next_section()
    while result.get("section"):
        file_name = result["section"]["file"]
        section = plan.section_for(file_name)
        for index, field in enumerate(section.output_fields):
            if index % 5 == 4:
                orch.mark_unknown(
                    file_name, field, owner="Jane Doe", next_step="confirm by 2026-07-01"
                )
            else:
                orch.record_answer(
                    file_name,
                    field,
                    f"Specific recorded value for {field}: owner Payments Platform, "
                    "reviewed quarterly, see internal runbook RB-42.",
                )
        orch.record_open_question(file_name, "Anything else for this area?", "Team lead")
        orch.set_file_summary(
            file_name,
            "The team described this area in detail during the call, including "
            "concrete owners and current operational practice.",
        )
        result = orch.next_section()
    orch.end_interview()
    return orch


def test_write_portfolio_emits_all_ten_files(plan, tmp_path) -> None:
    orch = build_completed_orchestrator(plan, tmp_path)
    out_dir = tmp_path / "portfolio"
    written = write_portfolio(orch.state, plan, out_dir)
    assert [p.name for p in written] == REQUIRED_FILES
    for path in written:
        assert path.exists()


def test_rendered_files_satisfy_validator_contract(plan, tmp_path) -> None:
    validator = _load_validator_module()
    expected_fields = validator.load_expected_fields(REPO_ROOT / "templates")

    orch = build_completed_orchestrator(plan, tmp_path)
    out_dir = tmp_path / "portfolio"
    write_portfolio(orch.state, plan, out_dir)

    for file_name, fields in expected_fields.items():
        text = (out_dir / file_name).read_text(encoding="utf-8")
        headers = set(validator.extract_headers(text))
        for required in REQUIRED_SECTIONS:
            assert required in headers, f"{file_name} missing section {required}"
        filled = validator.extract_filled_output_fields(text, fields)
        unfilled = [name for name, ok in filled.items() if not ok]
        assert not unfilled, f"{file_name} has unfilled fields: {unfilled}"


def test_rendered_files_meet_word_count(plan, tmp_path) -> None:
    orch = build_completed_orchestrator(plan, tmp_path)
    out_dir = tmp_path / "portfolio"
    write_portfolio(orch.state, plan, out_dir)
    import re

    for file_name in REQUIRED_FILES:
        text = (out_dir / file_name).read_text(encoding="utf-8")
        words = [w for w in re.findall(r"\b[\w/-]+\b", text) if not w.startswith("#")]
        assert len(words) >= MIN_CONTENT_WORDS, f"{file_name}: {len(words)} words"


def test_tbd_fields_restated_in_open_questions(plan, tmp_path) -> None:
    orch = build_completed_orchestrator(plan, tmp_path)
    state = orch.state
    # Find a file with a TBD field (every 5th field was marked unknown).
    for section in plan.sections:
        fs = state.files[section.file_name]
        tbd_fields = [n for n, a in fs.fields.items() if a.status == "tbd"]
        if tbd_fields:
            text = render_file(state, section)
            open_block = text.split("## Open Questions / TBDs")[1]
            for field_name in tbd_fields:
                assert field_name in open_block
                assert "Jane Doe" in open_block
            return
    pytest.fail("expected at least one TBD field in the fixture")


def test_partial_interview_still_renders_complete_portfolio(plan, tmp_path) -> None:
    validator = _load_validator_module()
    expected_fields = validator.load_expected_fields(REPO_ROOT / "templates")

    state = InterviewState(output_dir=str(tmp_path / "portfolio"))
    orch = InterviewOrchestrator(plan, state, None)
    orch.set_mode("A")
    orch.set_system_fact("system_name", "Exchange Online")
    orch.set_system_fact("owning_team", "Messaging Team")
    orch.set_system_fact("criticality_tier", "Tier 0")
    orch.set_system_fact("environments", "prod tenant")
    first = orch.next_section()["section"]["file"]
    orch.record_answer(first, plan.section_for(first).output_fields[0], "Exchange Online for corp mail.")
    # Call drops mid-interview:
    orch.end_interview(partial=True)

    out_dir = tmp_path / "portfolio"
    write_portfolio(orch.state, plan, out_dir)
    for file_name, fields in expected_fields.items():
        text = (out_dir / file_name).read_text(encoding="utf-8")
        filled = validator.extract_filled_output_fields(text, fields)
        assert all(filled.values()), f"{file_name} unfilled after partial save"


def test_summary_falls_back_when_not_drafted(plan, tmp_path) -> None:
    state = InterviewState(output_dir=str(tmp_path / "portfolio"))
    orch = InterviewOrchestrator(plan, state, None)
    orch.set_mode("D")
    orch.set_system_fact("system_name", "Snowflake")
    orch.set_system_fact("owning_team", "Data Eng")
    orch.set_system_fact("criticality_tier", "Tier 2")
    orch.set_system_fact("environments", "prod")
    orch.end_interview(partial=True)

    text = render_file(state, plan.section_for("data.md"))
    summary = text.split("## Summary")[1].split("##")[0].strip()
    assert "Snowflake" in summary
    assert "Data Eng" in summary
