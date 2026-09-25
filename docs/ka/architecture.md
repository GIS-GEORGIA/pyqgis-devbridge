# არქიტექტურა

```
pyqgis-devbridge/
├── src/devbridge/         # დამოუკიდებელი CLI + GUI (pip-installable)
│   ├── detectors/         # Windows / Linux QGIS ინსტალაციის ამოცნობა
│   ├── env_builder.py     # venv + qgis.pth + sitecustomize.py
│   ├── debugpy_installer.py
│   ├── vscode_config.py   # .vscode/settings.json + launch.json
│   ├── pycharm_config.py  # დოკუმენტირებული ხელით ნაბიჯები
│   ├── cli.py / gui.py
│   └── i18n/              # en.json / ka.json
└── qgis_plugin/           # DevBridge — ხიდის QGIS-შიდა ნახევარი
    ├── debug_bridge.py    # სუფთა debugpy wrapper, QGIS იმპორტების გარეშე
    ├── plugin.py           # QGIS მენიუ / message-bar ინტეგრაცია
    ├── ui/settings_dialog.py
    └── i18n/               # en.json / ka.json
```

## საპროექტო გადაწყვეტილებები, რაც სახელმძღვანელოს თავისთვის გამოგადგებათ

- **ორი დამოუკიდებელი პაკეტი, ერთი საერთო იდეა.** CLI/GUI და QGIS
  plugin ერთმანეთს არ იმპორტავენ. Plugin-მა უნდა დარჩეს დამოუკიდებელი
  საქაღალდე, რომლის QGIS-ის პროფილში კოპირებაც შესაძლებელია; CLI/GUI კი
  ჩვეულებრივი pip პაკეტია. ისინი თანხმდებიან მხოლოდ *პროტოკოლზე*
  (host/port + `.vscode/launch.json`-ის ფორმატი), არა საერთო კოდზე.
- **`debug_bridge.py`-ს არცერთი QGIS იმპორტი არ აქვს.** ყველა `qgis.*` /
  `qgis.PyQt` გამოყენება `plugin.py`-სა და `ui/`-შია. ეს ნიშნავს, რომ
  ხიდის ლოგიკა ჩვეულებრივი `pytest`-ით ტესტირებადია და შესაძლებელია
  QGIS Python კონსოლიდანაც პირდაპირ, მენიუს გარეშე გამოყენება.
- **i18n არის ბრტყელი key→string JSON, არა gettext/.po.** ორ-ენოვანი,
  მხოლოდ UI-სტრიქონების პროექტისთვის ეს გამორიცხავს კომპილირებული
  კატალოგის build-ეტაპს; თუ პროექტი EN/KA-ზე მეტს დაფარავს, სჯობს
  გადავიდეს Qt Linguist `.ts`/`.qm`-ზე (თავად QGIS-ის სტანდარტი) ამ
  მარტივი loader-ის ნაცვლად.
- **PyCharm მხარდაჭერა ავტომატიზირებულია იქ, სადაც შესაძლებელია, და
  გულწრფელია იქ, სადაც ვერ ხერხდება.** `qgis_plugin/pycharm_bridge.py`
  კითხულობს დაინსტალირებული PyCharm-ის საკუთარ `build.txt`-ს, პოულობს
  შესაბამის `pydevd-pycharm` ვერსიას PyPI-დან (ჯერ ზუსტი build ნომერი,
  შემდეგ უახლოესი იმავე major ვერსიის release-ი fallback-ად),
  აინსტალირებს QGIS-ის ინტერპრეტატორში და უკავშირდება — ერთი მენიუს
  action-იდან. ეს აშორებს ვერსიის ხელით ძებნის ნაბიჯს, რომელიც ადრე
  სრულად ხელით სრულდებოდა. რაც *არ* არის ავტომატიზირებული, განზრახ:
  portable/unzipped PyCharm build-ის აღმოჩენა არასტანდარტულ
  ადგილას, და offline მუშაობა (PyPI-ის ვერსიის ძებნას ქსელი სჭირდება).
  ორივე შემთხვევაში ეშვება fallback ხელით `.pycharm-debug/README.*.md`
  ნაბიჯებზე, ჩუმად ჩავარდნის ნაცვლად — იხილეთ `docs/*/usage.md`
  fallback გზისთვის და იმისთვის, თუ რატომ აქვს მნიშვნელობა კავშირის
  მიმართულებას (QGIS *გარეთ* უკავშირდება PyCharm-ს, საპირისპიროდ
  debugpy/VS Code ხიდისა).
