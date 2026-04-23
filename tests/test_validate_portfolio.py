from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "validate_portfolio.py"


def run_validate(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_examples_json_includes_quality_score() -> None:
    result = run_validate("examples", "--all", "--json")
    assert result.returncode == 0
    assert '"quality_score"' in result.stdout
    assert '"average_quality_score"' in result.stdout
    assert '"total_warnings"' in result.stdout


def test_quality_gate_enforced() -> None:
    result = run_validate("examples", "--all", "--quality-gate", "101")
    assert result.returncode == 2
    assert "--quality-gate must be between 0 and 100" in result.stdout


def test_report_written(tmp_path: Path) -> None:
    report_path = tmp_path / "validation.md"
    result = run_validate("examples", "--all", "--report", str(report_path))
    assert result.returncode == 0
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "# Portfolio Validation Report" in report_text
    assert "Quality score" in report_text


def test_enforce_freshness_requires_max_fact_age() -> None:
    result = run_validate("examples", "--all", "--enforce-freshness")
    assert result.returncode == 2
    assert "--enforce-freshness requires --max-fact-age-days" in result.stdout


def test_only_portfolios_requires_all() -> None:
    result = run_validate("examples", "--only-portfolios")
    assert result.returncode == 2
    assert "--only-portfolios requires --all" in result.stdout


def test_only_portfolios_filters_unrelated_directories(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "notes").mkdir()

    portfolio = root / "portfolio-a"
    portfolio.mkdir()
    required_files = [
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
    for file_name in required_files:
        (portfolio / file_name).write_text(
            "## Summary\n## Output Structure\n## For AI + Human Use\n## Open Questions / TBDs\n",
            encoding="utf-8",
        )

    result = run_validate(str(root), "--all", "--only-portfolios")
    assert result.returncode == 0
    assert f"Validating portfolio: {portfolio}" in result.stdout
    assert f"Validating portfolio: {root / 'notes'}" not in result.stdout


def test_freshness_gate_detects_stale_or_undated_content(tmp_path: Path) -> None:
    portfolio = tmp_path / "portfolio"
    portfolio.mkdir()

    required_files = [
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

    for file_name in required_files:
        (portfolio / file_name).write_text(
            "## Summary\n## Output Structure\n## For AI + Human Use\n## Open Questions / TBDs\n"
            "Last reviewed: 2020-01-01\n",
            encoding="utf-8",
        )

    result = run_validate(
        str(portfolio),
        "--max-fact-age-days",
        "30",
        "--enforce-freshness",
    )
    assert result.returncode == 1
    assert "stale or undated facts" in result.stdout


def test_fail_on_warnings_catches_placeholders(tmp_path: Path) -> None:
    portfolio = tmp_path / "portfolio"
    portfolio.mkdir()

    required_files = [
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

    for file_name in required_files:
        (portfolio / file_name).write_text(
            "## Summary\n## Output Structure\n## For AI + Human Use\n## Open Questions / TBDs\n"
            "TODO: fill this in\n",
            encoding="utf-8",
        )

    result = run_validate(str(portfolio), "--fail-on-warnings")
    assert result.returncode == 1
    assert "have warnings" in result.stdout
