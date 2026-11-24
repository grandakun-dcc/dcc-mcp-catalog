from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


class CatalogError(ValueError):
    pass


def load_catalog(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise CatalogError("catalog root must be a mapping")
    return data


def validate_catalog(data: dict[str, Any]) -> list[str]:
    if data.get("schema_version") != 1:
        raise CatalogError("schema_version must be 1")

    servers = data.get("servers", [])
    extensions = data.get("extensions", [])
    if not isinstance(servers, list) or not isinstance(extensions, list):
        raise CatalogError("servers and extensions must be lists")

    ids: set[str] = set()
    server_by_id: dict[str, dict[str, Any]] = {}
    repositories: set[str] = set()

    for item in [*servers, *extensions]:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise CatalogError("every entry requires a non-empty id")
        if item_id in ids:
            raise CatalogError(f"duplicate id: {item_id}")
        ids.add(item_id)

        repository = item.get("repository")
        if not isinstance(repository, str) or "/" not in repository:
            raise CatalogError(f"{item_id}: repository must be owner/name")
        if repository in repositories:
            raise CatalogError(f"duplicate repository: {repository}")
        repositories.add(repository)

        if item.get("visibility") not in {"public", "private"}:
            raise CatalogError(f"{item_id}: visibility must be public or private")

    for server in servers:
        server_by_id[server["id"]] = server
        if server.get("kind") not in {"owned", "fork"}:
            raise CatalogError(f"{server['id']}: kind must be owned or fork")
        if server.get("kind") == "fork" and not server.get("upstream"):
            raise CatalogError(f"{server['id']}: fork requires upstream")

    for extension in extensions:
        base_id = extension.get("extends")
        if base_id not in server_by_id:
            raise CatalogError(f"{extension['id']}: unknown base server: {base_id}")
        base_tools = server_by_id[base_id].get("tools")
        extension_tools = extension.get("tools")
        if isinstance(base_tools, int) and isinstance(extension_tools, int):
            expected = base_tools + extension_tools
            if extension.get("combined_tools") != expected:
                raise CatalogError(
                    f"{extension['id']}: combined_tools must equal {expected}"
                )

    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the DCC MCP catalog")
    parser.add_argument(
        "path",
        nargs="?",
        default="catalog/servers.yaml",
        help="Path to servers.yaml",
    )
    args = parser.parse_args(argv)
    validate_catalog(load_catalog(args.path))
    print(f"Catalog valid: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
