# Contributing / წვლილის შეტანა

- Keep `qgis_plugin/` self-contained: it must never `import` from
  `src/devbridge`. QGIS copies the plugin folder as-is into a user's
  profile; it can't rely on the CLI package being pip-installed.
- Keep `qgis_plugin/debug_bridge.py` free of `qgis.*` imports so it stays
  unit-testable with plain `pytest`.
- New UI strings go in **both** `src/devbridge/i18n/{en,ka}.json` and
  `qgis_plugin/i18n/{en,ka}.json` — whichever side they belong to.
- Run `pytest` before opening a PR: `pip install -e ".[dev]" && pytest`.
- macOS detector support is a known gap — contributions welcome in
  `src/devbridge/detectors/macos.py` following the pattern in
  `windows.py` / `linux.py`.

## Publishing the VS Code extension

`release.yml` publishes `extensions/vscode` on every `v*` tag. One-time setup:

1. **VS Code Marketplace** - create the `gis-georgia` publisher at
   <https://marketplace.visualstudio.com/manage>, then an Azure DevOps personal access token
   (scope *Marketplace > Manage*, organization *All accessible organizations*) and store it as the
   repository secret `VSCE_PAT`.
2. **Open VSX** (VSCodium, Cursor, etc.) - sign in at <https://open-vsx.org>, create the `gis-georgia`
   namespace (`npx ovsx create-namespace gis-georgia -p <token>`) and store the token as `OVSX_PAT`.

To release a new extension version, bump `version` in `extensions/vscode/package.json` (and
`package-lock.json`) before tagging. If the version is already published, the publish steps are skipped.
