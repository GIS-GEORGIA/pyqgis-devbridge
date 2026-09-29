# Usage

## The Control Panel (recommended)

Plugins → DevBridge → **Control Panel** (also a toolbar button). A **"Reload plugin"** picker sits at the
top, visible regardless of which tab you're on: pick a plugin already enabled in this QGIS session and press
*Reload in QGIS* to re-import its code and restart it — the same trick the separate "Plugin Reloader" plugin
does, built in here so an edit-in-VS-Code / see-it-live loop needs no extra plugin and no QGIS restart. Five
tabs below it, language switch (English / ქართული) at the very top, in the order you'll actually use them:

- **How to use** — the step-by-step instructions (first tab).
- **Prepare a plugin** — first choose what you want: *Improve an existing plugin* (the list covers every QGIS profile, QGIS 3 and 4), *Start a NEW plugin* (type a lowercase name; DevBridge writes a small working starter plugin into your profile's plugins folder) or *Any folder*. Then press
  *Prepare for debugging*: creates `.venv`, installs `debugpy`, writes `.vscode/launch.json`. Progress and
  pip output appear in the log. *Open folder* / *Open in VS Code* do what they say.
- **VS Code** — host/port, *Start / Stop debug bridge*, status.
- **PyCharm** — host/port, *Auto-configure & start*, *Stop*, manual instructions.
- **Desktop tool** — *Launch desktop tool* opens the standalone window (same operations, no QGIS
  needed, also lets you install/enable the plugin in your profile); *Open tool folder* opens the folder
  it lives in. Needs a Python with Tk on the machine (python.org installers include it).

Only one debugger per QGIS session: VS Code (debugpy) or PyCharm (pydevd) — to switch, restart QGIS.

## VS Code extension (optional)

A thin extension (`extensions/vscode/`, no debugging logic of its own — it calls this same CLI and starts VS
Code's own `debugpy` attach) adds the commands **DevBridge: Launch QGIS with debugger and attach**, **... Attach
to running QGIS**, **... Set up PyQGIS environment for this folder** and **... Detect QGIS installation**, plus a
status bar button. Not on the Marketplace yet — build it yourself:

```bash
cd extensions/vscode
npm install && npm test
npm run package                                    # -> devbridge-vscode-<version>.vsix
code --install-extension devbridge-vscode-*.vsix
```

Compiling, its own unit tests (string tables, config parsing, CLI-argument building) and packaging are all
green; the actual VS Code attach flow has not been exercised in a real VS Code window in this repo's history yet.

## Starting QGIS with the bridge already listening

`devbridge setup` also writes `.devbridge.json` (host/port/plugin name) and a second VS Code launch
configuration, **"PyQGIS: Launch QGIS + attach"**. Pressing F5 with it selected runs
`devbridge launch --wait-ready`, which starts QGIS via `qgis --code`, waits for the bridge to report ready, and
only then lets VS Code attach — no manual "Start Debug Bridge" click needed first. From a terminal:
`devbridge launch --wait-ready`; the desktop tool has the same as a **"Launch QGIS (debug)"** button. Confirmed
against a real QGIS 3.44.5 (standalone install and OSGeo4W).

Settings (language, ports) are stored in one file shared by the panel, the desktop tool and the
`devbridge` command. Its location is shown on the *Desktop tool* tab.

## Several QGIS installs on one machine

If more than one QGIS is found (OSGeo4W plus one or more standalone versions is common on Windows),
`devbridge detect` lists every one instead of just the first; the desktop tool has a **"QGIS:"** dropdown
above everything else; `--qgis-root PATH` on `setup`/`new`/`launch`/`doctor` targets a specific one from a
terminal (interactive terminals are asked with a numbered picker when several are found and neither this
flag nor a single unambiguous install is available). Left alone, the first one found is used, exactly as
before this existed.

## When something isn't working: `devbridge doctor`

Checks the whole chain and prints a plain `[OK]`/`[FAIL]` line with a one-line hint for each: QGIS found,
its Python can `import qgis.core`, `debugpy` installed (in QGIS's Python, and in a project's `.venv` too
with `--project-dir`), the DevBridge plugin installed and enabled, the configured port free,
`.devbridge.json` and `.vscode/launch.json` present.

```bash
devbridge doctor                              # QGIS/debugpy/plugin/port only
devbridge doctor --project-dir /path/to/plugin  # + that project's .venv/.devbridge.json/.vscode
```

The desktop tool has the same as a **"Run diagnostics"** button, next to *Launch QGIS (debug)*.

## Port conflicts

The usual cause is a previous QGIS session (from an earlier debug run) still sitting on the port. `devbridge
setup` now checks first: if the configured port is already taken, it picks the next free one nearby, uses it
for `.devbridge.json` and `.vscode/launch.json` too, and says so in the log - no broken config gets written.
`devbridge launch` can't silently swap ports like that (VS Code's launch configuration already expects a fixed
one), so it just prints a warning and launches anyway - you may actually want to attach to the already-running
session instead. Either way, `devbridge doctor` also reports a busy port directly.

## Using a non-local host

Setting `--host`/`gui_host` to anything other than `localhost` (a real IP, `0.0.0.0`, a hostname - typically to
reach QGIS running in a VM or container) makes `setup`, `launch` and the plugin's own bridge print a warning:
`debugpy`/`pydevd` accept whoever connects, with no password or token of their own. `devbridge doctor` also
flags it when `.devbridge.json` has one. Only do this on a network you trust.

## What gets ignored by git

`devbridge setup` adds `.venv/` (your actual venv folder name), `__pycache__/` and `.pycharm-debug/` to
`.gitignore` - but only where one is relevant: an existing `.gitignore`, or a `.git/` folder right there.
A scaffolded plugin that was never `git init`-ed gets no extra file. Existing lines are never touched.

## Linking another plugin from a git checkout

`devbridge setup --project-dir X` prepares a venv and IDE config wherever `X` is, but QGIS itself only loads
plugins that live inside a profile's `python/plugins/` folder. If your plugin's repo isn't already there
(it lives elsewhere on disk, or the checkout root isn't the plugin folder itself), `link-plugin` puts it there
too, the same way `install-plugin` does for DevBridge itself:

```bash
devbridge link-plugin /path/to/my_plugin_checkout
devbridge link-plugin . --name my_plugin --profile work --force   # rename it, target one profile, replace if present
```

Linked (not copied) by default, same as DevBridge installs itself - edits at the source show up in QGIS without
re-running anything. `--copy` makes an independent copy instead.

## Removing DevBridge / cleaning up a project

```bash
devbridge uninstall                                    # remove DevBridge from every QGIS profile that has it
devbridge uninstall --project-dir /path/to/plugin      # + that project's .venv, .devbridge.json, .pycharm-debug/
                                                        #   and DevBridge's own entries in .vscode/ (never the rest of it)
devbridge uninstall --project-dir . --keep-plugin      # only clean the project, leave DevBridge installed
devbridge uninstall --name my_plugin --profile work    # uninstall something set up with link-plugin instead
```

The desktop tool has a matching **"Remove from my QGIS profile"** button next to *Install / enable* (with a
confirmation prompt); project cleanup is terminal-only for now.

## Setting a breakpoint, either way

Once the bridge is listening (Control Panel's *VS Code* tab, or `devbridge launch`) and VS Code is attached
(*Run and Debug → "PyQGIS: Attach to running QGIS"*, or already attached because you used *Launch QGIS +
attach*): set breakpoints in your plugin code or in a standalone script, trigger that code path from inside
QGIS (run your plugin's action, or run a script through the Python console), and execution pauses there.

## Debugging a standalone script (no QGIS needed)

`devbridge setup` also writes a third VS Code launch configuration, **"PyQGIS: Debug current file (no QGIS)"**
- for a plain script (a processing algorithm, a batch conversion, a unit test) that only needs `qgis.core`/
`qgis.analysis`, with no QGIS session, bridge or port involved at all. Open the script, pick that configuration
in Run and Debug, press F5 (or the green triangle) - breakpoints work immediately. All it needs is:

```python
from qgis.core import QgsApplication

qgs = QgsApplication([], False)   # False = no GUI
qgs.initQgis()
try:
    ...                            # your code
finally:
    qgs.exitQgis()
```

No `QgsApplication.setPrefixPath(...)` and no `QGIS_PREFIX_PATH` needed - confirmed for real against both an
OSGeo4W and a standalone QGIS install: the venv `devbridge setup` builds already resolves it on its own.
Setting `QGIS_PREFIX_PATH` by hand was tried first and instead broke the `qgis.core` import outright ("DLL load
failed"), so don't add it unless something specific tells you to.

`devbridge new-script my_script` writes exactly that starter file (`.py` added automatically) and prepares the
containing folder the same way `devbridge new` does for a plugin (`--dir` to choose where, default: the current
directory; `--no-setup` to only write the file). Terminal-only for now, no desktop-tool button yet.

### Without the Control Panel

Everything above can also be done from the plugin's menu directly, without opening the panel:
**Plugins → DevBridge → Start Debug Bridge (VS Code)** starts the same bridge (same message-bar confirmation,
default `localhost:5678`), then attach from VS Code as above.

## Known limitation: stopping the bridge

`debugpy` does not expose a public "close the listening socket" API.
**Stop Debug Bridge** in the plugin menu only updates the UI state (so it
won't tell you "already running" incorrectly) — the underlying socket
stays open until QGIS itself is restarted. This is documented rather than
hidden so it doesn't surprise you mid-session.

## PyCharm

PyCharm cannot attach through the same `debugpy` bridge (different wire
protocol), but the plugin now automates the setup:

1. `devbridge setup` already wrote a **"PyQGIS Debug Server"** run configuration into
   `.idea/runConfigurations/` (host/port from the shared settings, default `localhost:12345`, with the
   same path mapping the VS Code config gets when the target is a profile plugin). Open it in PyCharm's
   Run/Debug Configurations dropdown and press the bug icon (Debug) - it says "Waiting for process
   connection". No manual **+ → Python Debug Server** needed; only fall back to that if the file isn't
   there (e.g. a project from before this existed - run `devbridge setup` again to add it).
2. In QGIS: **Plugins → DevBridge → Auto-configure & Start PyCharm
   Bridge**. This detects your installed PyCharm build (via its
   `build.txt`), resolves and installs the exact matching
   `pydevd-pycharm` version from PyPI into QGIS's interpreter, and
   connects — no manual version lookup.
3. A reusable `pydevd_pycharm.settrace(...)` script matched to that
   build is also saved under your QGIS profile's `devbridge/` folder,
   for pasting into a plugin's own debug entry point later.

Note the connection direction is reversed from the VS Code bridge:
PyCharm's "Python Debug Server" is the *listener*, QGIS is the client
that connects out — so start the PyCharm-side run configuration first,
or you'll see a "could not connect" message.

If the automatic detector can't find your PyCharm (portable/unzipped
build, unusual install path, or no network to resolve the matching
`pydevd-pycharm` version), fall back to **Plugins → DevBridge → Manual
PyCharm Instructions...**, which points at
`.pycharm-debug/README.en.md` (generated by `devbridge setup`) with the
fully manual steps.

The generated run configuration's shape is cross-checked against PyCharm's own field labels (extracted
from its installed files) and a real, actively used open-source tool generating the same configuration -
see `pycharm_run_config.py`'s docstring for exactly what. Not confirmed: actually pressing Debug on it in
a real PyCharm window - if it needs a tweak, only that one file changes.

## Changing the port

```bash
devbridge setup --project-dir . --port 5679
```

or edit `.vscode/launch.json` and the plugin's **Bridge Settings...**
dialog to match.
