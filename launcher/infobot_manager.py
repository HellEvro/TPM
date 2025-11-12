#!/usr/bin/env python3
"""
InfoBot Manager GUI

Provides a cross-platform control panel to:
- Install/upgrade dependencies inside the project virtual environment
- Check for git updates
- Retrieve hardware ID and license instructions
- Launch/stop app.py, bots.py and ai.py services
- Manage license files (.lic) and open configuration folders
"""

from __future__ import annotations

import atexit
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import threading
import webbrowser
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:  # pragma: no cover - tkinter should be available on all supported systems
    print("tkinter is required to run the InfoBot Manager GUI.")
    print("Install the python3-tk package or a Python distribution with tkinter support.")
    raise SystemExit(str(exc))


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = PROJECT_ROOT / ".venv"
DEFAULT_REMOTE_URL = "git@github.com:HellEvro/TPM_Public.git"


def _detect_python_executable() -> str:
    if os.name == "nt":
        venv_python = VENV_DIR / "Scripts" / "python.exe"
    else:
        venv_python = VENV_DIR / "bin" / "python"

    if venv_python.exists():
        return str(venv_python)

    # Fallbacks
    if os.name == "nt":
        launcher = shutil.which("py")
        if launcher:
            return f"{launcher} -3"
        return "python"

    return shutil.which("python3") or sys.executable


PYTHON_EXECUTABLE = _detect_python_executable()


ERROR_KEYWORDS = (
    "error",
    "exception",
    "traceback",
    "critical",
    "fatal",
    "fail",
    "failed",
    "stderr",
    "не удалось",
    "невозможно",
    "ошибк",
    "критич",
    "аварийн",
    "stacktrace",
    "panic",
    "cannot",
    "can't",
    "refused",
    "denied",
    "permission denied",
    "timeout",
    "timed out",
    "errno",
    "traceback (most recent call last",
)

SUPPRESSED_SEVERITIES = (
    "warning",
    "warn",
    "предупрежд",
    "caution",
    "info",
    "инфо",
    "inform",
    "success",
    "успех",
    "debug",
    "trace",
    "verbose",
    "notice",
    "ℹ️",
    "⚠️",
    "✅",
)

ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


class ManagedProcess:
    """Wraps a subprocess and streams its output to a Tkinter-safe queue."""

    def __init__(self, name: str, command: List[str], channel: str):
        self.name = name
        self.command = command
        self.channel = channel
        self.process: Optional[subprocess.Popen[str]] = None
        self._reader_thread: Optional[threading.Thread] = None
        self.child_pids: Set[int] = set()

    def start(self, log_queue: "queue.Queue[Tuple[str, str]]") -> None:
        if self.is_running:
            raise RuntimeError(f"{self.name} already running")

        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{PROJECT_ROOT}{os.pathsep}{pythonpath}" if pythonpath else str(PROJECT_ROOT)

        # On Windows we can optionally create a new console window.
        popen_kwargs: Dict[str, object] = {
            "cwd": str(PROJECT_ROOT),
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
            "env": env,
        }
        if os.name != "nt":
            popen_kwargs["start_new_session"] = True

        self.process = subprocess.Popen(self.command, **popen_kwargs)  # type: ignore[arg-type]

        def _safe_put(item: Tuple[str, str]) -> None:
            while True:
                try:
                    log_queue.put_nowait(item)
                    break
                except queue.Full:
                    try:
                        log_queue.get_nowait()
                    except queue.Empty:
                        break

        def _reader() -> None:
            assert self.process and self.process.stdout
            self._snapshot_children()
            startup_message = f"{self.name} запущен и работает. Все ошибки будут показаны здесь."
            _safe_put((self.channel, startup_message))
            _safe_put(("system", startup_message))
            last_snapshot = time.monotonic()
            for line in self.process.stdout:
                now = time.monotonic()
                if now - last_snapshot >= 1.0:
                    self._snapshot_children()
                    last_snapshot = now
                stripped = line.strip()
                if not stripped:
                    continue
                if self._is_error_line(stripped, service_channel=self.channel):
                    message = f"[{self.name}] {stripped}"
                    _safe_put((self.channel, message))
                    _safe_put(("system", message))
            self.process.stdout.close()
            self._snapshot_children()

        self._reader_thread = threading.Thread(target=_reader, daemon=True)
        self._reader_thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        if not self.process or self.process.poll() is not None:
            return

        self._snapshot_children()
        self._kill_children()

        self.process.terminate()
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

        if self._reader_thread:
            self._reader_thread.join(timeout=1)

        self.process = None
        self._reader_thread = None
        self.child_pids.clear()

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def pid(self) -> Optional[int]:
        return self.process.pid if self.process else None

    def _kill_process_tree_win(self) -> None:
        if not self.process:
            return
        try:
            subprocess.run(
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception:
            pass

    def _kill_process_tree_posix(self) -> None:
        if not self.process:
            return
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        except Exception:
            pass

    def _kill_children(self) -> None:
        self._snapshot_children()
        if os.name == "nt":
            self._kill_process_tree_win()
        else:
            self._kill_process_tree_posix()
        if not self.child_pids:
            return
        for pid in list(self.child_pids):
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        capture_output=True,
                        check=False,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                else:
                    os.kill(pid, signal.SIGTERM)
            except Exception:
                continue
        self.child_pids.clear()

    def _snapshot_children(self) -> None:
        if not self.process:
            return
        try:
            import psutil  # type: ignore import
        except Exception:
            return

        try:
            parent = psutil.Process(self.process.pid)
            descendants = parent.children(recursive=True)
            current = {proc.pid for proc in descendants if proc.is_running()}
            self.child_pids = current
        except Exception:
            pass

    def _is_error_line(self, text: str, service_channel: Optional[str] = None) -> bool:
        cleaned = ANSI_ESCAPE_RE.sub("", text)
        lowered = cleaned.lower()

        if any(marker in lowered for marker in SUPPRESSED_SEVERITIES):
            return False
        if "ошибок: 0" in lowered or "ошибок 0" in lowered:
            return False

        if service_channel == "system":
            return any(keyword in lowered for keyword in ERROR_KEYWORDS)

        if " warning " in lowered or lowered.startswith("warning"):
            return False

        return any(keyword in lowered for keyword in ERROR_KEYWORDS)


class InfoBotManager(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("InfoBot Manager")
        self.geometry("980x720")
        self.minsize(820, 600)

        self.log_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue(maxsize=3000)
        self.processes: Dict[str, ManagedProcess] = {}
        self.log_text_widgets: Dict[str, tk.Text] = {}
        self.log_tab_ids: Dict[str, str] = {}
        self.log_notebook: Optional[ttk.Notebook] = None
        self._temp_requirements_path: Optional[Path] = None
        self.status_var = tk.StringVar(value="Готово")
        self._active_tasks: Set[str] = set()
        self.max_log_lines = 2000
        self.active_log_channel = "system"
        self.pending_logs: Dict[str, List[str]] = defaultdict(list)
        atexit.register(self._cleanup_processes)

        self._ensure_utf8_console()

        self.env_status_var = tk.StringVar()
        self.git_status_var = tk.StringVar()
        self.license_status_var = tk.StringVar()
        self.update_environment_status()
        self.ensure_git_repository()
        self.update_git_status(initial=True)
        self.update_license_status()

        self.service_status_vars: Dict[str, tk.StringVar] = {}

        self._build_ui()
        self.after(200, self._flush_logs)
        self.after(1200, self._refresh_service_statuses)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI builder
    def _build_ui(self) -> None:
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        canvas.configure(yscrollcommand=scrollbar.set)

        scrollable = ttk.Frame(canvas)
        def _on_scrollable_configure(event: tk.Event) -> None:
            bbox = canvas.bbox("all")
            if bbox:
                canvas.configure(scrollregion=bbox)
                content_height = bbox[3] - bbox[1]
                if content_height <= canvas.winfo_height():
                    canvas.yview_moveto(0)

        scrollable.bind("<Configure>", _on_scrollable_configure)

        window_id = canvas.create_window((0, 0), window=scrollable, anchor="nw")

        def _resize_canvas(event: tk.Event) -> None:  # type: ignore[override]
            canvas.itemconfigure(window_id, width=event.width)

        canvas.bind("<Configure>", _resize_canvas)

        main = ttk.Frame(scrollable, padding=(12, 0, 12, 12))
        main.grid(row=0, column=0, sticky="nsew")

        scrollable.columnconfigure(0, weight=1)
        scrollable.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(9, weight=1)

        self._enable_mousewheel(canvas)

        status_frame = ttk.Frame(main, padding=(0, 0, 0, 6))
        status_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        status_frame.columnconfigure(1, weight=1)
        ttk.Label(status_frame, text="Статус операций:").grid(row=0, column=0, sticky="w")
        ttk.Label(status_frame, textvariable=self.status_var).grid(row=0, column=1, sticky="w")
        self.loader = ttk.Progressbar(status_frame, mode="indeterminate", length=150)
        self.loader.grid(row=0, column=2, sticky="e")
        self.loader.stop()
        self.loader.grid_remove()

        separator = ttk.Separator(main, orient="horizontal")
        separator.grid(row=1, column=0, sticky="ew", padx=4)

        venv_frame = ttk.LabelFrame(main, text="1. Виртуальное окружение (рекомендуется, вместо прямой установки в системный Python в п.2)", padding=10)
        venv_frame.grid(row=2, column=0, sticky="new", padx=4, pady=(4, 4))
        venv_frame.columnconfigure(1, weight=1)

        ttk.Label(venv_frame, text="Статус:").grid(row=0, column=0, sticky="w")
        ttk.Label(venv_frame, textvariable=self.env_status_var).grid(row=0, column=1, sticky="w")
        btn_create_venv = ttk.Button(
            venv_frame,
            text="Создать/обновить окружение (.venv)",
        )
        btn_create_venv.grid(row=1, column=0, sticky="w", pady=(6, 0))
        btn_create_venv.configure(command=lambda b=btn_create_venv: self.install_dependencies(b))
        btn_delete_venv = ttk.Button(
            venv_frame,
            text="Удалить окружение (.venv)",
        )
        btn_delete_venv.grid(row=1, column=1, sticky="w", pady=(6, 0))
        btn_delete_venv.configure(command=lambda b=btn_delete_venv: self.delete_environment(b))

        install_frame = ttk.LabelFrame(main, text="2. Установка зависимостей напрямую (опционально, изменяет системный Python)", padding=10)
        install_frame.grid(row=3, column=0, sticky="new", padx=4, pady=4)
        install_frame.columnconfigure(0, weight=1)

        self.btn_install_global = ttk.Button(
            install_frame,
            text="Установить/обновить зависимости (pip install -r requirements.txt)",
        )
        self.btn_install_global.grid(row=0, column=0, sticky="w")
        self.btn_install_global.configure(command=lambda b=self.btn_install_global: self.install_dependencies_global(b))

        self.install_note_var = tk.StringVar()
        ttk.Label(install_frame, textvariable=self.install_note_var, foreground="#707070").grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Button(
            install_frame,
            text="Открыть каталог проекта",
            command=lambda: self.open_path(PROJECT_ROOT),
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        git_frame = ttk.LabelFrame(main, text="3. Обновления из Git", padding=10)
        git_frame.grid(row=4, column=0, sticky="new", padx=4, pady=4)
        git_frame.columnconfigure(1, weight=1)

        ttk.Label(git_frame, text="Статус репозитория:").grid(row=0, column=0, sticky="w")
        ttk.Label(git_frame, textvariable=self.git_status_var).grid(row=0, column=1, sticky="w")

        btn_git_sync = ttk.Button(git_frame, text="Получить обновления (fetch + reset)")
        btn_git_sync.grid(row=1, column=0, sticky="w", pady=(6, 0))
        btn_git_sync.configure(command=lambda b=btn_git_sync: self.sync_with_remote(b))

        license_frame = ttk.LabelFrame(main, text="4. Лицензия и ключи (опционально)", padding=10)
        license_frame.grid(row=5, column=0, sticky="new", padx=4, pady=4)
        license_frame.columnconfigure(1, weight=1)

        ttk.Label(license_frame, text="Статус лицензии:").grid(row=0, column=0, sticky="w")
        ttk.Label(license_frame, textvariable=self.license_status_var).grid(row=0, column=1, sticky="w")

        btn_hwid = ttk.Button(license_frame, text="Получить Hardware ID")
        btn_hwid.grid(row=1, column=0, sticky="w", pady=(6, 0))
        btn_hwid.configure(command=lambda b=btn_hwid: self.run_license_activation(b))
        ttk.Button(license_frame, text="Импортировать .lic файл", command=self.import_license_file).grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )
        ttk.Button(
            license_frame,
            text="Как настроить ключи?",
            command=lambda: self.open_path(PROJECT_ROOT / "docs" / "INSTALL.md"),
        ).grid(row=1, column=2, sticky="w", pady=(6, 0))

        services_frame = ttk.LabelFrame(main, text="5. Запуск сервисов", padding=10)
        services_frame.grid(row=6, column=0, sticky="new", padx=4, pady=4)
        services_frame.columnconfigure(1, weight=1)

        header_frame = ttk.Frame(services_frame)
        header_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        header_frame.columnconfigure(0, weight=1)

        ttk.Label(header_frame, text="Управление сервисами:").grid(row=0, column=0, sticky="w")
        ttk.Button(header_frame, text="Запустить все", command=self.start_all_services).grid(
            row=0, column=1, padx=(8, 4), sticky="e"
        )
        ttk.Button(header_frame, text="Остановить все", command=self.stop_all_services).grid(
            row=0, column=2, sticky="e"
        )

        config_frame = ttk.Frame(services_frame)
        config_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Button(config_frame, text="Редактировать конфиг (app/config.py)", command=self.open_config_file).pack(side=tk.LEFT)
        ttk.Button(config_frame, text="Редактировать ключи (app/keys.py)", command=self.open_keys_file).pack(side=tk.LEFT, padx=(8, 0))

        for idx, (service_id, meta) in enumerate(self._services().items(), start=2):
            status_var = tk.StringVar(value="Не запущен")
            self.service_status_vars[service_id] = status_var
            ttk.Label(services_frame, text=meta["title"]).grid(row=idx, column=0, sticky="w")
            ttk.Label(services_frame, textvariable=status_var).grid(row=idx, column=1, sticky="w")
            button_frame = ttk.Frame(services_frame)
            button_frame.grid(row=idx, column=2, sticky="w")
            ttk.Button(button_frame, text="Запустить", command=lambda sid=service_id: self.start_service(sid)).pack(
                side=tk.LEFT, padx=(0, 4)
            )
            ttk.Button(button_frame, text="Остановить", command=lambda sid=service_id: self.stop_service(sid)).pack(
                side=tk.LEFT
            )

        docs_frame = ttk.LabelFrame(main, text="6. Документация и файлы", padding=10)
        docs_frame.grid(row=7, column=0, sticky="new", padx=4, pady=4)
        docs_frame.columnconfigure(0, weight=1)

        ttk.Button(docs_frame, text="Открыть README", command=lambda: self.open_path(PROJECT_ROOT / "README.md")).pack(
            anchor="w"
        )
        ttk.Button(
            docs_frame,
            text="Открыть лог ботов",
            command=self.open_bots_log,
        ).pack(anchor="w", pady=(4, 0))

        contacts_frame = ttk.Frame(main, padding=10)
        contacts_frame.grid(row=8, column=0, sticky="ew", padx=4, pady=(0, 4))
        contacts_frame.columnconfigure(0, weight=1)

        link_style = {"fg": "#0a66c2", "cursor": "hand2"}

        telegram_label = tk.Label(
            contacts_frame,
            text="📨 Telegram: h3113vr0",
            **link_style,
        )
        telegram_label.grid(row=0, column=0, sticky="w")
        telegram_label.config(font=(telegram_label.cget("font"), 10, "underline"))
        telegram_label.bind("<Button-1>", lambda _event: self.open_link("https://t.me/H3113vr0"))

        email_label = tk.Label(
            contacts_frame,
            text="📧 Email: gci.company.ou@gmail.com",
            **link_style,
        )
        email_label.grid(row=0, column=1, sticky="w", padx=(16, 0))
        email_label.config(font=(email_label.cget("font"), 10, "underline"))
        email_label.bind("<Button-1>", lambda _event: self.open_link("mailto:gci.company.ou@gmail.com"))
        log_frame = ttk.LabelFrame(main, text="7. Логи и вывод команд", padding=10)
        log_frame.grid(row=9, column=0, sticky="nsew", padx=4, pady=4)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(log_frame)
        notebook.grid(row=0, column=0, sticky="nsew")
        self.log_notebook = notebook
        self.log_tab_ids = {}
        notebook.bind("<<NotebookTabChanged>>", self._on_log_tab_changed)

        log_tabs = [
            ("system", "Системные события"),
            ("app", "Web UI (app.py)"),
            ("bots", "Bots Service (bots.py)"),
            ("ai", "AI Engine (ai.py)"),
        ]

        for channel, title in log_tabs:
            tab = ttk.Frame(notebook)
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)
            notebook.add(tab, text=title)
            tab_id = notebook.tabs()[-1]
            self.log_tab_ids[tab_id] = channel

            text_widget = tk.Text(tab, wrap="word", height=12)
            text_widget.grid(row=0, column=0, sticky="nsew")
            scrollbar = ttk.Scrollbar(tab, command=text_widget.yview)
            scrollbar.grid(row=0, column=1, sticky="ns")
            text_widget["yscrollcommand"] = scrollbar.set
            text_widget.bind("<Key>", self._log_text_key_handler)
            text_widget.bind("<<Paste>>", lambda event: "break")
            text_widget.bind("<<Cut>>", lambda event: "break")
            text_widget.bind("<Button-3>", lambda event, widget=text_widget: self._show_log_context_menu(event, widget))
            self.log_text_widgets[channel] = text_widget

        ttk.Button(
            log_frame,
            text="Скопировать текущий лог",
            command=self.copy_current_log,
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        # Обновляем статус окружения после создания элементов UI,
        # чтобы кнопка глобальной установки корректно отразила состояние.
        self.update_environment_status()

    def _enable_mousewheel(self, widget: tk.Widget) -> None:
        if sys.platform == "darwin":
            widget.bind_all("<MouseWheel>", lambda event: widget.yview_scroll(int(-event.delta), "units"))
            widget.bind_all("<Button-4>", lambda event: widget.yview_scroll(-1, "units"))
            widget.bind_all("<Button-5>", lambda event: widget.yview_scroll(1, "units"))
        else:
            widget.bind_all("<MouseWheel>", lambda event: widget.yview_scroll(int(-event.delta / 120), "units"))
            widget.bind_all("<Button-4>", lambda event: widget.yview_scroll(-1, "units"))
            widget.bind_all("<Button-5>", lambda event: widget.yview_scroll(1, "units"))

    def _log_text_key_handler(self, event: tk.Event) -> Optional[str]:
        nav_keys = {"Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"}
        if event.keysym in nav_keys:
            return None

        ctrl_pressed = (event.state & 0x4) != 0
        if ctrl_pressed:
            lowered = event.keysym.lower()
            if lowered == "c":
                return None
            if lowered == "a":
                event.widget.tag_add("sel", "1.0", tk.END)
                return "break"

        return "break"

    def _show_log_context_menu(self, event: tk.Event, widget: tk.Text) -> None:
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="Копировать", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Выделить всё", command=lambda: widget.tag_add("sel", "1.0", tk.END))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ------------------------------------------------------------------ Helpers
    def _services(self) -> Dict[str, Dict[str, str]]:
        python = PYTHON_EXECUTABLE.split() if " " in PYTHON_EXECUTABLE else [PYTHON_EXECUTABLE]
        return {
            "app": {
                "title": "Web UI (app.py, порт 5000)",
                "command": python + ["app.py"],
            },
            "bots": {
                "title": "Bots Service (bots.py, порт 5001)",
                "command": python + ["bots.py"],
            },
            "ai": {
                "title": "AI Engine (ai.py) (не обязателен)",
                "command": python + ["ai.py"],
            },
        }

    def update_environment_status(self) -> None:
        if VENV_DIR.exists():
            python = "python.exe" if os.name == "nt" else "python"
            self.env_status_var.set(f".venv найден (используется {python})")
            if hasattr(self, "btn_install_global"):
                self.btn_install_global.configure(state=tk.DISABLED)
            if hasattr(self, "install_note_var"):
                self.install_note_var.set("Виртуальное окружение активно. Чтобы установить зависимости в системный Python, удалите папку .venv.")
        else:
            self.env_status_var.set("Виртуальное окружение не создано (используется системный Python)")
            if hasattr(self, "btn_install_global"):
                self.btn_install_global.configure(state=tk.NORMAL)
            if hasattr(self, "install_note_var"):
                self.install_note_var.set("")

    def ensure_git_repository(self) -> None:
        git_dir = PROJECT_ROOT / ".git"
        if git_dir.exists():
            try:
                result = subprocess.run(
                    ["git", "symbolic-ref", "--short", "HEAD"],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=True,
                )
                current_branch = result.stdout.strip()
                if current_branch == "master":
                    subprocess.run(
                        ["git", "branch", "-m", "main"],
                        cwd=str(PROJECT_ROOT),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        check=True,
                    )
                    self.log("Переименована ветка master → main", channel="system")
                    self.update_git_status()
                self._configure_git_upstream()
                self._auto_align_main_with_remote()
            except subprocess.CalledProcessError:
                pass
            return
        if not shutil.which("git"):
            self.git_status_var.set("git не найден (обновления недоступны)")
            self.log("Git не установлен: обновления репозитория отключены.")
            return
        try:
            init_result = subprocess.run(
                ["git", "init"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            subprocess.run(
                ["git", "branch", "-m", "main"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            if init_result.stdout.strip():
                self.log(init_result.stdout.strip())
            remote_result = subprocess.run(
                ["git", "remote", "add", "origin", DEFAULT_REMOTE_URL],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            if remote_result.stdout.strip():
                self.log(remote_result.stdout.strip())
            self._configure_git_upstream()
            self._auto_align_main_with_remote()
            self.log(f"Git репозиторий инициализирован. origin → {DEFAULT_REMOTE_URL}")
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else str(exc)
            self.log(f"[git] Не удалось инициализировать репозиторий: {stderr}")

    def update_git_status(self, initial: bool = False) -> None:
        if not shutil.which("git"):
            self.git_status_var.set("git не найден (обновления недоступны)")
            return
        try:
            result = subprocess.run(
                ["git", "status", "-sb"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                check=True,
            )
            line = result.stdout.strip().splitlines()[0] if result.stdout else "Репозиторий"
            self.git_status_var.set(line)
        except subprocess.CalledProcessError as exc:
            if initial:
                self.git_status_var.set(f"Ошибка git status: {exc.returncode}")
            else:
                self.log(f"[git] Ошибка git status: {exc}")

    def update_license_status(self) -> None:
        lic_files = sorted(PROJECT_ROOT.glob("*.lic"))
        if lic_files:
            self.license_status_var.set(f"Найден файл: {lic_files[0].name}")
        else:
            self.license_status_var.set("Лицензия не найдена (.lic файл в корне проекта)")

    def _enqueue_log(self, channel: str, message: str, broadcast: bool = True) -> None:
        if broadcast and channel != "system":
            self._safe_put_log(("system", message))
        self._safe_put_log((channel, message))

    def log(self, message: str, channel: str = "system", broadcast: bool = False) -> None:
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self._enqueue_log(channel, formatted, broadcast=broadcast)

    def _flush_logs(self) -> None:
        max_lines_per_tick = 150
        processed = 0
        while processed < max_lines_per_tick:
            try:
                channel, line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            widget = self.log_text_widgets.get(channel) or self.log_text_widgets.get("system")
            if widget is None:
                continue
            self._append_log_line(widget, line, channel)
            processed += 1
        delay = 50 if not self.log_queue.empty() else 200
        self.after(delay, self._flush_logs)

    def _append_log_line(self, widget: tk.Text, line: str, channel: str) -> None:
        if channel != self.active_log_channel:
            buffer = self.pending_logs[channel]
            buffer.append(line)
            if len(buffer) > self.max_log_lines:
                del buffer[: len(buffer) - self.max_log_lines]
            return
        widget.insert(tk.END, line + "\n")
        if channel == self.active_log_channel:
            widget.see(tk.END)
        self._trim_text_widget(widget)

    def _trim_text_widget(self, widget: tk.Text) -> None:
        max_lines = getattr(self, "max_log_lines", 2000)
        try:
            end_index = widget.index("end-1c")
        except tk.TclError:
            return
        if not end_index:
            return
        try:
            total_lines = int(end_index.split(".")[0])
        except (ValueError, IndexError):
            return
        if total_lines <= max_lines:
            return
        lines_to_remove = total_lines - max_lines
        try:
            widget.delete("1.0", f"{lines_to_remove + 1}.0")
        except tk.TclError:
            pass

    def _safe_put_log(self, item: Tuple[str, str]) -> None:
        while True:
            try:
                self.log_queue.put_nowait(item)
                break
            except queue.Full:
                try:
                    self.log_queue.get_nowait()
                except queue.Empty:
                    break

    def _cleanup_processes(self) -> None:
        try:
            self.stop_all_services()
        except Exception:
            pass

    def _on_log_tab_changed(self, event: tk.Event) -> None:
        widget = event.widget
        if not isinstance(widget, ttk.Notebook):
            return
        selected = widget.select()
        channel = self.log_tab_ids.get(selected)
        if channel:
            self.active_log_channel = channel
            self._flush_pending_logs(channel)

    def _flush_pending_logs(self, channel: str) -> None:
        pending = self.pending_logs.get(channel)
        if not pending:
            return
        widget = self.log_text_widgets.get(channel)
        if not widget:
            return
        text = "".join(f"{line}\n" for line in pending)
        widget.insert(tk.END, text)
        widget.see(tk.END)
        self._trim_text_widget(widget)
        pending.clear()

    def _refresh_service_statuses(self) -> None:
        for service_id, status_var in self.service_status_vars.items():
            proc = self.processes.get(service_id)
            if proc and proc.is_running:
                status_var.set(f"Запущен (PID {proc.pid})")
            else:
                status_var.set("Не запущен")
                if proc and not proc.is_running:
                    self.processes.pop(service_id, None)
        self.after(1200, self._refresh_service_statuses)

    # ------------------------------------------------------------------ Command execution
    def _stream_command(self, title: str, command: List[str], channel: str = "system") -> None:
        self.log(f"[{title}] Запуск: {' '.join(command)}", channel=channel)
        try:
            proc = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            self.log(f"[{title}] Команда не найдена: {command[0]}", channel=channel)
            return

        assert proc.stdout
        for line in proc.stdout:
            self._enqueue_log(channel, f"[{title}] {line.rstrip()}")
        return_code = proc.wait()
        if return_code == 0:
            self.log(f"[{title}] Успешно завершено.", channel=channel)
        else:
            self.log(f"[{title}] Завершено с ошибкой (код {return_code}).", channel=channel)
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)

    def install_dependencies(self, button: Optional[ttk.Button] = None) -> None:
        def worker() -> None:
            try:
                global PYTHON_EXECUTABLE

                if not VENV_DIR.exists():
                    try:
                        self._stream_command(
                            "Создание окружения",
                            [sys.executable, "-m", "venv", str(VENV_DIR)],
                            channel="system",
                        )
                    except subprocess.CalledProcessError as exc:
                        self.log(
                            f"Ошибка при создании виртуального окружения (.venv): {exc.returncode}",
                            channel="system",
                        )
                        return

                python_exec = _detect_python_executable()
                if not python_exec:
                    self.log("Не удалось определить Python для установки зависимостей.", channel="system")
                    return

                pip_cmd = _split_command(python_exec) + ["-m", "pip"]
                self._preinstall_ccxt_without_coincurve(pip_cmd)
                requirements_file = self._prepare_requirements_file()
                commands = [
                    ("Обновление pip", pip_cmd + ["install", "--upgrade", "pip", "setuptools", "wheel"]),
                    ("Установка зависимостей", pip_cmd + ["install", "-r", requirements_file]),
                ]
                for title, command in commands:
                    try:
                        self._stream_command(title, command, channel="system")
                    except subprocess.CalledProcessError as exc:
                        self.log(f"[{title}] Ошибка установки ({exc.returncode})", channel="system")
                        return
                self.update_environment_status()
                PYTHON_EXECUTABLE = _detect_python_executable()
            finally:
                self._cleanup_temp_requirements()

        self._run_task("install_venv", button, "Создание/обновление окружения", worker)

    def install_dependencies_global(self, button: Optional[ttk.Button] = None) -> None:
        def worker() -> None:
            try:
                pip_cmd = _split_command(sys.executable) + ["-m", "pip"]
                self._preinstall_ccxt_without_coincurve(pip_cmd)
                requirements_file = self._prepare_requirements_file()
                python_cmd = pip_cmd + ["install", "-r", requirements_file]
                try:
                    self._stream_command("Установка зависимостей (глобально)", python_cmd, channel="system")
                    self.log("Глобальная установка зависимостей завершена.", channel="system")
                except subprocess.CalledProcessError as exc:
                    self.log(
                        f"[Установка зависимостей (глобально)] Ошибка ({exc.returncode}). Убедитесь, что есть права и активный pip.",
                        channel="system",
                    )
            finally:
                self._cleanup_temp_requirements()

        self._run_task("install_global", button, "Установка зависимостей", worker)

    def delete_environment(self, button: Optional[ttk.Button] = None) -> None:
        if not VENV_DIR.exists():
            messagebox.showinfo("Информация", "Виртуальное окружение (.venv) отсутствует.")
            return
        if messagebox.askyesno(
            "Удалить .venv",
            "Удалить виртуальное окружение (.venv)? Все запущенные сервисы будут остановлены.",
        ):
            def worker() -> None:
                self.stop_all_services()
                try:
                    shutil.rmtree(VENV_DIR)
                    self.log("Виртуальное окружение (.venv) удалено.", channel="system")
                except OSError as exc:
                    self.log(
                        f"Не удалось удалить .venv: {exc}",
                        channel="system",
                    )
                    self.after(
                        0,
                        lambda e=exc: messagebox.showerror(
                            "Ошибка удаления",
                            f"{e}\n\nЕсли проблема сохраняется, закройте менеджер и удалите папку .venv вручную.",
                        ),
                    )
                finally:
                    self.update_environment_status()
                    global PYTHON_EXECUTABLE
                    PYTHON_EXECUTABLE = _detect_python_executable()

            self._run_task("delete_venv", button, "Удаление окружения", worker)

    def sync_with_remote(self, button: Optional[ttk.Button] = None) -> None:
        if not shutil.which("git"):
            messagebox.showwarning("Git не найден", "Для обновления необходимо установить Git.")
            return
        self._run_task("git_sync", button, "Получение обновлений", self._git_sync_worker)

    def run_license_activation(self, button: Optional[ttk.Button] = None) -> None:
        python_cmd = _split_command(PYTHON_EXECUTABLE)
        command = python_cmd + ["scripts/activate_premium.py"]
        self._run_task(
            "license_activation",
            button,
            "Получение Hardware ID",
            lambda: self._license_worker(command),
        )

    def import_license_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Выберите файл лицензии",
            filetypes=[("InfoBot License", "*.lic"), ("Все файлы", "*.*")],
        )
        if not file_path:
            return

        destination = PROJECT_ROOT / Path(file_path).name
        try:
            shutil.copy2(file_path, destination)
            self.log(f"[license] Файл {destination.name} скопирован в корень проекта.")
            self.update_license_status()
        except OSError as exc:
            messagebox.showerror("Ошибка копирования", str(exc))

    def start_service(self, service_id: str) -> None:
        if service_id in self.processes and self.processes[service_id].is_running:
            messagebox.showinfo("Уже запущено", f"Сервис {service_id} уже запущен.")
            return

        services = self._services()
        service = services[service_id]
        process = ManagedProcess(service["title"], service["command"], service_id)
        try:
            process.start(self.log_queue)
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("Ошибка запуска", str(exc))
            return
        self.processes[service_id] = process
        self.log(f"{service['title']} запущен (PID {process.pid})", channel=service_id)

    def stop_service(self, service_id: str) -> None:
        process = self.processes.get(service_id)
        if not process or not process.is_running:
            self.log(f"Сервис {service_id} не запущен.", channel=service_id)
            return
        process.stop()
        self.processes.pop(service_id, None)
        services = self._services()
        title = services.get(service_id, {}).get("title", service_id)
        self.log(f"{title} остановлен.", channel=service_id)
        self.log(f"{title} остановлен.", channel="system", broadcast=False)

    def stop_all_services(self) -> None:
        for service_id in list(self.processes.keys()):
            self.stop_service(service_id)

    def start_all_services(self) -> None:
        for service_id in self._services().keys():
            self.start_service(service_id)

    def _on_close(self) -> None:
        self.stop_all_services()
        self.destroy()

    def open_path(self, path: Path) -> None:
        path = path if path.is_absolute() else PROJECT_ROOT / path
        if not path.exists():
            messagebox.showwarning("Файл не найден", f"Файл или папка {path} не существует.")
            return
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(path)], check=False)
            else:
                subprocess.run(["xdg-open", str(path)], check=False)
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("Ошибка открытия", str(exc))

    def open_link(self, url: str) -> None:
        try:
            webbrowser.open(url, new=2)
        except Exception as exc:  # pylint: disable=broad-except
            messagebox.showerror("Ошибка открытия ссылки", str(exc))

    def open_config_file(self) -> None:
        target = PROJECT_ROOT / "app" / "config.py"
        example = PROJECT_ROOT / "app" / "config.example.py"
        if not target.exists():
            if example.exists():
                if messagebox.askyesno(
                    "Создать конфиг",
                    "Файл app/config.py не найден. Создать его из app/config.example.py?",
                ):
                    try:
                        shutil.copy2(example, target)
                        self._strip_example_header(target)
                        self.log("Создан app/config.py", channel="system")
                    except OSError as exc:
                        messagebox.showerror("Ошибка копирования", str(exc))
                        return
            else:
                messagebox.showwarning(
                    "Файл не найден",
                    "Файл app/config.py отсутствует. Скопируйте app/config.example.py и заполните его вручную.",
                )
                return
        self.open_path(target)

    def open_keys_file(self) -> None:
        target = PROJECT_ROOT / "app" / "keys.py"
        example = PROJECT_ROOT / "app" / "keys.example.py"
        if not target.exists():
            if example.exists():
                if messagebox.askyesno(
                    "Создать файл ключей",
                    "Файл app/keys.py не найден. Создать его из app/keys.example.py?",
                ):
                    try:
                        shutil.copy2(example, target)
                        self.log("Создан app/keys.py из app/keys.example.py", channel="system")
                    except OSError as exc:
                        messagebox.showerror("Ошибка копирования", str(exc))
                        return
            else:
                messagebox.showwarning(
                    "Файл не найден",
                    "Файл app/keys.py отсутствует. Скопируйте app/keys.example.py и заполните его вручную.",
                )
                return
        self.open_path(target)

    def open_bots_log(self) -> None:
        target = PROJECT_ROOT / "logs" / "bots.log"
        if not target.exists():
            if messagebox.askyesno(
                "Лог не найден",
                "Файл logs/bots.log ещё не создан. Создать пустой файл?",
            ):
                try:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.touch()
                    self.log("Создан пустой файл logs/bots.log", channel="system")
                except OSError as exc:
                    messagebox.showerror("Ошибка создания файла", str(exc))
                    return
            else:
                messagebox.showinfo(
                    "Лог отсутствует",
                    "Файл logs/bots.log появится после первого запуска сервиса bots.py.",
                )
                return
        self.open_path(target)

    def copy_current_log(self) -> None:
        if not self.log_notebook:
            return
        current_tab = self.log_notebook.select()
        channel = self.log_tab_ids.get(current_tab, "system")
        widget = self.log_text_widgets.get(channel)
        if not widget:
            messagebox.showinfo("Лог не найден", "Не удалось определить активный лог.")
            return
        text = widget.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Пусто", "В текущем логе нет данных для копирования.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Готово", "Содержимое лога скопировано в буфер обмена.")

    def _git_sync_worker(self) -> None:
        self.ensure_git_repository()
        try:
            self._stream_command("git fetch", ["git", "fetch", "--all", "--prune"])
            self._stream_command("git status", ["git", "status", "-sb"])
            self._stream_command("git pull", ["git", "pull", "--ff-only"])
        except subprocess.CalledProcessError:
            pass
        self._configure_git_upstream()
        self._auto_align_main_with_remote()
        self._run_git_log_preview()
        self.update_git_status()
        self._auto_align_main_with_remote()

    def _license_worker(self, command: List[str]) -> None:
        try:
            self._stream_command("license", command)
        except subprocess.CalledProcessError:
            pass
        self.update_license_status()

    def _set_status(self, text: str, busy: bool) -> None:
        self.status_var.set(text)
        if busy:
            if not self.loader.winfo_ismapped():
                self.loader.grid()
            self.loader.start(10)
        else:
            self.loader.stop()
            if self.loader.winfo_ismapped():
                self.loader.grid_remove()

    def _run_task(
        self,
        task_id: str,
        button: Optional[ttk.Button],
        description: str,
        worker: Callable[[], None],
    ) -> None:
        if task_id in self._active_tasks:
            self.log(f"{description} уже выполняется...", channel="system")
            return

        original_text = button.cget("text") if button else None
        if button:
            button.config(state=tk.DISABLED, text=f"{description}…")

        self._active_tasks.add(task_id)
        self._set_status(f"{description}…", busy=True)

        def run() -> None:
            try:
                worker()
            finally:
                def finish() -> None:
                    if button and original_text is not None:
                        button.config(state=tk.NORMAL, text=original_text)
                    self._active_tasks.discard(task_id)
                    if self._active_tasks:
                        self._set_status("Выполняется…", busy=True)
                    else:
                        self._set_status("Готово", busy=False)

                self.after(0, finish)

        threading.Thread(target=run, daemon=True).start()

    def _preinstall_ccxt_without_coincurve(self, pip_cmd: List[str]) -> None:
        if os.name != "nt" or sys.version_info < (3, 13):
            return
        try:
            self._stream_command(
                "Подготовка ccxt (без optional зависимостей)",
                pip_cmd + ["install", "--upgrade", "ccxt", "--no-deps"],
                channel="system",
            )
        except subprocess.CalledProcessError:
            self.log(
                "[Подготовка ccxt] Не удалось установить ccxt без дополнительных зависимостей. Продолжаем стандартную установку.",
                channel="system",
            )

    def _configure_git_upstream(self) -> None:
        try:
            branch_result = subprocess.run(
                ["git", "symbolic-ref", "--short", "HEAD"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            current_branch = branch_result.stdout.strip()
            if current_branch != "main":
                return
            tracking_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "main@{upstream}"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if tracking_result.returncode != 0:
                subprocess.run(
                    ["git", "branch", "--set-upstream-to=origin/main", "main"],
                    cwd=str(PROJECT_ROOT),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=True,
                )
                self.log("Ветка main теперь отслеживает origin/main.", channel="system")
        except subprocess.CalledProcessError:
            self.log("[git] Не удалось настроить upstream для ветки main.", channel="system")

    def _auto_align_main_with_remote(self) -> None:
        try:
            # Проверяем количество коммитов в локальной ветке
            remote_check = subprocess.run(
                ["git", "rev-parse", "--verify", "origin/main"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if remote_check.returncode != 0:
                return

            # Сбрасываем локальную ветку к origin/main
            reset_result = subprocess.run(
                ["git", "reset", "--hard", "origin/main"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if reset_result.returncode == 0:
                self.log("Локальная ветка main сброшена к origin/main.", channel="system")
            else:
                self.log(
                    f"[git] Не удалось сбросить ветку main: {reset_result.stderr.strip()}",
                    channel="system",
                )
        except subprocess.CalledProcessError:
            self.log("[git] Не удалось синхронизировать ветку main с origin/main.", channel="system")

    def _run_git_log_preview(self) -> None:
        try:
            commit_check = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            if commit_check.stdout.strip() == "0":
                self.log("[git log] Нет коммитов для отображения истории.", channel="system")
                return
            # Показываем новый и предыдущий коммит(c) c датами
            result = subprocess.run(
                ["git", "log", "-2", "--pretty=format:%h %cd %an%n    %s", "--graph", "--date=short"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            output = result.stdout.strip()
            if output:
                self.log_queue.put(("system", f"[git log] Последние коммиты:\n{output}"))
        except subprocess.CalledProcessError:
            self.log("[git log] Не удалось получить историю коммитов.", channel="system")

    def _ensure_utf8_console(self) -> None:
        if os.name != "nt":
            return
        try:
            subprocess.run(
                "chcp 65001",
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except Exception:
            pass
        for cmd in [
            ["git", "config", "--global", "core.quotepath", "off"],
            ["git", "config", "--global", "i18n.logOutputEncoding", "utf-8"],
        ]:
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
            except Exception:
                pass

    def _strip_example_header(self, config_path: Path) -> None:
        try:
            text = config_path.read_text(encoding="utf-8")
        except OSError:
            return

        stripped = text.lstrip()
        if stripped.startswith('"""'):
            start_index = text.find('"""')
            end_index = text.find('"""', start_index + 3)
            if end_index != -1:
                new_text = text[end_index + 3 :]
                # remove leading blank lines
                new_text = new_text.lstrip("\n")
                try:
                    config_path.write_text(new_text, encoding="utf-8")
                    self.log("Удалён пояснительный блок из app/config.py.", channel="system")
                except OSError as exc:
                    self.log(f"[config] Не удалось очистить заголовок config.py: {exc}", channel="system")

    def _prepare_requirements_file(self) -> str:
        base_path = PROJECT_ROOT / "requirements.txt"
        if os.name != "nt" or sys.version_info < (3, 13):
            return str(base_path)

        try:
            lines = base_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            self.log(f"Не удалось прочитать requirements.txt: {exc}", channel="system")
            return str(base_path)

        filtered = []
        ccxt_skipped = False
        for line in lines:
            stripped = line.strip()
            if stripped.lower().startswith("ccxt"):
                ccxt_skipped = True
                continue
            filtered.append(line)

        if not ccxt_skipped:
            return str(base_path)

        fd, temp_path = tempfile.mkstemp(prefix="requirements_filtered_", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            temp_file.write("\n".join(filtered) + "\n")
        self._temp_requirements_path = Path(temp_path)
        self.log(
            "Используем requirements без ccxt (уже установлен отдельно, чтобы избежать установки coincurve).",
            channel="system",
        )
        return temp_path

    def _cleanup_temp_requirements(self) -> None:
        if self._temp_requirements_path and self._temp_requirements_path.exists():
            try:
                self._temp_requirements_path.unlink()
            except OSError:
                pass
        self._temp_requirements_path = None


def _split_command(command: str) -> List[str]:
    if os.name == "nt" and command.startswith("py "):
        return command.split()
    if " " in command:
        return command.split()
    return [command]


def main() -> None:
    manager = InfoBotManager()
    try:
        manager.mainloop()
    finally:
        manager.stop_all_services()


if __name__ == "__main__":
    main()

