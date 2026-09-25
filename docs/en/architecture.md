# Architecture

```
pyqgis-devbridge/
├── src/devbridge/         # standalone CLI + GUI (pip-installable)
│   ├── detectors/         # Windows / Linux QGIS-install detection
│   ├── env_builder.py     # venv + qgis.pth + sitecustomize.py
│   ├── debugpy_installer.py
│   ├── vscode_config.py   # .vscode/settings.json + launch.json
│   ├── pycharm_config.py  # documented manual steps (see docs/usage.md)
│   ├── cli.py / gui.py
│   └── i18n/              # en.json / ka.json
└── qgis_plugin/           # DevBridge — the in-QGIS half of the bridge
    ├── debug_bridge.py    # pure debugpy wrapper, no QGIS imports
    ├── plugin.py           # QGIS menu / message-bar integration
    ├── ui/settings_dialog.py
    └── i18n/               # en.json / ka.json (mirrors src/devbridge's)
```

## Design decisions worth knowing for a book chapter

- **Two independent packages, one shared idea.** The CLI/GUI and the
  QGIS plugin do not import each other. The plugin must remain a
  self-contained folder that QGIS can copy into a user's profile; the
  CLI/GUI is a normal pip package. They agree only on a *protocol*
  (host/port + `.vscode/launch.json` shape), not on shared code.
- **`debug_bridge.py` has zero QGIS imports.** All `qgis.*` / `qgis.PyQt`
  usage lives in `plugin.py` and `ui/`. This means the bridge logic is
  unit-testable with plain `pytest`, and could be reused from the QGIS
  Python console directly without the menu UI.
- **i18n is a flat key→string JSON file, not gettext/.po.** For a
  two-language, UI-string-only project this avoids a compiled-catalog
  build step; if the project grows past EN/KA it should migrate to Qt
  Linguist `.ts`/`.qm` (QGIS's own convention) instead of scaling this
  ad hoc loader.
- **PyCharm support is automated where it can be, and honest where it
  can't.** `qgis_plugin/pycharm_bridge.py` reads the installed PyCharm's
  own `build.txt`, resolves the matching `pydevd-pycharm` release from
  PyPI (exact build number first, nearest same-major release as a
  fallback), installs it into QGIS's interpreter, and connects — all
  from one menu action. This removes the version-lookup step that used
  to be fully manual. What's *not* automated, on purpose: detecting a
  portable/unzipped PyCharm build in a non-standard location, and
  working offline (PyPI resolution needs network). Both fall back to
  the manual `.pycharm-debug/README.*.md` steps rather than failing
  silently — see `docs/*/usage.md` for the fallback path and why the
  connection direction (QGIS connects *out* to PyCharm, the reverse of
  the debugpy/VS Code bridge) matters operationally.
