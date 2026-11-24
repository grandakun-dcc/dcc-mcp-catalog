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
