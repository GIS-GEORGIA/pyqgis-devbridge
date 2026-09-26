DevBridge desktop tool / DevBridge დესკტოპ ხელსაწყო
====================================================

EN
  A standalone window (English / Georgian) with the same operations as the
  DevBridge panel inside QGIS: prepare one of your plugins for debugging,
  open it in the file manager or VS Code, install/enable the DevBridge plugin
  in your QGIS profile, and edit the settings (language, ports) that the QGIS
  plugin shares. It does not need QGIS to be running.

  Start it:
    Windows        double-click  devbridge_gui.pyw
    Linux / macOS  python3 devbridge_gui.pyw
    any OS         python -m devbridge gui      (run from this folder)
  Needs Python 3.9+ with Tk (on python.org installers: keep "tcl/tk and IDLE"
  ticked; on Debian/Ubuntu: sudo apt install python3-tk).

  The command-line version:  python -m devbridge --help

KA
  დამოუკიდებელი ფანჯარა (ინგლისური / ქართული) იგივე ოპერაციებით, რაც
  QGIS-ში DevBridge-ის პანელს აქვს: თქვენი დანამატის დებაგისთვის მომზადება,
  გახსნა ფაილების მენეჯერში ან VS Code-ში, DevBridge-ის დაყენება/ჩართვა
  თქვენს QGIS პროფილში და პარამეტრების (ენა, პორტები) შეცვლა — ისინი QGIS
  დანამატთან საერთოა. QGIS-ის გაშვება არ სჭირდება.

  გაშვება:
    Windows        ორჯერ დააწკაპუნეთ  devbridge_gui.pyw-ზე
    Linux / macOS  python3 devbridge_gui.pyw
    ნებისმიერი OS  python -m devbridge gui      (გაუშვით ამ საქაღალდიდან)
  სჭირდება Python 3.9+ Tk-ით (python.org-ის ინსტალატორში დატოვეთ მონიშნული
  "tcl/tk and IDLE"; Debian/Ubuntu: sudo apt install python3-tk).

  ბრძანების სტრიქონის ვერსია:  python -m devbridge --help

https://github.com/GIS-GEORGIA/pyqgis-devbridge
