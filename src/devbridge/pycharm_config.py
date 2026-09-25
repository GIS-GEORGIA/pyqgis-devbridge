"""PyCharm's remote-debug protocol (pydevd) is not wire-compatible with
debugpy, so we cannot share one bridge implementation across both IDEs.
Instead we write a small run-config template plus a README note that
tells the user exactly what to install on the QGIS side
(`pip install pydevd-pycharm==<version matching PyCharm build>`).

This keeps scope honest: PyCharm support is "documented + scaffolded",
not "one-click" like the VS Code path, and that distinction should be
called out explicitly wherever this module's output is used (docs,
book chapter, README).
"""
from __future__ import annotations

from pathlib import Path

from .i18n_util import t

_NOTE_EN = """\
# PyCharm remote debugging — manual step required

PyCharm (JetBrains) uses its own remote-debug library (`pydevd-pycharm`),
which is versioned to match your exact PyCharm build and is NOT
protocol-compatible with debugpy (used for VS Code).

Steps:
1. In PyCharm: Run -> Edit Configurations -> + -> Python Debug Server.
   Note the host/port it shows you (default 127.0.0.1:12345).
2. Find the matching package version:
   Help -> About -> note the build number, then:
   `<qgis-python> -m pip install pydevd-pycharm~=<PyCharm version>`
3. In the QGIS Python console (or via the DevBridge plugin's
   "start bridge" action with backend=pycharm), run:
   ```python
   import pydevd_pycharm
   pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)
   ```
4. Execution will pause at that line and control passes to PyCharm.

This project intentionally does not automate step 2-3 fully, because the
required package version is tied to your installed PyCharm build and
would otherwise silently break on IDE updates.
"""

_NOTE_KA = """\
# PyCharm დისტანციური დებაგინგი — საჭიროა ხელით ნაბიჯი

PyCharm იყენებს საკუთარ ბიბლიოთეკას (`pydevd-pycharm`), რომლის ვერსია
ზუსტად უნდა ემთხვეოდეს თქვენს PyCharm-ის build-ს და არ არის თავსებადი
debugpy-სთან (რომელსაც VS Code იყენებს).

ნაბიჯები:
1. PyCharm-ში: Run -> Edit Configurations -> + -> Python Debug Server.
   ჩაინიშნეთ host/port (ნაგულისხმევად 127.0.0.1:12345).
2. მოძებნეთ შესაბამისი ვერსია:
   Help -> About -> ჩაინიშნეთ build ნომერი, შემდეგ:
   `<qgis-python> -m pip install pydevd-pycharm~=<PyCharm-ის ვერსია>`
3. QGIS Python კონსოლში (ან DevBridge plugin-ის "bridge-ის გაშვება"
   action-ით, backend=pycharm), გაუშვით:
   ```python
   import pydevd_pycharm
   pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)
   ```
4. შესრულება გაჩერდება ამ ხაზზე და კონტროლი გადადის PyCharm-ზე.

ეს პროექტი შეგნებულად არ ავტომატიზირებს მე-2 და მე-3 ნაბიჯს ბოლომდე,
რადგან საჭირო პაკეტის ვერსია მიბმულია თქვენს PyCharm build-ზე და
წინააღმდეგ შემთხვევაში IDE-ის განახლებისას ჩუმად გატყდებოდა.
"""


def write_pycharm_notes(project_dir: Path, verbose_print=print) -> None:
    verbose_print(t("writing_pycharm"))
    docs_dir = project_dir / ".pycharm-debug"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "README.en.md").write_text(_NOTE_EN, encoding="utf-8")
    (docs_dir / "README.ka.md").write_text(_NOTE_KA, encoding="utf-8")
