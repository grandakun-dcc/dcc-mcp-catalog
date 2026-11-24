from copy import deepcopy

import pytest

from validate_catalog import CatalogError, validate_catalog


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
                "tools": 71,
            },
            {
                "id": "dcc_zbrush",
                "repository": "grandakun-dcc/zbrush-mcp",
                "visibility": "private",
                "kind": "owned",
                "tools": 29,
            },
        ],
        "extensions": [
            {
                "id": "maya_xiaota",
                "repository": "grandakun-dcc/maya-tools-xiaota",
                "visibility": "private",
                "extends": "dcc_maya",
                "tools": 27,
                "combined_tools": 98,
            }
        ],
    }


def test_valid_catalog_has_no_errors(valid_catalog):
    assert validate_catalog(valid_catalog) == []


def test_duplicate_ids_are_rejected(valid_catalog):
    data = deepcopy(valid_catalog)
    data["servers"].append(deepcopy(data["servers"][0]))

    with pytest.raises(CatalogError, match="duplicate id: dcc_maya"):
        validate_catalog(data)


def test_invalid_visibility_is_rejected(valid_catalog):
    data = deepcopy(valid_catalog)
    data["servers"][0]["visibility"] = "internal"

    with pytest.raises(CatalogError, match="visibility must be public or private"):
        validate_catalog(data)


def test_extension_requires_existing_base(valid_catalog):
    data = deepcopy(valid_catalog)
    data["extensions"][0]["extends"] = "missing_maya"

    with pytest.raises(CatalogError, match="unknown base server: missing_maya"):
        validate_catalog(data)


def test_extension_combined_tool_count_must_match(valid_catalog):
    data = deepcopy(valid_catalog)
    data["extensions"][0]["combined_tools"] = 99

    with pytest.raises(CatalogError, match="combined_tools must equal 98"):
        validate_catalog(data)


def test_fork_requires_upstream(valid_catalog):
    data = deepcopy(valid_catalog)
    del data["servers"][0]["upstream"]

    with pytest.raises(CatalogError, match="fork requires upstream"):
        validate_catalog(data)
