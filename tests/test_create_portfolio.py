from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "create_portfolio.py"


def run_create(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_dry_run_does_not_create_destination(tmp_path: Path) -> None:
    destination = tmp_path / "new-portfolio"
    result = run_create(str(destination), "--dry-run")

    assert result.returncode == 0
    assert "WOULD COPY:" in result.stdout
    assert not destination.exists()


def test_dry_run_reports_would_skip_existing_files(tmp_path: Path) -> None:
    destination = tmp_path / "existing-portfolio"
    destination.mkdir()
    (destination / "system-identity.md").write_text("already here", encoding="utf-8")

    result = run_create(str(destination), "--dry-run")

    assert result.returncode == 0
    assert "WOULD SKIP:" in result.stdout
    assert (destination / "system-identity.md").read_text(encoding="utf-8") == "already here"
