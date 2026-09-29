"""Command-line entry point.

    devbridge setup           # detect QGIS, take a plugin from your QGIS
                               # profile folder, build venv, install debugpy,
                               # write VS Code + PyCharm configs
    devbridge setup --plugin MyPlugin      # pick the plugin by name
    devbridge setup --project-dir .        # or work on any folder instead
    devbridge plugins         # list plugins found in your QGIS profile
    devbridge new my_plugin   # start a NEW plugin (starter files) and prepare it for debugging
    devbridge new-script my_script  # start a standalone script (no QGIS needed) and prepare it for debugging
    devbridge launch          # start QGIS with the debug bridge already listening (for VS Code's F5)
    devbridge install-plugin  # put the DevBridge QGIS plugin into your profile and enable it
    devbridge link-plugin PATH  # link any other plugin folder into your QGIS profile and enable it
    devbridge uninstall       # remove DevBridge from your profile(s) (--project-dir to also clean a project)
    devbridge detect          # just print what was found
    devbridge doctor          # check the whole chain (QGIS, debugpy, plugin, port, .vscode/)
    devbridge doctor --fix    # ...and try to fix what's safe to fix automatically
    devbridge --lang ka setup
    devbridge gui             # launch the Tk GUI instead
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (__version__, bridge_plugin, config, doctor, launcher, link_plugin, pipeline, profiles,
              project_config, scaffold, uninstall, vscode_config)
from .i18n_util import detect_system_lang, set_lang, t


def cmd_detect(args: argparse.Namespace) -> int:
    installs = pipeline.find_all_qgis()
    if not installs:
        print(t("qgis_not_found"))
        return 1
    if len(installs) > 1:
        print(t("qgis_multiple_found", count=len(installs)))
    for i, qgis in enumerate(installs):
        prefix = f"{i + 1}. " if len(installs) > 1 else ""
        print(f"{prefix}{qgis.root}" + (" (default)" if i == 0 and len(installs) > 1 else ""))
        for k, v in qgis.as_dict().items():
            print(f"    {k}: {v}")
    return 0


def _ask_qgis(installs: list) -> "pipeline.QgisInstallation | None":
    """Numbered picker for multiple QGIS installs; interactive terminals only."""
    if not sys.stdin.isatty():
        return None
    print(t("qgis_multiple_found", count=len(installs)))
    for i, qgis in enumerate(installs, 1):
        print(f"  {i}. {qgis.root}" + (" (default)" if i == 1 else ""))
    try:
        answer = input(t("choose_qgis_prompt")).strip()
    except EOFError:                # isatty() can lie (piped/wrapped terminals); never hang or crash
        return None
    if answer.isdigit() and 1 <= int(answer) <= len(installs):
        return installs[int(answer) - 1]
    return None


NEW_PLUGIN = object()   # picker answer: "start a new plugin instead"


def _ask_plugin(plugins: list[profiles.ProfilePlugin]):
    """Numbered picker (existing plugin, or N for a new one); interactive terminals only."""
    if not sys.stdin.isatty():
        return None
    print(t("choose_plugin"))
    for i, plugin in enumerate(plugins, 1):
        print(f"  {i}. {plugin.label}")
    print(f"  N. {t('choose_new_option')}")
    while True:
        try:
            answer = input(t("choose_prompt")).strip()
        except EOFError:            # isatty() can lie (piped/wrapped terminals); never hang or crash
            return None
        if not answer:
            return None
        if answer.lower() == "n":
            return NEW_PLUGIN
        if answer.isdigit() and 1 <= int(answer) <= len(plugins):
            return plugins[int(answer) - 1]


def _new_plugin(name: str | None, parent: str | None, title: str | None = None) -> Path | None:
    """Create the starter files; prompts for the name on a terminal. None = nothing created."""
    if not name:
        if not sys.stdin.isatty():
            print(t("new_name_needed"))
            return None
        try:
            name = input(t("new_name_prompt")).strip()
        except EOFError:            # isatty() can lie (piped/wrapped terminals); never hang or crash
            return None
        if not name:
            return None
    parent_dir = Path(parent) if parent else profiles.default_plugins_dir()
    if parent_dir is None:
        print(t("new_no_profile"))
        return None
    try:
        parent_dir.mkdir(parents=True, exist_ok=True)
        path = scaffold.create_plugin(parent_dir, name, title=title)
    except scaffold.ScaffoldError as err:
        print(t(f"new_{err}", name=name, path=parent_dir))
        return None
    print(t("new_created", path=path))
    return path.resolve()


def _new_script(name: str | None, directory: str | None, title: str | None = None) -> Path | None:
    """Create the starter script, prompting for the name on a terminal. None = nothing created."""
    if not name:
        if not sys.stdin.isatty():
            print(t("new_script_name_needed"))
            return None
        try:
            name = input(t("new_script_name_prompt")).strip()
        except EOFError:            # isatty() can lie (piped/wrapped terminals); never hang or crash
            return None
        if not name:
            return None
    parent_dir = Path(directory) if directory else Path(".")
    try:
        path = scaffold.create_script(parent_dir, name, title=title)
    except scaffold.ScaffoldError as err:
        print(t(f"new_{err}", name=name, path=parent_dir))
        return None
    print(t("new_script_created", path=path))
    return path.resolve()


def _pycharm_kwargs() -> dict:
    """The shared settings' PyCharm host/port, ready to splat into
    pipeline.run_setup(**_pycharm_kwargs())."""
    cfg = config.load()
    return {"pycharm_host": cfg["pycharm_host"], "pycharm_port": cfg["pycharm_port"]}


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
        if err.key == "no_profile_plugins" and sys.stdin.isatty():
            return _new_plugin(None, None)          # nothing to pick: offer a new plugin
        return None
    if plugin is NEW_PLUGIN:
        return _new_plugin(None, None)
    print(t("using_plugin", label=plugin.label, path=plugin.path))
    return plugin.path.resolve()


def cmd_new(args: argparse.Namespace) -> int:
    path = _new_plugin(args.name, args.dir, args.title)
    if path is None:
        return 1
    if args.no_setup:
        return 0
    try:
        qgis = pipeline.find_qgis(qgis_root=args.qgis_root, ask=_ask_qgis)
        pipeline.run_setup(path, port=args.port, qgis=qgis, **_pycharm_kwargs())
    except pipeline.SetupError as err:
        print(err)
        return 1
    print(t("new_next_steps"))
    return 0


def cmd_new_script(args: argparse.Namespace) -> int:
    path = _new_script(args.name, args.dir, args.title)
    if path is None:
        return 1
    if args.no_setup:
        return 0
    try:
        qgis = pipeline.find_qgis(qgis_root=args.qgis_root, ask=_ask_qgis)
        pipeline.run_setup(path.parent, port=args.port, qgis=qgis, **_pycharm_kwargs())
    except pipeline.SetupError as err:
        print(err)
        return 1
    print(t("new_script_next_steps"))
    return 0


def cmd_plugins(args: argparse.Namespace) -> int:
    found = profiles.find_plugins(args.profile)
    if not found:
        print(t("no_profile_plugins"))
        return 1
    print(t("plugins_list_header"))
    for plugin in found:
        print(f"  {plugin.label}  {plugin.path}")
    return 0


def cmd_install_plugin(args: argparse.Namespace) -> int:
    return bridge_plugin.install_into_profiles(
        profile=args.profile, copy=args.copy, force=args.force)


def cmd_link_plugin(args: argparse.Namespace) -> int:
    return link_plugin.link_into_profiles(
        Path(args.path), name=args.name, profile=args.profile, copy=args.copy, force=args.force)


def cmd_uninstall(args: argparse.Namespace) -> int:
    status = 0
    if not (args.project_dir and args.keep_plugin):
        status = uninstall.uninstall_plugin(profile=args.profile, name=args.name) or status
    if args.project_dir:
        status = uninstall.uninstall_project(Path(args.project_dir)) or status
    return status


def cmd_doctor(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve() if args.project_dir else None
    qgis = None
    if args.qgis_root:
        try:
            qgis = pipeline.find_qgis(qgis_root=args.qgis_root, log=lambda _m: None)
        except pipeline.SetupError as err:
            print(err)
            return 1
    checks = doctor.run_checks(project_dir=project_dir, port=args.port, qgis=qgis, log=print)
    ok = doctor.print_report(checks, log=print)
    if ok or not args.fix:
        return 0 if ok else 1

    print(t("doctor_fix_header"))
    doctor.apply_fixes(checks, project_dir=project_dir, port=args.port, qgis=qgis, log=print)
    print(t("doctor_fix_rechecking"))
    checks = doctor.run_checks(project_dir=project_dir, port=args.port, qgis=qgis, log=print)
    return 0 if doctor.print_report(checks, log=print) else 1


def cmd_setup(args: argparse.Namespace) -> int:
    project_dir = _resolve_project_dir(args)
    if project_dir is None:
        return 1

    try:
        qgis = pipeline.find_qgis(qgis_root=args.qgis_root, ask=_ask_qgis)
        pipeline.run_setup(project_dir, port=args.port, venv_name=args.venv_name,
                           host=args.host, plugin_name=args.plugin_name, qgis=qgis, **_pycharm_kwargs())
    except pipeline.SetupError as err:
        print(err)
        return 1
    return 0


def cmd_launch(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve()
    cfg = project_config.read_project_config(project_dir)
    host = args.host or cfg["host"]
    port = args.port or cfg["port"]

    try:
        qgis = pipeline.find_qgis(qgis_root=args.qgis_root, ask=_ask_qgis)
    except pipeline.SetupError as err:
        print(err)
        return 1

    return launcher.launch_qgis(
        qgis, host=host, port=port, wait_for_client=args.wait_for_client,
        wait_ready=args.wait_ready, timeout=args.timeout,
        project_file=args.qgis_project, verbose_print=print,
        reuse_existing=not args.force_new)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="devbridge", description=t("welcome"))
    parser.add_argument("--version", action="version", version=f"devbridge {__version__}")
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
    p_setup.add_argument("--port", type=int, default=config.load()["port"],
                          help="debugpy attach port (default: from the shared DevBridge settings)")
    p_setup.add_argument("--host", default="localhost", help="debugpy host")
    p_setup.add_argument("--qgis-root", default=None,
                          help="Use this specific QGIS install (see 'devbridge detect'); "
                               "asked interactively when several are found and this is omitted")
    p_setup.add_argument("--plugin-name", default=None,
                          help="Folder name QGIS loads the plugin from, for VS Code path mappings "
                               "(auto-detected when the target is inside a QGIS profile's plugins folder)")
    p_setup.set_defaults(func=cmd_setup)

    p_launch = sub.add_parser("launch", help="Start QGIS with the debug bridge already listening")
    p_launch.add_argument("--project-dir", default=".", help="Folder containing .devbridge.json")
    p_launch.add_argument("--host", default=None, help="Override host from .devbridge.json")
    p_launch.add_argument("--port", type=int, default=None, help="Override port from .devbridge.json")
    p_launch.add_argument("--wait-ready", action="store_true",
                          help="Wait until the bridge reports ready (or fails) before exiting")
    p_launch.add_argument("--wait-for-client", action="store_true",
                          help="Also block QGIS's startup until an IDE attaches")
    p_launch.add_argument("--timeout", type=float, default=60.0, help="Seconds to wait with --wait-ready")
    p_launch.add_argument("--qgis-project", default=None, help="Optional .qgz/.qgs to open")
    p_launch.add_argument("--qgis-root", default=None,
                          help="Use this specific QGIS install (see 'devbridge detect')")
    p_launch.add_argument("--force-new", action="store_true",
                          help="Always start a fresh QGIS, even if the port is already in use (default: "
                               "assume that's an already-running session with the bridge up and reuse it, "
                               "no second QGIS window)")
    p_launch.set_defaults(func=cmd_launch)

    p_plugins = sub.add_parser("plugins", help="List plugins found in your QGIS profile")
    p_plugins.add_argument("--profile", default=None, help="QGIS profile name")
    p_plugins.set_defaults(func=cmd_plugins)

    p_new = sub.add_parser("new", help="Start a NEW plugin (starter files) and prepare it for debugging")
    p_new.add_argument("name", nargs="?", help="Plugin folder name, lowercase, e.g. my_plugin (asked if omitted)")
    p_new.add_argument("--dir", default=None,
                        help="Parent folder (default: python/plugins of your QGIS profile, so QGIS sees it)")
    p_new.add_argument("--title", default=None, help="Display name (default: derived from the folder name)")
    p_new.add_argument("--port", type=int, default=config.load()["port"], help="debugpy attach port")
    p_new.add_argument("--no-setup", action="store_true", help="Only write the starter files")
    p_new.add_argument("--qgis-root", default=None,
                        help="Use this specific QGIS install (see 'devbridge detect')")
    p_new.set_defaults(func=cmd_new)

    p_new_script = sub.add_parser(
        "new-script", help="Start a standalone PyQGIS script (no QGIS needed) and prepare it for debugging")
    p_new_script.add_argument("name", nargs="?",
                              help="Script file name, e.g. my_script (asked if omitted; .py added automatically)")
    p_new_script.add_argument("--dir", default=None, help="Folder to create it in (default: current directory)")
    p_new_script.add_argument("--title", default=None,
                              help="Display name in the file's docstring (default: derived from the file name)")
    p_new_script.add_argument("--port", type=int, default=config.load()["port"], help="debugpy attach port")
    p_new_script.add_argument("--no-setup", action="store_true", help="Only write the script, skip venv/IDE setup")
    p_new_script.add_argument("--qgis-root", default=None,
                              help="Use this specific QGIS install (see 'devbridge detect')")
    p_new_script.set_defaults(func=cmd_new_script)

    p_bridge = sub.add_parser("install-plugin",
                              help="Install the DevBridge QGIS plugin into your profile and enable it")
    p_bridge.add_argument("--profile", default=None, help="QGIS profile name (default: 'default')")
    p_bridge.add_argument("--copy", action="store_true",
                           help="Copy instead of linking (edits in the repo won't show up in QGIS)")
    p_bridge.add_argument("--force", action="store_true",
                           help="Replace an existing DevBridge folder in the profile")
    p_bridge.set_defaults(func=cmd_install_plugin)

    p_link = sub.add_parser("link-plugin",
                            help="Link (or copy) any plugin folder into your QGIS profile and enable it")
    p_link.add_argument("path", help="Plugin folder to link in, e.g. a git checkout outside any QGIS profile")
    p_link.add_argument("--name", default=None,
                        help="Folder name QGIS sees it under (default: the source folder's own name)")
    p_link.add_argument("--profile", default=None, help="QGIS profile name (default: 'default')")
    p_link.add_argument("--copy", action="store_true",
                        help="Copy instead of linking (edits at the source won't show up in QGIS)")
    p_link.add_argument("--force", action="store_true",
                        help="Replace an existing folder of that name in the profile")
    p_link.set_defaults(func=cmd_link_plugin)

    p_uninstall = sub.add_parser(
        "uninstall", help="Remove a plugin from your QGIS profile(s), and/or clean up one project's debug setup")
    p_uninstall.add_argument("--profile", default=None,
                             help="QGIS profile name (default: every profile that has it)")
    p_uninstall.add_argument("--name", default=bridge_plugin.PLUGIN_NAME,
                             help="Plugin folder name to remove (default: DevBridge itself)")
    p_uninstall.add_argument("--project-dir", default=None,
                             help="Also remove this project's .venv, .devbridge.json, .pycharm-debug/ "
                                  "and DevBridge's own .vscode/ entries")
    p_uninstall.add_argument("--keep-plugin", action="store_true",
                             help="With --project-dir: only clean the project, don't touch the QGIS profile")
    p_uninstall.set_defaults(func=cmd_uninstall)

    p_doctor = sub.add_parser("doctor", help="Check the whole chain: QGIS, debugpy, the plugin, the port, .vscode/")
    p_doctor.add_argument("--project-dir", default=None,
                          help="Also check this project's .venv/.devbridge.json/.vscode (optional)")
    p_doctor.add_argument("--port", type=int, default=config.load()["port"],
                          help="Port to check (default: from the shared DevBridge settings)")
    p_doctor.add_argument("--qgis-root", default=None,
                          help="Check this specific QGIS install (see 'devbridge detect')")
    p_doctor.add_argument("--fix", action="store_true",
                          help="Try to fix what's safe to fix automatically (installs debugpy/the plugin, "
                               "reruns setup for --project-dir), then re-check")
    p_doctor.set_defaults(func=cmd_doctor)

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
    set_lang(config.load()["lang"] or detect_system_lang())

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
