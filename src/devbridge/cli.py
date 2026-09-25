"""Command-line entry point.

    devbridge setup           # detect QGIS, build venv, install debugpy,
                               # write VS Code + PyCharm configs
    devbridge detect          # just print what was found
    devbridge --lang ka setup
    devbridge gui             # launch the Tk GUI instead
"""
from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from . import env_builder, debugpy_installer, vscode_config, pycharm_config
from .i18n_util import detect_system_lang, set_lang, t

from .detectors import get_detector

_detector = get_detector()


def _venv_python(venv_path: Path) -> Path:
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def cmd_detect(args: argparse.Namespace) -> int:
    print(t("detecting_qgis"))
    qgis = _detector.find_qgis()
    if not qgis:
        print(t("qgis_not_found"))
        return 1
    print(t("qgis_found", path=qgis.root))
    for k, v in qgis.as_dict().items():
        print(f"  {k}: {v}")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    print(t("detecting_qgis"))
    qgis = _detector.find_qgis()
    if not qgis:
        print(t("qgis_not_found"))
        return 1
    print(t("qgis_found", path=qgis.root))

    project_dir = Path(args.project_dir).resolve()
    venv_path = project_dir / args.venv_name

    env_builder.build_venv(qgis, venv_path)
    debugpy_installer.install_debugpy(qgis, venv_python=_venv_python(venv_path))
    vscode_config.write_vscode_config(project_dir, venv_path, port=args.port)
    pycharm_config.write_pycharm_notes(project_dir)

    print(t("done"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devbridge", description=t("welcome"))
    parser.add_argument("--lang", choices=["en", "ka"], default=None,
                         help="Interface language / ინტერფეისის ენა")

    sub = parser.add_subparsers(dest="command", required=True)

    p_detect = sub.add_parser("detect", help="Detect QGIS installation only")
    p_detect.set_defaults(func=cmd_detect)

    p_setup = sub.add_parser("setup", help="Full environment + IDE setup")
    p_setup.add_argument("--project-dir", default=".", help="Target project folder")
    p_setup.add_argument("--venv-name", default=".venv", help="Venv folder name")
    p_setup.add_argument("--port", type=int, default=vscode_config.DEFAULT_PORT,
                          help="debugpy attach port")
    p_setup.set_defaults(func=cmd_setup)

    p_gui = sub.add_parser("gui", help="Launch the graphical interface")
    p_gui.set_defaults(func=lambda a: _launch_gui())

    return parser


def _launch_gui() -> int:
    from .gui import launch
    launch()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    set_lang(detect_system_lang())

    # allow --lang to be parsed before we know the subcommand, for
    # localized --help text too
    if "--lang" in argv:
        idx = argv.index("--lang")
        if idx + 1 < len(argv):
            set_lang(argv[idx + 1])

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.lang:
        set_lang(args.lang)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
