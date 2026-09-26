# ინსტალაცია

## 1. დამოუკიდებელი setup ინსტრუმენტი (CLI + GUI)

საჭიროა Python 3.9+ თქვენს PATH-ში (ნებისმიერი Python — არა აუცილებლად
QGIS-ის ჩაშენებული — მას მხოლოდ venv-ის შექმნა და pip-ის გაშვება
სჭირდება).

```bash
git clone https://github.com/GIS-GEORGIA/pyqgis-devbridge.git
cd pyqgis-devbridge
pip install -e .
```

გაუშვით — plugin-ს ის თავად აიღებს თქვენი QGIS პროფილის `python/plugins`
საქაღალდიდან (ცვლილებები QGIS-შიც მაშინვე ჩანს):

```bash
devbridge plugins                      # რა plugin-ებია პროფილში
devbridge setup                        # ერთი plugin-ის შემთხვევაში ავტომატურად,
                                       # რამდენიმეს შემთხვევაში ნომრით ირჩევთ
devbridge setup --plugin MyPlugin      # ან სახელით
devbridge setup --project-dir /path/to/folder   # ნებისმიერი სხვა საქაღალდე
```

ან გახსენით GUI:

```bash
devbridge gui
```

ეს ავტომატურად:
1. მოძებნის QGIS ინსტალაციას (Windows: OSGeo4W / სტანდარტული
   ინსტალატორის სტრუქტურა; Linux: სისტემური `python3`, სადაც `import
   qgis` მუშაობს, ან ცნობილი სტატიკური გზები; macOS: `/Applications/QGIS*.app`
   ან ნებისმიერი `python3`, რომელსაც უკვე შეუძლია `import qgis`).
2. შექმნის `--system-site-packages` ვირტუალურ გარემოს, დაკავშირებულს
   QGIS-ის Python მოდულებთან (`qgis.pth`), საჭიროების შემთხვევაში
   ავტომატურად დაამატებს Windows-ის DLL-directory შუალედურ ფაილს
   (`sitecustomize.py`).
3. დააინსტალირებს `debugpy`-ს როგორც QGIS-ის ინტერპრეტატორში, ისე venv-ში.
4. ჩაწერს `.vscode/settings.json`-სა და `.vscode/launch.json`-ს
   ("Attach to running QGIS" კონფიგურაციით).
5. ჩაწერს `.pycharm-debug/README.{en,ka}.md`-ს PyCharm-ის ხელით
   შესასრულებელი ნაბიჯებით (იხილეთ იმ ფაილში ახსნა, რატომ არ არის ეს
   ნაწილი სრულად ავტომატიზირებული).

## 2. QGIS Plugin (DevBridge)

დააკოპირეთ (ან დამუშავების დროს symlink გააკეთეთ) `qgis_plugin/`
თქვენს QGIS პროფილის plugins საქაღალდეში, სახელით `DevBridge`:

- Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/DevBridge`
- macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/DevBridge`
- Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\DevBridge`

შემდეგ ჩართეთ **Plugins → Manage and Install Plugins → Installed**-დან.

QGIS Plugin Repository-სთვის შესაფერისი `.zip` შეიძლება აიწყოს:

```bash
cd qgis_plugin
zip -r ../DevBridge.zip . -x "__pycache__/*"
```
