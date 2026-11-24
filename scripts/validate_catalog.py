from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path
from typing import Any

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


ENTRY_POINT_GROUP = "grandakun.maya_mcp.extensions"
DISABLED_EXTENSIONS_ENV = "DCC_MAYA_DISABLED_EXTENSIONS"
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class CatalogError(ValueError):
    pass


def load_catalog(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise CatalogError("catalog root must be a mapping")
    return data


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise CatalogError(f"{key} must be a mapping")
    return value


def _require_list(data: dict[str, Any], key: str) -> list[Any]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise CatalogError(f"{key} must be a list")
    return value


def _validate_schema(data: dict[str, Any], label: str) -> None:
    if data.get("schema_version") != 1:
        raise CatalogError(f"{label} schema_version must be 1")


def _extension_tools(extension: dict[str, Any]) -> list[str]:
    return [*extension["tool_names"], *extension["compatibility_aliases"]]


def combined_tool_count(data: dict[str, Any], server_id: str) -> int:
    servers = {item["id"]: item for item in data.get("servers", [])}
    base_tools = servers.get(server_id, {}).get("tools")
    if not isinstance(base_tools, int):
        raise CatalogError(f"{server_id}: base tool count is unavailable")
    return base_tools + sum(
        len(_extension_tools(item))
        for item in data.get("extensions", [])
        if item.get("extends") == server_id
    )


def validate_catalog(
    data: dict[str, Any],
    compatibility_data: dict[str, Any] | None = None,
    releases_data: dict[str, Any] | None = None,
) -> list[str]:
    _validate_schema(data, "catalog")
    servers = _require_list(data, "servers")
    extensions = _require_list(data, "extensions")
    legacy_repositories = _require_list(data, "legacy_repositories")

    ids: set[str] = set()
    repositories: set[str] = set()
    server_by_id: dict[str, dict[str, Any]] = {}
    extension_by_id: dict[str, dict[str, Any]] = {}

    for item in [*servers, *extensions, *legacy_repositories]:
        if not isinstance(item, dict):
            raise CatalogError("catalog entries must be mappings")
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise CatalogError("every entry requires a non-empty id")
        if item_id in ids:
            raise CatalogError(f"duplicate id: {item_id}")
        ids.add(item_id)

        repository = item.get("repository")
        if not isinstance(repository, str) or repository.count("/") != 1:
            raise CatalogError(f"{item_id}: repository must be owner/name")
        if repository in repositories:
            raise CatalogError(f"duplicate repository: {repository}")
        repositories.add(repository)
        if item.get("visibility") not in {"public", "private"}:
            raise CatalogError(f"{item_id}: visibility must be public or private")

    for server in servers:
        server_id = server["id"]
        server_by_id[server_id] = server
        if server.get("kind") not in {"owned", "fork"}:
            raise CatalogError(f"{server_id}: kind must be owned or fork")
        if server.get("kind") == "fork" and not server.get("upstream"):
            raise CatalogError(f"{server_id}: fork requires upstream")
        if not isinstance(server.get("version"), str):
            raise CatalogError(f"{server_id}: missing version")

    all_tool_names: set[str] = set()
    required_extension_fields = (
        "extension_id",
        "extends",
        "adapter_package",
        "adapter_version",
        "auto_enable_when_installed",
        "entry_point",
        "tool_names",
        "compatibility_aliases",
    )
    for extension in extensions:
        extension_id = extension["id"]
        extension_by_id[extension_id] = extension
        for field in required_extension_fields:
            if field not in extension:
                raise CatalogError(f"{extension_id}: missing {field}")
        if extension["extends"] != "dcc_maya":
            raise CatalogError(f"{extension_id}: must extend dcc_maya")
        if extension["extends"] not in server_by_id:
            raise CatalogError(
                f"{extension_id}: unknown base server: {extension['extends']}"
            )
        if extension["auto_enable_when_installed"] is not True:
            raise CatalogError(f"{extension_id}: must auto-enable when installed")
        if not isinstance(extension["adapter_package"], str) or not extension[
            "adapter_package"
        ]:
            raise CatalogError(f"{extension_id}: adapter_package must be non-empty")
        if not isinstance(extension["adapter_version"], str) or not extension[
            "adapter_version"
        ]:
            raise CatalogError(f"{extension_id}: adapter_version must be non-empty")

        entry_point = extension["entry_point"]
        if not isinstance(entry_point, dict):
            raise CatalogError(f"{extension_id}: entry_point must be a mapping")
        if entry_point.get("group") != ENTRY_POINT_GROUP:
            raise CatalogError(f"{extension_id}: invalid Entry Point group")
        if entry_point.get("name") != extension["extension_id"]:
            raise CatalogError(
                f"{extension_id}: Entry Point name must match extension_id"
            )
        if not isinstance(entry_point.get("value"), str) or not entry_point["value"]:
            raise CatalogError(f"{extension_id}: Entry Point value must be non-empty")

        for field in ("tool_names", "compatibility_aliases"):
            names = extension[field]
            if not isinstance(names, list) or any(
                not isinstance(name, str) or not name for name in names
            ):
                raise CatalogError(f"{extension_id}: {field} must be tool names")
        for name in _extension_tools(extension):
            if name in all_tool_names:
                raise CatalogError(f"duplicate tool name: {name}")
            all_tool_names.add(name)

    for legacy in legacy_repositories:
        legacy_id = legacy["id"]
        if legacy.get("visibility") != "private":
            raise CatalogError(f"{legacy_id}: legacy repository must stay private")
        if legacy.get("role") != "migration_rollback":
            raise CatalogError(f"{legacy_id}: role must be migration_rollback")
        if legacy.get("archive_allowed") is not False:
            raise CatalogError(f"{legacy_id}: archive_allowed must be false")
        baseline = legacy.get("baseline_commit")
        if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-f]{40}", baseline):
            raise CatalogError(f"{legacy_id}: baseline_commit must be a full SHA")

    if compatibility_data is not None:
        _validate_schema(compatibility_data, "compatibility")
        compatibility = _require_mapping(compatibility_data, "compatibility")
        for server_id, server in server_by_id.items():
            item = compatibility.get(server_id)
            if not isinstance(item, dict):
                raise CatalogError(f"{server_id}: missing compatibility entry")
            if item.get("server_version") != server["version"]:
                raise CatalogError(
                    f"{server_id}: compatibility server_version must equal {server['version']}"
                )
        for extension_id, extension in extension_by_id.items():
            item = compatibility.get(extension_id)
            if not isinstance(item, dict):
                raise CatalogError(f"{extension_id}: missing compatibility entry")
            if item.get("base_server") != extension["extends"]:
                raise CatalogError(
                    f"{extension_id}: compatibility base_server must equal {extension['extends']}"
                )
            if item.get("adapter_version") != extension["adapter_version"]:
                raise CatalogError(
                    f"{extension_id}: compatibility adapter_version must equal "
                    f"{extension['adapter_version']}"
                )

    if releases_data is not None:
        _validate_schema(releases_data, "releases")
        releases = _require_mapping(releases_data, "releases")
        for server_id, server in server_by_id.items():
            item = releases.get(server_id)
            if not isinstance(item, dict):
                raise CatalogError(f"{server_id}: missing release lock")
            if item.get("version") != server["version"]:
                raise CatalogError(
                    f"{server_id}: release version must equal {server['version']}"
                )
        for extension_id, extension in extension_by_id.items():
            item = releases.get(extension_id)
            if not isinstance(item, dict):
                raise CatalogError(f"{extension_id}: missing release lock")
            if item.get("adapter_version") != extension["adapter_version"]:
                raise CatalogError(
                    f"{extension_id}: release adapter_version must equal "
                    f"{extension['adapter_version']}"
                )
            commit = item.get("commit")
            if commit is not None and (
                not isinstance(commit, str) or not _COMMIT_PATTERN.fullmatch(commit)
            ):
                raise CatalogError(f"{extension_id}: invalid release commit")
            if extension_id == "maya_hairpin":
                if not isinstance(item.get("asset"), str) or not item["asset"]:
                    raise CatalogError("maya_hairpin: release asset is required")
                sha256 = item.get("sha256")
                if not isinstance(sha256, str) or not _SHA256_PATTERN.fullmatch(sha256):
                    raise CatalogError("maya_hairpin: release sha256 must be 64 hex chars")

    return []


def inspect_installed_extensions(
    data: dict[str, Any],
    *,
    package_versions: dict[str, str] | None = None,
    entry_points: Iterable[Any] | None = None,
    disabled_ids: set[str] | None = None,
) -> list[str]:
    extensions = data.get("extensions", [])
    if package_versions is None:
        package_versions = {}
        for extension in extensions:
            package = extension["adapter_package"]
            try:
                package_versions[package] = metadata.version(package)
            except metadata.PackageNotFoundError:
                pass
    if entry_points is None:
        entry_points = metadata.entry_points(group=ENTRY_POINT_GROUP)
    if disabled_ids is None:
        disabled_ids = {
            value.strip()
            for value in os.environ.get(DISABLED_EXTENSIONS_ENV, "").split(",")
            if value.strip()
        }

    entry_points_by_name = {entry.name: entry for entry in entry_points}
    errors: list[str] = []
    installed_tool_names: set[str] = set()
    for extension in extensions:
        extension_id = extension["extension_id"]
        package = extension["adapter_package"]
        expected_version = extension["adapter_version"]
        installed_version = package_versions.get(package)
        if installed_version is None:
            errors.append(f"{extension_id}: package {package} is not installed")
        elif installed_version != expected_version:
            errors.append(
                f"{extension_id}: installed version {installed_version}, "
                f"expected {expected_version}"
            )
        if extension_id in disabled_ids:
            errors.append(f"{extension_id}: disabled by {DISABLED_EXTENSIONS_ENV}")

        entry_point = entry_points_by_name.get(extension_id)
        if entry_point is None:
            errors.append(f"{extension_id}: Entry Point is missing")
            continue
        expected_value = extension["entry_point"]["value"]
        if entry_point.value != expected_value:
            errors.append(
                f"{extension_id}: Entry Point {entry_point.value}, expected {expected_value}"
            )
            continue
        try:
            factory = entry_point.load()
            descriptor = factory()
        except Exception as exc:  # noqa: BLE001 - installed extensions are isolated
            errors.append(f"{extension_id}: Entry Point load failed: {type(exc).__name__}")
            continue
        if descriptor.id != extension_id:
            errors.append(f"{extension_id}: descriptor id is {descriptor.id}")
        if descriptor.version != expected_version:
            errors.append(
                f"{extension_id}: descriptor version {descriptor.version}, "
                f"expected {expected_version}"
            )
        expected_tools = tuple(_extension_tools(extension))
        if tuple(descriptor.tool_names) != expected_tools:
            errors.append(f"{extension_id}: descriptor tool list does not match catalog")
        for tool_name in descriptor.tool_names:
            if tool_name in installed_tool_names:
                errors.append(f"duplicate installed tool name: {tool_name}")
            installed_tool_names.add(tool_name)
    return errors


def validate_workspace(
    data: dict[str, Any], releases_data: dict[str, Any], workspace_root: Path
) -> list[str]:
    errors: list[str] = []
    for extension in data.get("extensions", []):
        repository_name = extension["repository"].split("/", 1)[1]
        pyproject_path = workspace_root / repository_name / "integrations" / "mcp" / "pyproject.toml"
        if not pyproject_path.is_file():
            errors.append(f"{extension['extension_id']}: missing {pyproject_path}")
            continue
        with pyproject_path.open("rb") as stream:
            project = tomllib.load(stream).get("project", {})
        if project.get("name") != extension["adapter_package"]:
            errors.append(f"{extension['extension_id']}: adapter package name mismatch")
        if project.get("version") != extension["adapter_version"]:
            errors.append(f"{extension['extension_id']}: adapter package version mismatch")
        entry_points = project.get("entry-points", {}).get(ENTRY_POINT_GROUP, {})
        expected_entry = extension["entry_point"]
        if entry_points.get(expected_entry["name"]) != expected_entry["value"]:
            errors.append(f"{extension['extension_id']}: pyproject Entry Point mismatch")

    hairpin_lock_path = workspace_root / "maya-tools-xiaota" / "hairpin.lock.yaml"
    if hairpin_lock_path.is_file():
        hairpin_lock = load_catalog(hairpin_lock_path)
        release = releases_data.get("releases", {}).get("maya_hairpin", {})
        for field in ("version", "asset", "sha256"):
            expected_field = "adapter_version" if field == "version" else field
            if hairpin_lock.get(field) != release.get(expected_field):
                errors.append(f"maya_hairpin: workspace lock {field} mismatch")
    else:
        errors.append(f"maya_hairpin: missing {hairpin_lock_path}")
    return errors


def _repository_rows(data: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        (item["repository"], item["repository"].split("/", 1)[1])
        for item in [*data.get("servers", []), *data.get("extensions", [])]
    ]


def _run_git_check(workspace_root: Path, repository_rows: list[tuple[str, str]]) -> list[str]:
    errors: list[str] = []
    for repository, directory in repository_rows:
        path = workspace_root / directory
        if not path.is_dir():
            errors.append(f"{repository}: repository directory is missing")
            continue
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != "true":
            errors.append(f"{repository}: directory is not a git repository")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the DCC MCP catalog")
    parser.add_argument("path", nargs="?", default="catalog/servers.yaml")
    parser.add_argument("--compatibility", default="catalog/compatibility.yaml")
    parser.add_argument("--releases", default="catalog/releases.lock.yaml")
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--check-installed", action="store_true")
    parser.add_argument("--list-repositories", action="store_true")
    args = parser.parse_args(argv)

    data = load_catalog(args.path)
    compatibility = load_catalog(args.compatibility)
    releases = load_catalog(args.releases)
    validate_catalog(data, compatibility, releases)

    if args.list_repositories:
        for repository, directory in _repository_rows(data):
            print(f"{repository}\t{directory}")
        return 0

    errors: list[str] = []
    if args.workspace_root is not None:
        errors.extend(_run_git_check(args.workspace_root, _repository_rows(data)))
        errors.extend(validate_workspace(data, releases, args.workspace_root))
    if args.check_installed:
        errors.extend(inspect_installed_extensions(data))
    if errors:
        for error in errors:
            print(f"ERROR\t{error}", file=sys.stderr)
        return 1

    total = combined_tool_count(data, "dcc_maya")
    print(f"Catalog valid: {args.path}; dcc_maya installed-combination tools={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
