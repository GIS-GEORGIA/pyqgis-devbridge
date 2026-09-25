"""Minimal Tkinter GUI (stdlib only, no extra dependency) wrapping the
same setup pipeline as the CLI. Kept intentionally small: this is a
convenience front-end, the CLI/library is the source of truth."""
from __future__ import annotations

import platform
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk

from . import debugpy_installer, env_builder, pycharm_config, vscode_config
from .i18n_util import detect_system_lang, get_lang, set_lang, t

if platform.system() == "Windows":
    from .detectors import windows as _detector
else:
    from .detectors import linux as _detector


class DevBridgeApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=12)
        self.master = master
        self.project_dir = tk.StringVar(value=str(Path.cwd()))
        self.port = tk.StringVar(value=str(vscode_config.DEFAULT_PORT))
        self.lang = tk.StringVar(value=get_lang())
        self._build_widgets()
        self.pack(fill="both", expand=True)

    def _build_widgets(self) -> None:
        self.master.title(t("welcome"))

        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="EN/KA:").pack(side="left")
        lang_box = ttk.Combobox(top, textvariable=self.lang, values=["en", "ka"],
                                 width=4, state="readonly")
        lang_box.pack(side="left", padx=4)
        lang_box.bind("<<ComboboxSelected>>", self._on_lang_change)

        row = ttk.Frame(self)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Project dir:").pack(side="left")
        ttk.Entry(row, textvariable=self.project_dir, width=40).pack(side="left", padx=4)
        ttk.Button(row, text="...", width=3, command=self._browse).pack(side="left")

        row2 = ttk.Frame(self)
        row2.pack(fill="x", pady=4)
        ttk.Label(row2, text="debugpy port:").pack(side="left")
        ttk.Entry(row2, textvariable=self.port, width=8).pack(side="left", padx=4)

        self.run_btn = ttk.Button(self, text=t("welcome"), command=self._run_setup)
        self.run_btn.pack(fill="x", pady=8)

        self.log = scrolledtext.ScrolledText(self, width=70, height=18, state="disabled")
        self.log.pack(fill="both", expand=True)

    def _on_lang_change(self, _evt=None) -> None:
        set_lang(self.lang.get())
        self.master.title(t("welcome"))
        self.run_btn.config(text=t("welcome"))

    def _browse(self) -> None:
        chosen = filedialog.askdirectory()
        if chosen:
            self.project_dir.set(chosen)

    def _log(self, msg: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _run_setup(self) -> None:
        self.run_btn.config(state="disabled")
        threading.Thread(target=self._run_setup_worker, daemon=True).start()

    def _run_setup_worker(self) -> None:
        try:
            self._log(t("detecting_qgis"))
            qgis = _detector.find_qgis()
            if not qgis:
                self._log(t("qgis_not_found"))
                return
            self._log(t("qgis_found", path=qgis.root))

            project_dir = Path(self.project_dir.get()).resolve()
            venv_path = project_dir / ".venv"
            venv_python = (
                venv_path / "Scripts" / "python.exe"
                if platform.system() == "Windows"
                else venv_path / "bin" / "python"
            )

            env_builder.build_venv(qgis, venv_path, verbose_print=self._log)
            debugpy_installer.install_debugpy(qgis, venv_python=venv_python,
                                               verbose_print=self._log)
            vscode_config.write_vscode_config(
                project_dir, venv_path, port=int(self.port.get() or 5678),
                verbose_print=self._log,
            )
            pycharm_config.write_pycharm_notes(project_dir, verbose_print=self._log)
            self._log(t("done"))
        except Exception as exc:  # surfaced to the log pane, not a stack trace dialog
            self._log(f"ERROR: {exc}")
        finally:
            self.run_btn.config(state="normal")


def launch() -> None:
    set_lang(detect_system_lang())
    root = tk.Tk()
    DevBridgeApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
