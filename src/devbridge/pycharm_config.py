"""PyCharm's remote-debug protocol (pydevd) is not wire-compatible with
debugpy, so we cannot share one bridge implementation across both IDEs.

Two things get written for the PyCharm side of `devbridge setup`:
- a real, loadable "Python Debug Server" run configuration
  (`.idea/runConfigurations/`, see `pycharm_run_config.py`) - PyCharm's
  own "+ > Python Debug Server" step, done for you;
- a README (`.pycharm-debug/`) as the fallback for when the automatic
  PyCharm-build detection on the QGIS side
  (`qgis_plugin/pycharm_bridge.py`) can't find a match, with the fully
  manual steps.
"""
from __future__ import annotations

from pathlib import Path

from . import pycharm_run_config
from .i18n_util import t
from .paths import qgis_user_plugins_dir

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


def write_pycharm_run_config(project_dir: Path, host: str = "localhost", port: int = 12345,
                             plugin_name: str | None = None, profile: str = "default",
                             verbose_print=print) -> Path:
    """Writes the "Python Debug Server" run configuration PyCharm would
    otherwise need creating by hand (Run > Edit Configurations > + >
    Python Debug Server) - see pycharm_run_config.py for what this is
    checked against. `plugin_name` gets the same path mapping VS Code's
    config gets, so breakpoints in the workspace match frames PyCharm
    reports from the QGIS profile path."""
    remote_root = str(qgis_user_plugins_dir(profile) / plugin_name) if plugin_name else None
    path = pycharm_run_config.write_run_config(project_dir, host=host, port=port, remote_root=remote_root)
    verbose_print(t("wrote_file", path=path))
    return path
