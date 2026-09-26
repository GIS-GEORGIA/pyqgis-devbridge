"""Standalone desktop GUI (stdlib Tkinter, no extra dependency).

Everything the CLI does, with buttons, in English or Georgian: pick a
plugin from your QGIS profile (or any folder), prepare it for debugging,
open it in Explorer / VS Code, install the DevBridge QGIS plugin, and edit
the settings (language, ports) that the QGIS plugin shares via
``devbridge.config``.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import bridge_plugin, config, desktop, pipeline, profiles
from .i18n_util import detect_system_lang, get_lang, set_lang, t

_POLL_MS = 100


class DevBridgeApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=12)
        self.master = master
        self._cfg = config.load()
        self._plugins: list[profiles.ProfilePlugin] = []
        self._logq: queue.Queue[str] = queue.Queue()
        self._labels: dict[str, list] = {}   # i18n key -> widgets whose text it drives

        self.lang = tk.StringVar(value=get_lang())
        self.host = tk.StringVar(value=str(self._cfg["host"]))
        self.port = tk.StringVar(value=str(self._cfg["port"]))
        self.py_host = tk.StringVar(value=str(self._cfg["pycharm_host"]))
        self.py_port = tk.StringVar(value=str(self._cfg["pycharm_port"]))
        self.project_dir = tk.StringVar(value="")

        self._build_widgets()
        self.pack(fill="both", expand=True)
        self._load_plugins()
        self._apply_texts()
        self.after(_POLL_MS, self._drain_log)

    # --- layout ----------------------------------------------------------------
    def _text(self, widget, key: str):
        """Register a widget whose label follows the current language."""
        self._labels.setdefault(key, []).append(widget)
        return widget

    def _build_widgets(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 8))
        self._text(ttk.Label(top), "gui_lang").pack(side="left")
        lang_box = ttk.Combobox(top, textvariable=self.lang, values=["en", "ka"],
                                width=4, state="readonly")
        lang_box.pack(side="left", padx=4)
        lang_box.bind("<<ComboboxSelected>>", self._on_lang_change)
        self._text(ttk.Button(top, command=self._show_guide), "gui_guide_btn").pack(side="right")

        # settings shared with the QGIS plugin
        box = self._text(ttk.LabelFrame(self, padding=8), "gui_settings")
        box.pack(fill="x", pady=4)
        for row, (key, var) in enumerate((
            ("gui_host", self.host), ("gui_port", self.port),
            ("gui_pycharm_host", self.py_host), ("gui_pycharm_port", self.py_port),
        )):
            r, c = divmod(row, 2)
            self._text(ttk.Label(box), key).grid(row=r, column=c * 2, sticky="w", padx=(0, 4), pady=2)
            ttk.Entry(box, textvariable=var, width=16).grid(row=r, column=c * 2 + 1, sticky="w", padx=(0, 16))
        self._text(ttk.Button(box, command=self._save_settings), "gui_save_settings").grid(
            row=0, column=4, rowspan=2, padx=8)

        # project
        proj = self._text(ttk.LabelFrame(self, padding=8), "gui_project")
        proj.pack(fill="x", pady=4)
        plug_row = ttk.Frame(proj)
        plug_row.pack(fill="x", pady=2)
        self._text(ttk.Label(plug_row), "gui_plugin_label").pack(side="left")
        self.plugin_box = ttk.Combobox(plug_row, state="readonly", width=38)
        self.plugin_box.pack(side="left", padx=4)
        self.plugin_box.bind("<<ComboboxSelected>>", self._on_plugin_pick)
        self._text(ttk.Button(plug_row, command=self._load_plugins), "gui_refresh").pack(side="left")

        dir_row = ttk.Frame(proj)
        dir_row.pack(fill="x", pady=2)
        self._text(ttk.Label(dir_row), "gui_project_label").pack(side="left")
        ttk.Entry(dir_row, textvariable=self.project_dir, width=46).pack(side="left", padx=4)
        ttk.Button(dir_row, text="...", width=3, command=self._browse).pack(side="left")

        btn_row = ttk.Frame(proj)
        btn_row.pack(fill="x", pady=(6, 0))
        self.run_btn = self._text(ttk.Button(btn_row, command=self._run_setup), "gui_prepare")
        self.run_btn.pack(side="left", padx=(0, 6))
        self._text(ttk.Button(btn_row, command=self._open_folder), "gui_open_folder").pack(side="left", padx=(0, 6))
        self._text(ttk.Button(btn_row, command=self._open_vscode), "gui_open_vscode").pack(side="left")

        # DevBridge QGIS plugin
        qbox = self._text(ttk.LabelFrame(self, padding=8), "gui_qgis_plugin")
        qbox.pack(fill="x", pady=4)
        self.bridge_btn = self._text(ttk.Button(qbox, command=self._install_bridge), "gui_install_bridge")
        self.bridge_btn.pack(side="left")
        if bridge_plugin.plugin_source() is None:
            self.bridge_btn.state(["disabled"])
            self._text(ttk.Label(qbox), "gui_bridge_unavailable").pack(side="left", padx=8)

        self.log = scrolledtext.ScrolledText(self, width=78, height=14, state="disabled")
        self.log.pack(fill="both", expand=True, pady=(6, 0))

    def _apply_texts(self) -> None:
        self.master.title(t("welcome"))
        for key, widgets in self._labels.items():
            for w in widgets:
                w.configure(text=t(key))

    # --- events ----------------------------------------------------------------
    def _on_lang_change(self, _evt=None) -> None:
        set_lang(self.lang.get())
        self._cfg["lang"] = get_lang()
        self._persist()
        self._apply_texts()

    def _show_guide(self) -> None:
        """Plain step-by-step instructions in a window of their own (re-opened in the current language)."""
        if getattr(self, "_guide_win", None) is not None and self._guide_win.winfo_exists():
            self._guide_win.destroy()
        win = self._guide_win = tk.Toplevel(self.master)
        win.title(t("gui_guide_title"))
        box = scrolledtext.ScrolledText(win, width=84, height=26, wrap="word", font="TkDefaultFont")
        box.insert("1.0", t("gui_guide_text"))
        box.configure(state="disabled")
        box.pack(fill="both", expand=True, padx=8, pady=8)

    def _load_plugins(self) -> None:
        self._plugins = profiles.find_plugins()
        self.plugin_box["values"] = [p.label for p in self._plugins]
        if self._plugins and not self.plugin_box.get():
            self.plugin_box.current(0)
            self._on_plugin_pick()

    def _on_plugin_pick(self, _evt=None) -> None:
        idx = self.plugin_box.current()
        if idx >= 0:
            self.project_dir.set(str(self._plugins[idx].path))

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(title=t("gui_browse_title"))
        if chosen:
            self.project_dir.set(chosen)

    def _settings_from_form(self) -> dict | None:
        try:
            cfg = dict(self._cfg)
            cfg.update(host=self.host.get().strip() or "localhost", port=int(self.port.get()),
                       pycharm_host=self.py_host.get().strip() or "localhost",
                       pycharm_port=int(self.py_port.get()))
        except ValueError:
            messagebox.showerror("DevBridge", t("gui_bad_port"))
            return None
        return cfg

    def _persist(self) -> None:
        try:
            config.save(self._cfg)
        except OSError as exc:
            self._log(f"ERROR: {exc}")

    def _save_settings(self) -> None:
        cfg = self._settings_from_form()
        if cfg is None:
            return
        self._cfg = cfg
        self._persist()
        self._log(t("gui_saved", path=config.config_path()))

    def _project_path(self) -> Path | None:
        raw = self.project_dir.get().strip()
        if not raw or not Path(raw).is_dir():
            messagebox.showwarning("DevBridge", t("gui_project_missing"))
            return None
        return Path(raw)

    def _open_folder(self) -> None:
        path = self._project_path()
        if path:
            desktop.open_folder(path)

    def _open_vscode(self) -> None:
        path = self._project_path()
        if path and not desktop.open_in_vscode(path):
            messagebox.showinfo("DevBridge", t("gui_vscode_missing"))

    # --- background work ------------------------------------------------------
    def _log(self, msg: str) -> None:
        """Thread-safe: workers only enqueue, the Tk thread does the drawing."""
        self._logq.put(msg)

    def _drain_log(self) -> None:
        try:
            while True:
                msg = self._logq.get_nowait()
                self.log.configure(state="normal")
                self.log.insert("end", msg + "\n")
                self.log.see("end")
                self.log.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(_POLL_MS, self._drain_log)

    def _run_setup(self) -> None:
        path = self._project_path()
        cfg = self._settings_from_form()
        if path is None or cfg is None:
            return
        self._cfg = cfg
        self._persist()
        self.run_btn.state(["disabled"])
        threading.Thread(target=self._setup_worker, args=(path, cfg["port"]), daemon=True).start()

    def _setup_worker(self, path: Path, port: int) -> None:
        try:
            pipeline.run_setup(path, port=port, log=self._log)
        except Exception as exc:  # surfaced in the log pane, not a stack-trace dialog
            self._log(f"ERROR: {exc}")
        finally:
            self.after(0, lambda: self.run_btn.state(["!disabled"]))

    def _install_bridge(self) -> None:
        def work():
            try:
                bridge_plugin.install_into_profiles(log=self._log)
            except Exception as exc:
                self._log(f"ERROR: {exc}")
        threading.Thread(target=work, daemon=True).start()


def launch() -> None:
    cfg = config.load()
    set_lang(cfg["lang"] or detect_system_lang())
    root = tk.Tk()
    DevBridgeApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch()
