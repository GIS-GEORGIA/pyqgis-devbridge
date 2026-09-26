# Installation

## Quick start (everything automated)

Windows (PowerShell or double-click / cmd):

```powershell
scripts\install.cmd                          # pick the plugin from a list
scripts\install.cmd -Plugin selection_tools  # or by name
scripts\install.cmd -Lang ka -Force          # Georgian UI; replace an old DevBridge copy
```

Linux / macOS:

```bash
scripts/install.sh                            # pick the plugin from a list
scripts/install.sh --plugin selection_tools
```

This installs the CLI, links the DevBridge plugin into your QGIS profile
and enables it, then prepares the chosen plugin (venv, debugpy, VS Code
config). Afterwards restart QGIS. Re-running is safe. Useful switches:
`-SkipBridge` / `-SkipSetup` (`--skip-bridge` / `--skip-setup`),
`-ProjectDir` (`--project-dir`) for any folder, `-Copy` to copy instead of
link. If QGIS is running, its settings file is left alone: tick DevBridge in
the Plugin Manager or close QGIS and re-run. The manual steps below do the
same thing one at a time.

## 1. Standalone setup tool (CLI + GUI)

Requires Python 3.9+ already on your PATH (any Python, not necessarily
QGIS's bundled one — it only needs to be able to create a venv and run
pip).

```bash
git clone https://github.com/GIS-GEORGIA/pyqgis-devbridge.git
cd pyqgis-devbridge
pip install -e .
```

Run it. It takes your plugin straight from your QGIS profile's
`python/plugins` folder, so edits are live in QGIS too:

```bash
devbridge plugins                      # list plugins found in your profile
devbridge setup                        # auto if there is one, numbered picker if several
devbridge setup --plugin MyPlugin      # or pick by name
devbridge setup --project-dir /path/to/folder   # any other folder instead
```

Or launch the GUI:

```bash
devbridge gui
```

This will:
1. Detect your QGIS installation (Windows: OSGeo4W / standalone installer
   layouts; Linux: system `python3` with `import qgis` working, or common
   static paths; macOS: `/Applications/QGIS*.app` bundle, or any `python3`
   that can already `import qgis`).
2. Create a `--system-site-packages` virtual environment linked to QGIS's
   Python bindings (`qgis.pth`), with the Windows DLL-directory shim
   (`sitecustomize.py`) applied automatically where needed.
3. Install `debugpy` into both QGIS's interpreter and the venv.
4. Write `.vscode/settings.json` and `.vscode/launch.json` (an "Attach to
   running QGIS" configuration).
5. Write `.pycharm-debug/README.{en,ka}.md` with manual PyCharm steps
   (see the note in that file for why this part isn't fully automated).

## 2. QGIS plugin (DevBridge)

Copy (or symlink during development) `qgis_plugin/` into your QGIS
profile's plugin folder, named `DevBridge`:

- Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/DevBridge`
- macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/DevBridge`
- Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\DevBridge`

Then enable it from **Plugins → Manage and Install Plugins → Installed**.

A packaged `.zip` suitable for the QGIS Plugin Repository can be built
with:

```bash
cd qgis_plugin
zip -r ../DevBridge.zip . -x "__pycache__/*"
```
