import subprocess
from copy import deepcopy
from types import SimpleNamespace

import pytest
from validate_catalog import (
    CatalogError,
    _repository_rows,
    _run_git_check,
    combined_tool_count,
    inspect_installed_extensions,
    validate_catalog,
)


@pytest.fixture
def valid_catalog():
    return {
        "schema_version": 1,
        "servers": [
            {
                "id": "dcc_maya",
                "repository": "grandakun-dcc/maya-mcp",
                "visibility": "public",
                "kind": "fork",
                "upstream": "GimbalGoats/GG_MayaMCP",
                "version": "0.6.1",
                "tools": 71,
            },
            {
                "id": "dcc_zbrush",
                "repository": "grandakun-dcc/zbrush-mcp",
                "visibility": "public",
                "kind": "owned",
                "version": "0.1.0-dev",
                "tools": 29,
            },
        ],
        "extensions": [
            {
                "id": "maya_xiaota",
                "extension_id": "xiaota",
                "repository": "grandakun-dcc/maya-tools-xiaota",
                "visibility": "private",
                "extends": "dcc_maya",
                "adapter_package": "maya-tools-xiaota-mcp",
                "adapter_version": "5.1.0",
                "auto_enable_when_installed": True,
                "entry_point": {
                    "group": "grandakun.maya_mcp.extensions",
                    "name": "xiaota",
                    "value": "xiaota_mcp.extension:get_extension",
                },
                "tool_names": ["xiaota_one"],
                "compatibility_aliases": [],
            }
        ],
        "legacy_repositories": [
            {
                "id": "legacy_xiaota",
                "repository": "grandakun/xiaota",
                "visibility": "private",
                "role": "migration_rollback",
                "baseline_commit": "663804d2d89377e8499dd6ace71420b3e196c3ba",
                "archive_allowed": False,
            }
        ],
    }


@pytest.fixture
def valid_compatibility():
    return {
        "schema_version": 1,
        "compatibility": {
            "dcc_maya": {"server_version": "0.6.1", "dcc_versions": ["2024"]},
            "dcc_zbrush": {
                "server_version": "0.1.0-dev",
                "dcc_versions": ["2027"],
            },
            "maya_xiaota": {
                "adapter_version": "5.1.0",
                "base_server": "dcc_maya",
                "dcc_versions": ["2024"],
            },
        },
    }


@pytest.fixture
def valid_releases():
    return {
        "schema_version": 1,
        "releases": {
            "dcc_maya": {"version": "0.6.1", "commit": "7c62dac"},
            "dcc_zbrush": {"version": "0.1.0-dev", "commit": "33159c4"},
            "maya_xiaota": {"adapter_version": "5.1.0", "commit": "42865d5"},
        },
    }


def test_valid_catalog_has_no_errors(
    valid_catalog, valid_compatibility, valid_releases
):
    assert validate_catalog(valid_catalog, valid_compatibility, valid_releases) == []
    assert combined_tool_count(valid_catalog, "dcc_maya") == 72


def test_duplicate_ids_are_rejected(valid_catalog):
    data = deepcopy(valid_catalog)
    data["servers"].append(deepcopy(data["servers"][0]))

    with pytest.raises(CatalogError, match="duplicate id: dcc_maya"):
        validate_catalog(data)


def test_extension_requires_all_runtime_fields(valid_catalog):
    data = deepcopy(valid_catalog)
    del data["extensions"][0]["entry_point"]

    with pytest.raises(CatalogError, match="maya_xiaota: missing entry_point"):
        validate_catalog(data)


def test_extension_must_extend_maya_and_auto_enable(valid_catalog):
    data = deepcopy(valid_catalog)
    data["extensions"][0]["extends"] = "dcc_zbrush"

    with pytest.raises(CatalogError, match="must extend dcc_maya"):
        validate_catalog(data)

    data = deepcopy(valid_catalog)
    data["extensions"][0]["auto_enable_when_installed"] = False
    with pytest.raises(CatalogError, match="must auto-enable when installed"):
        validate_catalog(data)


def test_entry_point_name_must_match_extension_id(valid_catalog):
    data = deepcopy(valid_catalog)
    data["extensions"][0]["entry_point"]["name"] = "other"

    with pytest.raises(CatalogError, match="Entry Point name must match extension_id"):
        validate_catalog(data)


def test_duplicate_tool_names_are_rejected(valid_catalog):
    data = deepcopy(valid_catalog)
    second = deepcopy(data["extensions"][0])
    second.update(
        {
            "id": "maya_hairpin",
            "extension_id": "hairpin",
            "repository": "grandakun-dcc/maya-tools-hairpin",
            "adapter_package": "maya-tools-hairpin-mcp",
            "entry_point": {
                "group": "grandakun.maya_mcp.extensions",
                "name": "hairpin",
                "value": "hairpin_mcp.extension:get_extension",
            },
        }
    )
    data["extensions"].append(second)

    with pytest.raises(CatalogError, match="duplicate tool name: xiaota_one"):
        validate_catalog(data)


def test_release_and_compatibility_versions_must_match(
    valid_catalog, valid_compatibility, valid_releases
):
    releases = deepcopy(valid_releases)
    releases["releases"]["maya_xiaota"]["adapter_version"] = "5.0.0"

    with pytest.raises(CatalogError, match="release adapter_version must equal 5.1.0"):
        validate_catalog(valid_catalog, valid_compatibility, releases)

    compatibility = deepcopy(valid_compatibility)
    compatibility["compatibility"]["maya_xiaota"]["base_server"] = "missing"
    with pytest.raises(CatalogError, match="compatibility base_server must equal dcc_maya"):
        validate_catalog(valid_catalog, compatibility, valid_releases)


def test_every_installable_repository_requires_a_locked_commit(
    valid_catalog, valid_compatibility, valid_releases
):
    releases = deepcopy(valid_releases)
    del releases["releases"]["dcc_zbrush"]["commit"]

    with pytest.raises(CatalogError, match="dcc_zbrush: missing release commit"):
        validate_catalog(valid_catalog, valid_compatibility, releases)


def test_repository_rows_include_locked_commits(valid_catalog, valid_releases):
    assert _repository_rows(valid_catalog, valid_releases) == [
        ("grandakun-dcc/maya-mcp", "maya-mcp", "7c62dac"),
        ("grandakun-dcc/zbrush-mcp", "zbrush-mcp", "33159c4"),
        ("grandakun-dcc/maya-tools-xiaota", "maya-tools-xiaota", "42865d5"),
    ]


def test_git_check_rejects_revision_mismatch(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", str(repository)], check=True, capture_output=True)
    (repository / "file.txt").write_text("locked", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "file.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Catalog Tests",
            "-c",
            "user.email=catalog-tests@example.invalid",
            "commit",
            "-m",
            "test",
        ],
        check=True,
        capture_output=True,
    )

    errors = _run_git_check(
        tmp_path,
        [("grandakun-dcc/repo", "repo", "0" * 40)],
    )

    assert errors == ["grandakun-dcc/repo: revision does not match locked commit"]


def test_legacy_rollback_repository_cannot_be_archived(valid_catalog):
    data = deepcopy(valid_catalog)
    data["legacy_repositories"][0]["archive_allowed"] = True

    with pytest.raises(CatalogError, match="archive_allowed must be false"):
        validate_catalog(data)


def test_installed_extensions_check_package_entry_point_version_and_tools(valid_catalog):
    extension = SimpleNamespace(
        id="xiaota", version="5.1.0", tool_names=("xiaota_one",)
    )
    entry_point = SimpleNamespace(
        name="xiaota",
        value="xiaota_mcp.extension:get_extension",
        load=lambda: lambda: extension,
    )

    assert inspect_installed_extensions(
        valid_catalog,
        package_versions={"maya-tools-xiaota-mcp": "5.1.0"},
        entry_points=[entry_point],
        disabled_ids=set(),
    ) == []

    errors = inspect_installed_extensions(
        valid_catalog,
        package_versions={"maya-tools-xiaota-mcp": "5.0.0"},
        entry_points=[entry_point],
        disabled_ids={"xiaota"},
    )
    assert "xiaota: installed version 5.0.0, expected 5.1.0" in errors
    assert "xiaota: disabled by DCC_MAYA_DISABLED_EXTENSIONS" in errors
