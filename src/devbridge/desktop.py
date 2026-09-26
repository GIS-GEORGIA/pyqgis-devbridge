"""Tiny OS helpers for the standalone GUI: open a folder, open it in VS Code."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


def open_folder(path: Path) -> None:
    path = Path(path)
    system = platform.system()
    if system == "Windows":
        os.startfile(str(path))  # noqa: S606 - opening a local folder in Explorer
    elif system == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def find_vscode() -> str | None:
    """Path of the `code` launcher, or None if VS Code's CLI isn't on PATH."""
    candidates = ["code"]
    if platform.system() == "Windows":
        candidates = ["code.cmd", "code"]
    for name in candidates:
        found = shutil.which(name)
        if found:
            return found
    return None


def open_in_vscode(path: Path) -> bool:
    code = find_vscode()
    if not code:
        return False
    # .cmd launchers on Windows need the shell; list2cmdline quotes the path.
    subprocess.Popen([code, str(path)], shell=platform.system() == "Windows")
    return True
