# Changelog

## [Unreleased]
### Added
- `devbridge doctor` (`--project-dir`, `--port`): checks the whole chain end to end and prints a plain
  OK/FAIL line with a one-line hint for each - QGIS found, its Python can `import qgis.core`, `debugpy`
  installed (in QGIS's Python and, with `--project-dir`, the project's `.venv`), the DevBridge plugin
  installed/enabled, the port free, `.devbridge.json` and `.vscode/launch.json` present. A "Run diagnostics"
  button in the desktop tool does the same. On Windows, checking a QGIS-bundled interpreter uses its own
  `python-qgis[-<edition>].bat` wrapper - a bare `import qgis.core` on that interpreter, or reconstructing
  the wrapper's PATH/PYTHONPATH/`os.add_dll_directory` by hand, both failed against a real OSGeo4W install.
- Choosing which QGIS to use, for the (not unusual) case of several installed side by side - this machine
  has four. `devbridge detect` now lists every install found, not just the first; `--qgis-root PATH` on
  `setup`/`new`/`launch`/`doctor` targets one specifically; an interactive terminal is asked (numbered
  picker) when several are found and neither is given; the desktop tool has a "QGIS:" dropdown. Detectors
  gained `find_all_qgis()` (Windows enumerates every install; Linux/macOS wrap their single result for a
  uniform API).

- Control Panel: a "Reload plugin" picker sits above the tabs (visible regardless of which one is
  open) - pick a plugin already enabled in this QGIS session, press "Reload in QGIS", and its
  latest code runs immediately (`qgis.utils.reloadPlugin`, the same mechanism the separate
  "Plugin Reloader" plugin uses), no QGIS restart and no extra plugin needed. Plugin 0.2.3.

- `devbridge launch` (`--wait-ready`, `--wait-for-client`, `--host`/`--port`, `--qgis-project`): starts QGIS with
  the debug bridge already listening, via `qgis --code <bootstrap>` - so VS Code's F5 attaches to a QGIS that is
  already running, without a manual "Start Debug Bridge" click in the QGIS menu first. Confirmed against a real
  QGIS 3.44.5, both the standalone binary and OSGeo4W's `qgis-ltr.bat` wrapper. A "Launch QGIS (debug)" button in
  the desktop tool does the same by hand.
- `.devbridge.json`: a small, committable per-project file (host/port/plugin name/venv name) written by
  `devbridge setup` and read by `devbridge launch`; `--host`/`--plugin-name` on `setup` (plugin name is
  auto-detected when the target already lives in `<profile>/python/plugins/<name>`).
- VS Code: a second launch configuration, "PyQGIS: Launch QGIS + attach", backed by a task that runs
  `devbridge launch --wait-ready`; `pathMappings` for a plugin loaded from the QGIS profile so breakpoints in a
  symlinked/copied-in workspace resolve correctly.
- New plugin or existing one: the panel's "Prepare a plugin" tab (and the desktop tool) now start with a choice - **Improve an existing plugin**
  (a list over *every* QGIS profile, QGIS3 and QGIS4, nothing pre-selected), **Start a NEW plugin** (name + where; writes a working Qt5/Qt6
  starter plugin, then prepares it) or **Any folder**. CLI: `devbridge new my_plugin`, and the picker of `devbridge setup` offers "N. Start a NEW plugin"
  (also when the profile has no plugins yet). `src/devbridge/scaffold.py` writes the starter files.
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
- Windows detector: `bin_dirs` (the DLL search path used both for a venv's `sitecustomize.py` and by
  `doctor`) hardcoded `apps/qgis/bin`, missing `apps/qgis-ltr/bin` entirely on an LTR/"-ltr" edition install
  - confirmed against a real OSGeo4W "qgis-ltr" install, where the directory holding `qgis_core.dll` itself
    was never on the search path. Now derived from the same install's own detected edition.
- Desktop GUI: `_selected_qgis()`/`self.mode.get()` (Tk widgets/variables) were read from inside background
  worker threads (setup, launch, and now doctor) - Tkinter is not thread-safe there and this could raise
  `RuntimeError: main thread is not in main loop`. Now read on the main thread before the thread starts.
- The interactive pickers (plugin, QGIS install, new-plugin name) called `input()` after checking
  `sys.stdin.isatty()`, which can still lie in some wrapped/piped terminals; a subsequent EOF crashed with
  an uncaught `EOFError` instead of falling back to the non-interactive default.

- A real (non-editable) wheel silently dropped the `i18n/*.json` files - `pip install -e .`, used throughout this
  repo's own testing, never caught it, because an editable install just points back at the source tree. Confirmed
  by building an actual wheel and installing it into a clean venv, both before (missing files, `FileNotFoundError`
  on any non-English string) and after adding `[tool.setuptools.package-data]`.
- **Critical: the VS Code debug bridge (`qgis_plugin/debug_bridge.py`) never told debugpy which Python to use.**
  Inside QGIS, `debugpy.listen()` spawns its adapter subprocess through `sys.executable`, which there is the QGIS
  program itself; the adapter never started and `listen()` failed ~20-30s later with "timed out waiting for
  adapter to connect" - confirmed against a real, running QGIS 3.44.5, every single time, meaning "Start Debug
  Bridge (VS Code)" was non-functional as shipped in 0.2.1. `debugpy.configure(python=...)` is now called first,
  using the same interpreter-finding logic as the PyCharm bridge (`qgis_plugin/pyexe.py`, now shared by both).
  Also: a second `listen()` (plugin reload) is now treated as already-running instead of raising. Plugin 0.2.2.
- `devbridge setup` used to overwrite `.vscode/settings.json` and `launch.json` outright, destroying anything the
  user had added there. Both files (and the new `tasks.json`) are now merged: our entries are upserted by
  name/label, everything else is kept. A file that isn't strict JSON (VS Code tolerates comments there) is left
  untouched, with the content we would have written saved next to it as `*.devbridge-suggested.json`.
- `devbridge launch`: a launch process that exits 0 almost immediately used to be reported as a failed launch.
  Confirmed against a real OSGeo4W install: its `qgis*.bat` wrappers `start /B` the real `qgis*-bin.exe` as a
  detached grandchild and return 0 right away, while QGIS keeps loading for another 20-40s in the background. Only
  a non-zero exit is now treated as a real failure; zero keeps polling the ready file until the timeout.
- The panel listed only the running QGIS profile and silently pre-selected its first plugin (e.g. `postgis_manager` in QGIS 4 hid the QGIS 3 plugins).
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
