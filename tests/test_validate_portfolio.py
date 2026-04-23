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
