from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs" / "codex-config.example.toml"


def test_codex_config_example_is_safe_and_parseable():
    raw = EXAMPLE.read_text(encoding="utf-8")
    config = tomllib.loads(raw)
    servers = config["mcp_servers"]

    assert set(servers) == {
        "dcc_maya",
        "dcc_zbrush",
        "dcc_substance_painter",
        "dcc_marmoset",
    }
    assert all(server["enabled"] is False for server in servers.values())
    assert all("<" in server["command"] for server in servers.values())
    assert servers["dcc_zbrush"]["args"] == ["serve"]
    assert servers["dcc_maya"]["args"] == [
        "<MAYA_TOOLS_XIAOTA>/tools/mcp_server.py"
    ]
    assert "token" not in raw.lower()
    assert "api_key" not in raw.lower()
