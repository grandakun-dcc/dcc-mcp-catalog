from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.ps1"
DOCTOR = ROOT / "scripts" / "doctor.ps1"


def run_ps1(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(script), *args],
        text=True,
        capture_output=True,
        encoding="utf-8",
    )


def test_bootstrap_rejects_file_as_workspace_root(tmp_path):
    target = tmp_path / "not-a-directory"
    target.write_text("occupied", encoding="utf-8")

    result = run_ps1(BOOTSTRAP, "-WorkspaceRoot", str(target), "-DryRun")

    assert result.returncode != 0
    assert "not a directory" in (result.stdout + result.stderr).lower()


def test_bootstrap_rejects_existing_non_git_repository_directory(tmp_path):
    target = tmp_path / "workspace"
    (target / "maya-mcp").mkdir(parents=True)

    result = run_ps1(BOOTSTRAP, "-WorkspaceRoot", str(target), "-DryRun")

    assert result.returncode != 0
    assert "exists but is not a git repository" in (result.stdout + result.stderr)


def test_bootstrap_rejects_invalid_git_metadata(tmp_path):
    target = tmp_path / "workspace"
    (target / "maya-mcp" / ".git").mkdir(parents=True)

    result = run_ps1(BOOTSTRAP, "-WorkspaceRoot", str(target), "-DryRun")

    assert result.returncode != 0
    assert "exists but is not a git repository" in (result.stdout + result.stderr)


def test_bootstrap_dry_run_lists_managed_repositories(tmp_path):
    target = tmp_path / "workspace"

    result = run_ps1(BOOTSTRAP, "-WorkspaceRoot", str(target), "-DryRun")

    assert result.returncode == 0, result.stderr
    assert "grandakun-dcc/maya-mcp" in result.stdout
    assert "grandakun-dcc/maya-tools-xiaota" in result.stdout
    assert "grandakun-dcc/zbrush-mcp" in result.stdout


def test_doctor_fails_for_missing_repository(tmp_path):
    target = tmp_path / "workspace"
    target.mkdir()

    result = run_ps1(DOCTOR, "-WorkspaceRoot", str(target))

    assert result.returncode != 0
    assert "MISSING" in result.stdout


def test_doctor_reports_invalid_git_metadata(tmp_path):
    target = tmp_path / "workspace"
    (target / "maya-mcp" / ".git").mkdir(parents=True)

    result = run_ps1(DOCTOR, "-WorkspaceRoot", str(target))

    assert result.returncode != 0
    assert "NOT_GIT\tmaya-mcp" in result.stdout
