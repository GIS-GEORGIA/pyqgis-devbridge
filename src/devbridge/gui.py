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

from . import bridge_plugin, config, desktop, doctor, launcher, pipeline, profiles, project_config, scaffold
from .i18n_util import detect_system_lang, get_lang, set_lang, t

_POLL_MS = 100


class DevBridgeApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master, padding=12)
        self.master = master
        self._cfg = config.load()
        self._plugins: list[profiles.ProfilePlugin] = []
        self._qgis_installs: list = []      # pipeline.QgisInstallation, most-preferred first
        self._logq: queue.Queue[str] = queue.Queue()
        self._labels: dict[str, list] = {}   # i18n key -> widgets whose text it drives

        self.lang = tk.StringVar(value=get_lang())
        self.host = tk.StringVar(value=str(self._cfg["host"]))
        self.port = tk.StringVar(value=str(self._cfg["port"]))
        self.py_host = tk.StringVar(value=str(self._cfg["pycharm_host"]))
        self.py_port = tk.StringVar(value=str(self._cfg["pycharm_port"]))
        self.project_dir = tk.StringVar(value="")
        self.mode = tk.StringVar(value="existing")          # existing | new | folder
        self.new_name = tk.StringVar(value="")
        default_parent = profiles.default_plugins_dir()
        self.new_parent = tk.StringVar(value=str(default_parent) if default_parent else "")

        self._build_widgets()
        self.pack(fill="both", expand=True)
        self._load_qgis_installs()
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

        # only matters when more than one QGIS is installed; harmless to show otherwise
        qgis_row = ttk.Frame(self)
        qgis_row.pack(fill="x", pady=(0, 4))
        self._text(ttk.Label(qgis_row), "gui_qgis_install").pack(side="left")
        self.qgis_box = ttk.Combobox(qgis_row, state="readonly", width=52)
        self.qgis_box.pack(side="left", padx=4)
        self._text(ttk.Button(qgis_row, command=self._load_qgis_installs), "gui_refresh").pack(side="left")

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

        # project: what do you want to do?
        proj = self._text(ttk.LabelFrame(self, padding=8), "gui_project")
        proj.pack(fill="x", pady=4)
        modes = ttk.Frame(proj)
        modes.pack(fill="x")
        for value, key in (("existing", "gui_mode_existing"), ("new", "gui_mode_new"), ("folder", "gui_mode_folder")):
            self._text(ttk.Radiobutton(modes, variable=self.mode, value=value, command=self._show_mode), key
                       ).pack(side="left", padx=(0, 14))

        # existing plugin: a list over ALL QGIS profiles, nothing pre-selected
        self.existing_row = ttk.Frame(proj)
        self._text(ttk.Label(self.existing_row), "gui_plugin_label").pack(side="left")
        self.plugin_box = ttk.Combobox(self.existing_row, state="readonly", width=44)
        self.plugin_box.pack(side="left", padx=4)
        self.plugin_box.bind("<<ComboboxSelected>>", self._on_plugin_pick)
        self._text(ttk.Button(self.existing_row, command=self._load_plugins), "gui_refresh").pack(side="left")

        # new plugin: name + where to create it
        self.new_frame = ttk.Frame(proj)
        r1 = ttk.Frame(self.new_frame)
        r1.pack(fill="x", pady=2)
        self._text(ttk.Label(r1, width=18), "gui_new_name").pack(side="left")
        ttk.Entry(r1, textvariable=self.new_name, width=30).pack(side="left", padx=4)
        r2 = ttk.Frame(self.new_frame)
        r2.pack(fill="x", pady=2)
        self._text(ttk.Label(r2, width=18), "gui_new_parent").pack(side="left")
        ttk.Entry(r2, textvariable=self.new_parent, width=46).pack(side="left", padx=4)
        ttk.Button(r2, text="...", width=3, command=self._browse_parent).pack(side="left")

        # any folder
        self.folder_row = ttk.Frame(proj)
        self._text(ttk.Label(self.folder_row), "gui_project_label").pack(side="left")
        ttk.Entry(self.folder_row, textvariable=self.project_dir, width=46).pack(side="left", padx=4)
        ttk.Button(self.folder_row, text="...", width=3, command=self._browse).pack(side="left")

        self.btn_row = ttk.Frame(proj)
        self.run_btn = self._text(ttk.Button(self.btn_row, command=self._run_setup), "gui_prepare")
        self.run_btn.pack(side="left", padx=(0, 6))
        self.open_btns = ttk.Frame(self.btn_row)
        self._text(ttk.Button(self.open_btns, command=self._open_folder), "gui_open_folder").pack(side="left", padx=(0, 6))
        self._text(ttk.Button(self.open_btns, command=self._open_vscode), "gui_open_vscode").pack(side="left", padx=(0, 6))
        self._text(ttk.Button(self.open_btns, command=self._launch_qgis), "gui_launch_qgis").pack(side="left", padx=(0, 6))
        self._text(ttk.Button(self.open_btns, command=self._run_doctor), "gui_doctor").pack(side="left")
        self.open_btns.pack(side="left")
        self._proj_frame = proj
        self._show_mode()

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
        if hasattr(self, "plugin_box"):                  # keep the current pick, retitle the placeholder
            current = self.plugin_box.current()
            self.plugin_box["values"] = [t("gui_plugin_placeholder")] + [p.label for p in self._plugins]
            self.plugin_box.current(max(current, 0))

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

    def _show_mode(self) -> None:
        for frame in (self.existing_row, self.new_frame, self.folder_row, self.btn_row):
            frame.pack_forget()
        mode = self.mode.get()
        {"existing": self.existing_row, "new": self.new_frame, "folder": self.folder_row}[mode].pack(
            fill="x", pady=(8, 2))
        self.btn_row.pack(fill="x", pady=(6, 0))
        self._sync_prepare_label()

    def _sync_prepare_label(self) -> None:
        """The prepare button doubles as 'Create and prepare' in new-plugin mode."""
        key = "gui_new_create" if self.mode.get() == "new" else "gui_prepare"
        for k, widgets in self._labels.items():
            if self.run_btn in widgets and k != key:
                widgets.remove(self.run_btn)
        self._labels.setdefault(key, [])
        if self.run_btn not in self._labels[key]:
            self._labels[key].append(self.run_btn)
        self.run_btn.configure(text=t(key))

    def _load_qgis_installs(self) -> None:
        self._qgis_installs = pipeline.find_all_qgis(log=lambda _msg: None)
        self.qgis_box["values"] = (
            [str(q.root) + ("  (default)" if i == 0 else "") for i, q in enumerate(self._qgis_installs)]
            or [t("gui_no_qgis_found")]
        )
        self.qgis_box.current(0)

    def _selected_qgis(self):
        idx = self.qgis_box.current()
        return self._qgis_installs[idx] if 0 <= idx < len(self._qgis_installs) else None

    def _load_plugins(self) -> None:
        self._plugins = profiles.find_plugins()
        self.plugin_box["values"] = [t("gui_plugin_placeholder")] + [p.label for p in self._plugins]
        self.plugin_box.current(0)                       # nothing chosen until the user picks
        if self.mode.get() == "existing":
            self.project_dir.set("")

    def _on_plugin_pick(self, _evt=None) -> None:
        idx = self.plugin_box.current() - 1              # entry 0 is the placeholder
        self.project_dir.set(str(self._plugins[idx].path) if 0 <= idx < len(self._plugins) else "")

    def _browse_parent(self) -> None:
        chosen = filedialog.askdirectory(title=t("gui_browse_title"))
        if chosen:
            self.new_parent.set(chosen)

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
        if not raw and self.mode.get() == "existing":
            messagebox.showwarning("DevBridge", t("gui_choose_plugin_first"))
            return None
        if not raw or not Path(raw).is_dir():
            messagebox.showwarning("DevBridge", t("gui_project_missing"))
            return None
        return Path(raw)

    def _create_new(self) -> Path | None:
        """New-plugin mode: write the starter files, then it is prepared like any other folder."""
        parent, name = Path(self.new_parent.get().strip() or "."), self.new_name.get().strip()
        try:
            parent.mkdir(parents=True, exist_ok=True)
            path = scaffold.create_plugin(parent, name)
        except (scaffold.ScaffoldError, OSError) as exc:
            key = f"new_{exc}" if isinstance(exc, scaffold.ScaffoldError) else None
            messagebox.showwarning("DevBridge", t(key, name=name, path=parent) if key else str(exc))
            return None
        self._log(t("new_created", path=path))
        self.project_dir.set(str(path))
        return path

    def _open_folder(self) -> None:
        path = self._project_path()
        if path:
            desktop.open_folder(path)

    def _open_vscode(self) -> None:
        path = self._project_path()
        if path and not desktop.open_in_vscode(path):
            messagebox.showinfo("DevBridge", t("gui_vscode_missing"))

    def _launch_qgis(self) -> None:
        """Starts QGIS with the debug bridge already listening - the same
        thing VS Code's F5 ("PyQGIS: Launch QGIS + attach") does, useful to
        try once by hand before wiring it into an IDE."""
        path = self._project_path()
        if path is None:
            return
        qgis = self._selected_qgis()      # read the Tk widget here, on the main thread, not in the worker
        threading.Thread(target=self._launch_qgis_worker, args=(path, qgis), daemon=True).start()

    def _launch_qgis_worker(self, path: Path, qgis) -> None:
        try:
            qgis = qgis or pipeline.find_qgis(self._log)
            cfg = project_config.read_project_config(path)
            code = launcher.launch_qgis(qgis, host=cfg["host"], port=cfg["port"],
                                        wait_ready=True, verbose_print=self._log)
            if code != 0:
                self._log(t("gui_launch_failed"))
        except pipeline.SetupError as exc:
            self._log(str(exc))

    def _run_doctor(self) -> None:
        """Checks the whole chain (QGIS, debugpy, the plugin, the port, and
        this project's .venv/.devbridge.json/.vscode if one is selected)."""
        path = self.project_dir.get().strip() or None
        cfg = self._settings_from_form()
        port = cfg["port"] if cfg else None
        qgis = self._selected_qgis()      # read the Tk widget here, on the main thread, not in the worker
        threading.Thread(target=self._doctor_worker, args=(path, port, qgis), daemon=True).start()

    def _doctor_worker(self, path: str | None, port: int | None, qgis) -> None:
        checks = doctor.run_checks(project_dir=path, port=port, qgis=qgis, log=self._log)
        doctor.print_report(checks, log=self._log)

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
        cfg = self._settings_from_form()
        if cfg is None:
            return
        path = self._create_new() if self.mode.get() == "new" else self._project_path()
        if path is None:
            return
        self._cfg = cfg
        self._persist()
        self.run_btn.state(["disabled"])
        # Read every Tk widget/variable here, on the main thread - not in the worker thread below.
        qgis, is_new = self._selected_qgis(), self.mode.get() == "new"
        threading.Thread(target=self._setup_worker, args=(path, cfg["port"], qgis, is_new), daemon=True).start()

    def _setup_worker(self, path: Path, port: int, qgis, is_new: bool) -> None:
        try:
            pipeline.run_setup(path, port=port, log=self._log, qgis=qgis)
            if is_new:
                self._log(t("new_next_steps"))
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
