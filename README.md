# Grandakun DCC MCP Catalog

Public source of truth for the DCC MCP repositories maintained under
`grandakun-dcc`.

## Validate

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python scripts/validate_catalog.py
```

`catalog/releases.lock.yaml` records only combinations that have been verified.
Do not point production configuration at an unpinned branch.

Blender is installed from its external published package rather than cloned
from this workspace. The verified dependency is `mcp-for-blender==2.3.1`:

```powershell
uvx mcp-for-blender setup
```

## Maya extension workspace

`dcc_maya` is the only MCP server that agents configure. Installed Adapter
packages register through `grandakun.maya_mcp.extensions` and are enabled on the
next server start unless their extension ID is listed in
`DCC_MAYA_DISABLED_EXTENSIONS`.

```powershell
# Show clone/fetch/checkout actions without changing the workspace.
pwsh -File scripts/bootstrap.ps1 -DryRun

# Optionally install maya-mcp plus all three Adapters into an explicit Python.
pwsh -File scripts/bootstrap.ps1 `
  -Python <maya-mcp-python.exe> `
  -InstallExtensions

# Check repositories, locked versions/SHA256, installed packages and Entry Points.
pwsh -File scripts/doctor.ps1 `
  -Python <maya-mcp-python.exe>
```

Both scripts derive the workspace root from the parent directory of
`dcc-mcp-catalog`, so the complete workspace can be renamed or moved without
editing configuration. Pass `-WorkspaceRoot` only when managing a different
workspace. Bootstrap refuses repositories with local changes, fetches the
remote, and checks out the exact verified commit in detached-HEAD mode.

The Catalog derives the verified Maya combination as 71 base tools, 25 xiaota
tools, 2 HairPin tools plus 2 compatibility aliases, and 6 OpenAIGenMaya tools.
No handwritten `combined_tools` value is stored.

The private repositories `grandakun/xiaota`, `grandakun/HairPinMaya`, and
`grandakun/OpenAIGenMaya` are recorded only as migration rollback sources.
Bootstrap and doctor do not clone, fetch, install, archive, or otherwise modify
them. Their `main` branches remain fixed until local/P4V validation, rollback
rehearsal, and explicit owner confirmation are complete.
