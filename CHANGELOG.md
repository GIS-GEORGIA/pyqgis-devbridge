# Changelog

## [Unreleased]
### Added
- "How to use" tab (first tab of the panel) and a "How to use" button in the desktop tool: step-by-step
  instructions in English / Georgian (prepare once, then VS Code or PyCharm).
- One debugger per QGIS session: debugpy (VS Code) and pydevd-pycharm both load a pydevd under the same module
  names, so the second one is refused with an explanation instead of a traceback / crash.
- **DevBridge Control Panel** in QGIS (Plugins > DevBridge > Control Panel + toolbar button): tabs for the
  VS Code bridge, PyCharm bridge, "prepare a plugin" (runs the setup in a worker thread with a live log,
  Open folder / Open in VS Code) and the desktop tool; EN/KA switch; the menu relabels with it.
- Standalone desktop tool bundled in the plugin zip under `tool/` (`python -m devbridge gui`, or double-click
  `devbridge_gui.pyw`), launchable from the panel; GUI now edits the shared settings and can open the folder
  / VS Code and install the plugin. Shared JSON settings file (`devbridge.config` / `qgis_plugin/shared_config.py`).
- `make_plugin_zip.py` builds the reproducible `DevBridge.zip` for plugins.qgis.ge; `tools/qgis_headless_check.py`
  loads it in a real QGIS 3.44 / 4.2 and drives the panel.
- Plugin metadata: QGIS 3.40 - 4.99 universal build (`supportsQt6`), all Qt code uses scoped enums / `exec()`.
- One-shot scripts (`scripts/install.ps1`, `install.cmd`, `install.sh`): install the CLI,
  link + enable the DevBridge plugin in your QGIS profile, then set up a profile plugin.
- `devbridge install-plugin` (`--profile`, `--copy`, `--force`): links (junction/symlink)
  `qgis_plugin/` into the profile and sets `DevBridge=true` in the QGIS settings file
  unless QGIS is running.
- `devbridge setup` now takes the plugin from your QGIS profile folder by default
  (`--plugin NAME`, `--profile NAME`; numbered picker when several); new
  `devbridge plugins` command; plugin dropdown in the GUI. `--project-dir`
  still works and wins when given.
- macOS QGIS detector (`detectors/macos.py`: `QGIS*.app` bundles in
  `/Applications` and `~/Applications`, plus Homebrew/conda import probe) and
  `detectors.get_detector()` for per-OS selection; `macos-latest` added to CI.
- `qgis_plugin/icon.png` (required by `metadata.txt`).
- `qgis_plugin/pycharm_bridge.py`: detects the installed PyCharm build
  (`build.txt`), resolves and installs the matching `pydevd-pycharm`
  version from PyPI, and connects — via a new "Auto-configure & Start
  PyCharm Bridge" plugin menu action. Manual `.pycharm-debug/` steps
  remain as the documented fallback for setups it can't detect.
### Fixed
- PyCharm bridge: `pip` was run with `sys.executable`, which inside QGIS is the QGIS program itself. It now finds
  the matching Python from the interpreter prefix, installs pydevd-pycharm with `--target` into
  `<settings dir>/pydevd` (no rights needed on QGIS's folders), streams pip's output to the panel and runs it on a
  worker thread. The generated attach script adds that folder to `sys.path`.
- PyCharm bridge: connecting while no PyCharm server listened could crash QGIS (pydevd left half-installed in the Qt
  event loop). The port is now checked first and a failed `settrace` is cleaned up.
- Child processes (venv, pip) now stream their output to the log (visible inside QGIS / the GUI) instead of
  vanishing, do not flash a console window on Windows, and pip retries with `--user` when the QGIS Python lives
  in a read-only folder such as `C:\Program Files\QGIS 3.44.5`.
- Windows detector finds any `Program Files\QGIS x.y.z` standalone install, not just 3.34/3.28.
- CLI no longer crashes printing Georgian on legacy (cp1252) Windows consoles.
- venv `site-packages` lookup no longer assumes the host Python's minor
  version matches the QGIS-bundled interpreter that created the venv.

## [0.1.0] - unreleased
### Added
- Initial `devbridge` CLI + Tkinter GUI: QGIS detection (Windows/Linux),
  venv builder, debugpy installer, VS Code config writer, PyCharm notes.
- Initial `DevBridge` QGIS plugin: debugpy bridge, bilingual EN/KA menu,
  settings dialog.
- Bilingual docs (`docs/en/`, `docs/ka/`) and README.
- Unit tests for detectors, env builder, and i18n loader.
