# Changelog

## [Unreleased]
### Added
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
