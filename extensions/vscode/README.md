# PyQGIS DevBridge (VS Code)

Thin companion to the [`pyqgis-devbridge`](../../README.md) CLI. It adds
one-click PyQGIS debugging to VS Code and contains **no debugging logic of
its own** — it calls the CLI and starts VS Code's own `debugpy` attach.

| Command | What it does |
|---|---|
| **DevBridge: Launch QGIS with debugger and attach** | runs `devbridge launch --wait-ready`, then attaches using the generated `launch.json` entry |
| **DevBridge: Attach to running QGIS** | attach only (QGIS already started the bridge) |
| **DevBridge: Set up PyQGIS environment for this folder** | runs `devbridge setup` (asks for the plugin folder name → breakpoint path mapping) |
| **DevBridge: Detect QGIS installation** | runs `devbridge detect` |

Requirements: the `devbridge` CLI on `PATH` (or set `devbridge.cliCommand`),
and the *Python Debugger* extension (`ms-python.debugpy`, pulled in automatically).

Language: setting `devbridge.language` (`auto` / `en` / `ka`) controls the
extension's messages and the CLI's `--lang`; it works even if VS Code has no
Georgian display language.

Activates in folders that contain `.devbridge.json` (written by `devbridge setup`)
or when you run one of the commands.

## ქართულად

pyqgis-devbridge CLI-ის თხელი თანმხლები. ამატებს PyQGIS-ის დებაგინგს ერთი
ღილაკით და **საკუთარ დებაგინგ-ლოგიკას არ შეიცავს** — უბრალოდ იძახებს CLI-ს და
უშვებს VS Code-ის ჩვეულებრივ `debugpy` attach-ს. ბრძანებების სია ზემოთაა;
ენა იცვლება პარამეტრით `devbridge.language`.

## Build / ასაწყობად

```bash
npm install
npm test
npm run package            # -> devbridge-vscode-0.1.0.vsix
code --install-extension devbridge-vscode-0.1.0.vsix
```
