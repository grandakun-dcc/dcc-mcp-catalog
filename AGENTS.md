# Repository guidance

- Keep this repository free of credentials and user-specific absolute paths.
- Treat `catalog/servers.yaml` as the source of truth for repository identities.
- Update release locks only after the corresponding repository tests pass.
- Preserve private visibility for the Maya tool Adapter repositories.
- Preserve upstream Fork relationships for Maya, Substance Painter, and Marmoset.
- Run `python -m pytest -q` and `python scripts/validate_catalog.py` before commit.
