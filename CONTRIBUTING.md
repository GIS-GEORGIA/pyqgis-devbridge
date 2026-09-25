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
