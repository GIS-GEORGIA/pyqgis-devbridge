# pyqgis-devbridge

**One-command PyQGIS development environment setup + live in-QGIS
debugging bridge for VS Code, with a documented PyCharm path.**
Bilingual (English / ქართული).

**Easiest way in:** in QGIS add the repository `https://plugins.qgis.ge/plugins.xml`
(Plugins → Manage and Install Plugins → Settings → Add), install **DevBridge**, then open
**Plugins → DevBridge → Control Panel**: start/stop the VS Code and PyCharm bridges, pick one of your
plugins and prepare it for debugging, all with buttons and in English or Georgian. The panel also
launches (or opens the folder of) a standalone desktop tool that does the same without QGIS running.

`devbridge setup` also writes a VS Code launch configuration that starts QGIS itself with the bridge already
listening (`devbridge launch`), so F5 attaches without a manual click in the QGIS menu first. A thin
[VS Code extension](extensions/vscode/) turns that into actual buttons/commands, for people who would rather
not remember CLI flags.

Two halves, one protocol:

| Piece | What it is | Where |
|---|---|---|
| **`devbridge` CLI/GUI** | Detects QGIS, builds a matching venv, installs `debugpy`, writes `.vscode/` config | `src/devbridge/` — `pip install -e .` |
| **DevBridge plugin** | QGIS plugin that starts a `debugpy` server inside the running QGIS process | `qgis_plugin/` — installed from plugins.qgis.ge, or copy into your QGIS profile |

**Full install + first-debug-session walkthrough:** [`docs/en/installation.md`](docs/en/installation.md) →
[`docs/en/usage.md`](docs/en/usage.md) · [`docs/ka/installation.md`](docs/ka/installation.md) →
[`docs/ka/usage.md`](docs/ka/usage.md).

---

## ქართულად

**PyQGIS-ის დამუშავების გარემოს ერთი ბრძანებით მომზადება + ცოცხალი
დებაგინგის ხიდი VS Code-სთვის, PyCharm-ის დოკუმენტირებული გზით.**
ორენოვანი (ინგლისური / ქართული).

**ყველაზე მარტივი გზა:** QGIS-ში დაამატეთ რეპოზიტორია `https://plugins.qgis.ge/plugins.xml`
(Plugins → Manage and Install Plugins → Settings → Add), დააყენეთ **DevBridge** და გახსენით
**Plugins → DevBridge → მართვის პანელი**: VS Code-ისა და PyCharm-ის ხიდების გაშვება/გაჩერება,
თქვენი დანამატის არჩევა და დებაგისთვის მომზადება — ყველაფერი ღილაკებით, ინგლისურად ან ქართულად.
პანელიდან შეგიძლიათ გახსნათ (ან მისი საქაღალდე გახსნათ) ცალკე დესკტოპ ხელსაწყო, რომელიც იგივეს
აკეთებს QGIS-ის გაშვების გარეშე.

`devbridge setup` ასევე წერს VS Code-ის launch კონფიგურაციას, რომელიც თავად უშვებს QGIS-ს უკვე მოქმედი
ხიდით (`devbridge launch`), რომ F5-მდე QGIS-ის მენიუში ხელით დაჭერა აღარ დაგჭირდეთ. თხელი
[VS Code extension](extensions/vscode/) ამას ღილაკებად/ბრძანებებად აქცევს, ვისაც CLI-ის ალამები არ სურს ახსოვდეს.

ორი ნაწილი, ერთი პროტოკოლი:

| ნაწილი | რა არის | სად |
|---|---|---|
| **`devbridge` CLI/GUI** | პოულობს QGIS-ს, აწყობს შესაბამის venv-ს, აყენებს `debugpy`-ს, წერს `.vscode/` კონფიგურაციას | `src/devbridge/` — `pip install -e .` |
| **DevBridge plugin** | QGIS plugin, რომელიც გაშვებულ QGIS პროცესში `debugpy` სერვერს იწყებს | `qgis_plugin/` — დაყენებულია plugins.qgis.ge-დან, ან დააკოპირეთ QGIS პროფილში |

**სრული ინსტალაცია + პირველი დებაგ სესია:** [`docs/ka/installation.md`](docs/ka/installation.md) →
[`docs/ka/usage.md`](docs/ka/usage.md) · [`docs/en/installation.md`](docs/en/installation.md) →
[`docs/en/usage.md`](docs/en/usage.md).

---

## Status

Alpha / experimental. Runs on QGIS 3.40+ (Qt5) and QGIS 4 (Qt6) from one build. Windows + Linux supported; macOS detection
(official `QGIS*.app` bundle, Homebrew/conda) is implemented but untested on real hardware. See
[`docs/en/architecture.md`](docs/en/architecture.md) for design notes,
including what's deliberately *not* automated (PyCharm's version-pinned
`pydevd-pycharm`, and stopping a `debugpy` listener mid-session).

## License

MIT — see [LICENSE](LICENSE).
