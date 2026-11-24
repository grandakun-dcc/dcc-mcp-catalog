from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap.ps1"
DOCTOR = ROOT / "scripts" / "doctor.ps1"


def run_ps1(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["pwsh", "-NoProfile", "-File", str(script), *args],
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )


def test_bootstrap_dry_run_lists_all_new_maya_repositories(tmp_path):
    result = run_ps1(BOOTSTRAP, "-WorkspaceRoot", str(tmp_path), "-DryRun")

    assert result.returncode == 0, result.stderr
    assert "grandakun-dcc/maya-tools-xiaota" in result.stdout
    assert "grandakun-dcc/maya-tools-hairpin" in result.stdout
    assert "grandakun-dcc/maya-tools-openaigenmaya" in result.stdout
    assert "grandakun-dcc/maya-tools-openai-gen-maya" not in result.stdout
    assert "grandakun/xiaota" not in result.stdout
    assert "grandakun/HairPinMaya" not in result.stdout
    assert "grandakun/OpenAIGenMaya" not in result.stdout


def test_bootstrap_defaults_to_catalog_parent_directory():
    result = run_ps1(BOOTSTRAP, "-DryRun")

    assert result.returncode == 0, result.stderr
    assert str(ROOT.parent / "maya-mcp") in result.stdout
    assert "D:\\Dev\\Grandakun-DCC" not in BOOTSTRAP.read_text(encoding="utf-8")
    assert "D:\\Dev\\Grandakun-DCC" not in DOCTOR.read_text(encoding="utf-8")


def test_doctor_fails_for_missing_repository(tmp_path):
    result = run_ps1(
        DOCTOR,
        "-WorkspaceRoot",
        str(tmp_path),
        "-SkipInstalledExtensions",
    )

    assert result.returncode != 0
    assert "MISSING" in result.stdout
