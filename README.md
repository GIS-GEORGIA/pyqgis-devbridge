# pyqgis-devbridge

**One-command PyQGIS development environment setup + live in-QGIS
debugging bridge for VS Code, with a documented PyCharm path.**
Bilingual (English / ქართული).

Two halves, one protocol:

| Piece | What it is | Where |
|---|---|---|
| **`devbridge` CLI/GUI** | Detects QGIS, builds a matching venv, installs `debugpy`, writes `.vscode/` config | `src/devbridge/` — `pip install -e .` |
| **DevBridge plugin** | QGIS plugin that starts a `debugpy` server inside the running QGIS process | `qgis_plugin/` — copy into your QGIS profile |

```bash
pip install -e .
devbridge setup --project-dir /path/to/plugin --lang en   # or --lang ka
```
Then in QGIS: **Plugins → DevBridge → Start Debug Bridge (VS Code)**,
and in VS Code: **Run and Debug → PyQGIS: Attach to running QGIS**.

Full docs: [`docs/en/`](docs/en/installation.md) · [`docs/ka/`](docs/ka/installation.md)

---

## ქართულად

**PyQGIS-ის დამუშავების გარემოს ერთი ბრძანებით მომზადება + ცოცხალი
დებაგინგის ხიდი VS Code-სთვის, PyCharm-ის დოკუმენტირებული გზით.**
ორენოვანი (ინგლისური / ქართული).

ორი ნაწილი, ერთი პროტოკოლი:

| ნაწილი | რა არის | სად |
|---|---|---|
| **`devbridge` CLI/GUI** | პოულობს QGIS-ს, აწყობს შესაბამის venv-ს, აყენებს `debugpy`-ს, წერს `.vscode/` კონფიგურაციას | `src/devbridge/` — `pip install -e .` |
| **DevBridge plugin** | QGIS plugin, რომელიც გაშვებულ QGIS პროცესში `debugpy` სერვერს იწყებს | `qgis_plugin/` — დააკოპირეთ QGIS პროფილში |

```bash
pip install -e .
devbridge setup --project-dir /path/to/plugin --lang ka
```
შემდეგ QGIS-ში: **Plugins → DevBridge → დებაგ ხიდის გაშვება (VS Code)**,
VS Code-ში: **Run and Debug → PyQGIS: Attach to running QGIS**.

სრული დოკუმენტაცია: [`docs/ka/`](docs/ka/installation.md) · [`docs/en/`](docs/en/installation.md)

---

## Status

Alpha / experimental. Windows + Linux supported; macOS not yet covered
by the detectors (contributions welcome). See
[`docs/en/architecture.md`](docs/en/architecture.md) for design notes,
including what's deliberately *not* automated (PyCharm's version-pinned
`pydevd-pycharm`, and stopping a `debugpy` listener mid-session).

## License

MIT — see [LICENSE](LICENSE).
