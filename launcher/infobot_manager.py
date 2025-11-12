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

import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


class ManagedProcess:
    """Wraps a subprocess and streams its output to a Tkinter-safe queue."""

    def __init__(self, name: str, command: List[str], channel: str):
        self.name = name
        self.command = command
        self.channel = channel
        self.process: Optional[subprocess.Popen[str]] = None
        self._reader_thread: Optional[threading.Thread] = None

    def start(self, log_queue: "queue.Queue[Tuple[str, str]]") -> None:
        if self.is_running:
            raise RuntimeError(f"{self.name} already running")

        env = os.environ.copy()
        pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{PROJECT_ROOT}{os.pathsep}{pythonpath}" if pythonpath else str(PROJECT_ROOT)

        # On Windows we can optionally create a new console window.
        self.process = subprocess.Popen(
            self.command,
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
        )

        def _reader() -> None:
            assert self.process and self.process.stdout
            for line in self.process.stdout:
                message = f"[{self.name}] {line.rstrip()}"
                log_queue.put(("system", message))
                log_queue.put((self.channel, message))
            self.process.stdout.close()

        self._reader_thread = threading.Thread(target=_reader, daemon=True)
        self._reader_thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        if not self.process or self.process.poll() is not None:
            return

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

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def pid(self) -> Optional[int]:
        return self.process.pid if self.process else None


class InfoBotManager(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("InfoBot Manager")
        self.geometry("980x720")
        self.minsize(820, 600)

        self.log_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()
        self.processes: Dict[str, ManagedProcess] = {}
        self.log_text_widgets: Dict[str, tk.Text] = {}

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
        scrollable.bind(
            "<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        window_id = canvas.create_window((0, 0), window=scrollable, anchor="nw")

        def _resize_canvas(event: tk.Event) -> None:  # type: ignore[override]
            canvas.itemconfigure(window_id, width=event.width)

        canvas.bind("<Configure>", _resize_canvas)

        main = ttk.Frame(scrollable, padding=12)
        main.grid(row=0, column=0, sticky="nsew")

        scrollable.columnconfigure(0, weight=1)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(6, weight=1)

        self._enable_mousewheel(canvas)

        install_frame = ttk.LabelFrame(main, text="1. Установка зависимостей (обязательно)", padding=10)
        install_frame.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        install_frame.columnconfigure(0, weight=1)

        ttk.Button(
            install_frame,
            text="Установить/обновить зависимости (pip install -r requirements.txt)",
            command=self.install_dependencies_global,
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            install_frame,
            text="Открыть каталог проекта",
            command=lambda: self.open_path(PROJECT_ROOT),
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        venv_frame = ttk.LabelFrame(main, text="2. Виртуальное окружение (опционально)", padding=10)
        venv_frame.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        venv_frame.columnconfigure(1, weight=1)

        ttk.Label(venv_frame, text="Статус:").grid(row=0, column=0, sticky="w")
        ttk.Label(venv_frame, textvariable=self.env_status_var).grid(row=0, column=1, sticky="w")
        ttk.Button(
            venv_frame,
            text="Создать/обновить окружение (.venv)",
            command=self.install_dependencies,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(
            venv_frame,
            text="Удалить окружение (.venv)",
            command=self.delete_environment,
        ).grid(row=1, column=1, sticky="w", pady=(6, 0))

        git_frame = ttk.LabelFrame(main, text="3. Обновления из Git", padding=10)
        git_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=4)
        git_frame.columnconfigure(1, weight=1)

        ttk.Label(git_frame, text="Статус репозитория:").grid(row=0, column=0, sticky="w")
        ttk.Label(git_frame, textvariable=self.git_status_var).grid(row=0, column=1, sticky="w")

        ttk.Button(git_frame, text="Проверить обновления", command=self.check_for_updates).grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Button(git_frame, text="Обновить (git pull)", command=self.pull_updates).grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )

        license_frame = ttk.LabelFrame(main, text="4. Лицензия и ключи (опционально)", padding=10)
        license_frame.grid(row=3, column=0, sticky="ew", padx=4, pady=4)
        license_frame.columnconfigure(1, weight=1)

        ttk.Label(license_frame, text="Статус лицензии:").grid(row=0, column=0, sticky="w")
        ttk.Label(license_frame, textvariable=self.license_status_var).grid(row=0, column=1, sticky="w")

        ttk.Button(license_frame, text="Получить Hardware ID", command=self.run_license_activation).grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        ttk.Button(license_frame, text="Импортировать .lic файл", command=self.import_license_file).grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )
        ttk.Button(
            license_frame,
            text="Как настроить ключи?",
            command=lambda: self.open_path(PROJECT_ROOT / "docs" / "INSTALL.md"),
        ).grid(row=1, column=2, sticky="w", pady=(6, 0))

        services_frame = ttk.LabelFrame(main, text="5. Запуск сервисов", padding=10)
        services_frame.grid(row=4, column=0, sticky="ew", padx=4, pady=4)
        services_frame.columnconfigure(1, weight=1)

        ttk.Button(services_frame, text="Остановить все", command=self.stop_all_services).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        for idx, (service_id, meta) in enumerate(self._services().items(), start=1):
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
        docs_frame.grid(row=5, column=0, sticky="ew", padx=4, pady=4)
        docs_frame.columnconfigure(0, weight=1)

        ttk.Button(docs_frame, text="Открыть README", command=lambda: self.open_path(PROJECT_ROOT / "README.md")).pack(
            anchor="w"
        )
        ttk.Button(
            docs_frame,
            text="Открыть лог ботов",
            command=lambda: self.open_path(PROJECT_ROOT / "logs" / "bots.log"),
        ).pack(anchor="w", pady=(4, 0))
        ttk.Button(
            docs_frame,
            text="Редактировать конфиг (app/config.py)",
            command=lambda: self.open_path(PROJECT_ROOT / "app" / "config.py"),
        ).pack(anchor="w", pady=(4, 0))
        ttk.Button(
            docs_frame,
            text="Редактировать ключи (app/keys.py)",
            command=lambda: self.open_path(PROJECT_ROOT / "app" / "keys.py"),
        ).pack(anchor="w", pady=(4, 0))

        log_frame = ttk.LabelFrame(main, text="7. Логи и вывод команд", padding=10)
        log_frame.grid(row=6, column=0, sticky="nsew", padx=4, pady=4)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(log_frame)
        notebook.grid(row=0, column=0, sticky="nsew")

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

            text_widget = tk.Text(tab, wrap="word", height=12, state=tk.DISABLED)
            text_widget.grid(row=0, column=0, sticky="nsew")
            scrollbar = ttk.Scrollbar(tab, command=text_widget.yview)
            scrollbar.grid(row=0, column=1, sticky="ns")
            text_widget["yscrollcommand"] = scrollbar.set
            self.log_text_widgets[channel] = text_widget

    def _enable_mousewheel(self, widget: tk.Widget) -> None:
        if sys.platform == "darwin":
            widget.bind_all("<MouseWheel>", lambda event: widget.yview_scroll(int(-event.delta), "units"))
            widget.bind_all("<Button-4>", lambda event: widget.yview_scroll(-1, "units"))
            widget.bind_all("<Button-5>", lambda event: widget.yview_scroll(1, "units"))
        else:
            widget.bind_all("<MouseWheel>", lambda event: widget.yview_scroll(int(-event.delta / 120), "units"))
            widget.bind_all("<Button-4>", lambda event: widget.yview_scroll(-1, "units"))
            widget.bind_all("<Button-5>", lambda event: widget.yview_scroll(1, "units"))

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
                "title": "AI Engine (ai.py)",
                "command": python + ["ai.py"],
            },
        }

    def update_environment_status(self) -> None:
        if VENV_DIR.exists():
            python = "python.exe" if os.name == "nt" else "python"
            self.env_status_var.set(f".venv найден (используется {python})")
        else:
            self.env_status_var.set("Виртуальное окружение не создано (используется системный Python)")

    def ensure_git_repository(self) -> None:
        git_dir = PROJECT_ROOT / ".git"
        if git_dir.exists():
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
                check=True,
            )
            if init_result.stdout.strip():
                self.log(init_result.stdout.strip())
            remote_result = subprocess.run(
                ["git", "remote", "add", "origin", DEFAULT_REMOTE_URL],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                check=True,
            )
            if remote_result.stdout.strip():
                self.log(remote_result.stdout.strip())
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
            self.log_queue.put(("system", message))
        self.log_queue.put((channel, message))

    def log(self, message: str, channel: str = "system", broadcast: bool = True) -> None:
        timestamp = time.strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self._enqueue_log(channel, formatted, broadcast=broadcast)

    def _flush_logs(self) -> None:
        while True:
            try:
                channel, line = self.log_queue.get_nowait()
            except queue.Empty:
                break
            widget = self.log_text_widgets.get(channel) or self.log_text_widgets.get("system")
            if widget is None:
                continue
            widget.configure(state=tk.NORMAL)
            widget.insert(tk.END, line + "\n")
            widget.see(tk.END)
            widget.configure(state=tk.DISABLED)
        self.after(200, self._flush_logs)

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
            )
        except FileNotFoundError:
            self.log(f"[{title}] Команда не найдена: {command[0]}", channel=channel)
            return

        assert proc.stdout
        for line in proc.stdout:
            self._enqueue_log(channel, f"[{title}] {line.rstrip()}")
        return_code = proc.wait()
        self.log(f"[{title}] Завершено (код {return_code})", channel=channel)
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, command)

    def install_dependencies(self) -> None:
        def worker() -> None:
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
            commands = [
                ("Обновление pip", pip_cmd + ["install", "--upgrade", "pip", "setuptools", "wheel"]),
                ("Установка зависимостей", pip_cmd + ["install", "-r", "requirements.txt"]),
            ]
            for title, command in commands:
                try:
                    self._stream_command(title, command, channel="system")
                except subprocess.CalledProcessError as exc:
                    self.log(f"[{title}] Ошибка установки ({exc.returncode})", channel="system")
                    return
            self.update_environment_status()
            PYTHON_EXECUTABLE = _detect_python_executable()

        threading.Thread(target=worker, daemon=True).start()

    def install_dependencies_global(self) -> None:
        def worker() -> None:
            python_cmd = _split_command(sys.executable) + ["-m", "pip", "install", "-r", "requirements.txt"]
            try:
                self._stream_command("Установка зависимостей (глобально)", python_cmd, channel="system")
                self.log("Глобальная установка зависимостей завершена.", channel="system")
            except subprocess.CalledProcessError as exc:
                self.log(
                    f"[Установка зависимостей (глобально)] Ошибка ({exc.returncode}). Убедитесь, что есть права и активный pip.",
                    channel="system",
                )

        threading.Thread(target=worker, daemon=True).start()

    def delete_environment(self) -> None:
        if not VENV_DIR.exists():
            messagebox.showinfo("Информация", "Виртуальное окружение (.venv) отсутствует.")
            return
        if messagebox.askyesno(
            "Удалить .venv",
            "Удалить виртуальное окружение (.venv)? Все запущенные сервисы будут остановлены.",
        ):
            self.stop_all_services()
            try:
                shutil.rmtree(VENV_DIR)
                self.log("Виртуальное окружение (.venv) удалено.", channel="system")
                self.update_environment_status()
                global PYTHON_EXECUTABLE
                PYTHON_EXECUTABLE = _detect_python_executable()
            except OSError as exc:
                messagebox.showerror(
                    "Ошибка удаления",
                    f"{exc}\n\nЕсли проблема сохраняется, закройте менеджер и удалите папку .venv вручную.",
                )

    def check_for_updates(self) -> None:
        if not shutil.which("git"):
            messagebox.showwarning("Git не найден", "Для проверки обновлений необходимо установить Git.")
            return

        def worker() -> None:
            try:
                self._stream_command("git fetch", ["git", "fetch", "--all", "--prune"])
                self._stream_command("git status", ["git", "status", "-sb"])
                self._stream_command("git log", ["git", "log", "-5", "--oneline", "--decorate", "--graph"])
            except subprocess.CalledProcessError:
                pass
            self.update_git_status()

        threading.Thread(target=worker, daemon=True).start()

    def pull_updates(self) -> None:
        if not shutil.which("git"):
            messagebox.showwarning("Git не найден", "Для обновления необходимо установить Git.")
            return

        def worker() -> None:
            try:
                self._stream_command("git pull", ["git", "pull", "--ff-only"])
            except subprocess.CalledProcessError:
                pass
            self.update_git_status()

        threading.Thread(target=worker, daemon=True).start()

    def run_license_activation(self) -> None:
        python_cmd = _split_command(PYTHON_EXECUTABLE)
        command = python_cmd + ["scripts/activate_premium.py"]

        def worker() -> None:
            try:
                self._stream_command("license", command)
            except subprocess.CalledProcessError:
                pass
            self.update_license_status()

        threading.Thread(target=worker, daemon=True).start()

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

    def stop_all_services(self) -> None:
        for service_id in list(self.processes.keys()):
            self.stop_service(service_id)

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

