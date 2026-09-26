"""Run a child process while streaming its output to a log callback.

Needed because the same code runs from a terminal (CLI), a Tk window and
inside QGIS (no console at all): output has to go through `log`, and on
Windows the child must not flash a console window.
"""
from __future__ import annotations

import platform
import subprocess
from typing import Callable, Sequence


class CommandError(RuntimeError):
    """`str(exc)` holds the failed command and the tail of its output."""

    def __init__(self, cmd: Sequence[str], code: int, tail: str):
        super().__init__(f"{' '.join(map(str, cmd))} -> exit {code}\n{tail}".rstrip())
        self.cmd, self.code, self.tail = list(cmd), code, tail


def run_logged(cmd: Sequence[str], log: Callable[[str], None] = print,
               env: dict | None = None) -> str:
    """Run `cmd`, log each output line, return the full output. Raises
    CommandError on a non-zero exit."""
    flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
    proc = subprocess.Popen(
        [str(c) for c in cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
        env=env, creationflags=flags,
    )
    lines: list[str] = []
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip()
        if line:
            lines.append(line)
            log(line)
    code = proc.wait()
    if code != 0:
        raise CommandError(cmd, code, "\n".join(lines[-15:]))
    return "\n".join(lines)
