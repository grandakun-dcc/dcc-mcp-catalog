# Grandakun DCC MCP Catalog

Private source of truth for the DCC MCP repositories maintained under
`grandakun-dcc`.

## Validate

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/validate_catalog.py
```

`catalog/releases.lock.yaml` records only combinations that have been verified.
Do not point production configuration at an unpinned branch.

## Local workspace

Preview or create/update the standard Windows workspace:

```powershell
./scripts/bootstrap.ps1 -WorkspaceRoot D:\Dev\Grandakun-DCC -DryRun
./scripts/bootstrap.ps1 -WorkspaceRoot D:\Dev\Grandakun-DCC
./scripts/doctor.ps1 -WorkspaceRoot D:\Dev\Grandakun-DCC
```

`bootstrap.ps1` refuses to overwrite an existing non-Git directory. Existing
repositories are fetched but not automatically merged, rebased or switched, so
local branches and uncommitted work remain under the developer's control.

## Codex MCP names

Use stable client names independent of local checkout paths:

```text
dcc_maya
dcc_zbrush
dcc_substance_painter
dcc_marmoset
dcc_blender          # reserved for the later Blender migration
```

Keep `maya-tools-xiaota` behind the single `dcc_maya` server; do not register a
second Maya connector for the xiaota extension.

Use [`docs/codex-config.example.toml`](docs/codex-config.example.toml) as the
client configuration template. Every entry is disabled and uses an explicit
placeholder: replace and verify paths locally, then enable one server at a
time. Do not copy credentials into the Catalog or commit a user config file.
