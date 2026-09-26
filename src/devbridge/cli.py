"""Command-line entry point.

    devbridge setup           # detect QGIS, take a plugin from your QGIS
                               # profile folder, build venv, install debugpy,
                               # write VS Code + PyCharm configs
    devbridge setup --plugin MyPlugin      # pick the plugin by name
    devbridge setup --project-dir .        # or work on any folder instead
    devbridge plugins         # list plugins found in your QGIS profile
    devbridge detect          # just print what was found
    devbridge --lang ka setup
    devbridge gui             # launch the Tk GUI instead
"""
from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

from . import env_builder, debugpy_installer, profiles, vscode_config, pycharm_config
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


def _ask_plugin(plugins: list[profiles.ProfilePlugin]) -> profiles.ProfilePlugin | None:
    """Numbered picker; only usable on an interactive terminal."""
    if not sys.stdin.isatty():
        return None
    print(t("choose_plugin"))
    for i, plugin in enumerate(plugins, 1):
        print(f"  {i}. {plugin.label}")
    while True:
        answer = input(t("choose_prompt")).strip()
        if not answer:
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(plugins):
            return plugins[int(answer) - 1]


def _resolve_project_dir(args: argparse.Namespace) -> Path | None:
    """--project-dir wins; otherwise take the plugin straight from the
    QGIS profile folder."""
    if args.project_dir:
        return Path(args.project_dir).resolve()
    print(t("scanning_profiles"))
    try:
        plugin = profiles.choose_plugin(args.plugin, args.profile, ask=_ask_plugin)
    except profiles.PluginSelectionError as err:
        print(t(err.key, **err.params))
        return None
    print(t("using_plugin", label=plugin.label, path=plugin.path))
    return plugin.path.resolve()


def cmd_plugins(args: argparse.Namespace) -> int:
    found = profiles.find_plugins(args.profile)
    if not found:
        print(t("no_profile_plugins"))
        return 1
    print(t("plugins_list_header"))
    for plugin in found:
        print(f"  {plugin.label}  {plugin.path}")
    return 0


def cmd_setup(args: argparse.Namespace) -> int:
    project_dir = _resolve_project_dir(args)
    if project_dir is None:
        return 1

    print(t("detecting_qgis"))
    qgis = _detector.find_qgis()
    if not qgis:
        print(t("qgis_not_found"))
        return 1
    print(t("qgis_found", path=qgis.root))

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
    p_setup.add_argument("--project-dir", default=None,
                          help="Target folder. Default: a plugin taken from your QGIS profile")
    p_setup.add_argument("--plugin", default=None,
                          help="Plugin name in your QGIS profile (auto-picked if there is only one)")
    p_setup.add_argument("--profile", default=None,
                          help="QGIS profile name (default: any, 'default' first)")
    p_setup.add_argument("--venv-name", default=".venv", help="Venv folder name")
    p_setup.add_argument("--port", type=int, default=vscode_config.DEFAULT_PORT,
                          help="debugpy attach port")
    p_setup.set_defaults(func=cmd_setup)

    p_plugins = sub.add_parser("plugins", help="List plugins found in your QGIS profile")
    p_plugins.add_argument("--profile", default=None, help="QGIS profile name")
    p_plugins.set_defaults(func=cmd_plugins)

    p_gui = sub.add_parser("gui", help="Launch the graphical interface")
    p_gui.set_defaults(func=lambda a: _launch_gui())

    return parser


def _launch_gui() -> int:
    from .gui import launch
    launch()
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    # Georgian text must not crash legacy Windows consoles (cp1252 etc.)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
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
