from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
BACKEND_PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
ANON_URL = "http://127.0.0.1:5173/"
BACKEND_HEALTH = "http://127.0.0.1:8000/health"
OLLAMA_HEALTH = "http://127.0.0.1:11434/api/tags"
GITHUB_CREATOR_URL = "https://github.com/LukasFurtado"


def read_app_version() -> str:
    version_file = ROOT / "backend" / "app" / "version.py"
    try:
        namespace: dict[str, str] = {}
        exec(version_file.read_text(encoding="utf-8"), namespace)
        return str(namespace.get("APP_VERSION") or "2.0.0")
    except Exception:
        return "2.0.0"


def http_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


class AnonLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ANON - Painel Local")
        self.geometry("780x640")
        self.minsize(700, 600)
        self.configure(bg="#07111f")

        self.processes: dict[str, subprocess.Popen] = {}
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.opened_browser = False
        self.starting = False
        self.app_version = read_app_version()

        self._build_ui()
        self.after(300, self._drain_logs)
        self.after(500, self._refresh_footer_clock)
        self.after(900, self._refresh_status_loop)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg="#08223c", padx=22, pady=18)
        header.pack(fill="x")

        title = tk.Label(
            header,
            text="ANON",
            fg="#f6fbff",
            bg="#08223c",
            font=("Segoe UI", 26, "bold"),
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            header,
            text="Anonimizador institucional offline de arquivos",
            fg="#bcd6ee",
            bg="#08223c",
            font=("Segoe UI", 12),
        )
        subtitle.pack(anchor="w", pady=(2, 0))

        body = tk.Frame(self, bg="#07111f", padx=22, pady=18)
        body.pack(fill="both", expand=True)

        status_box = tk.Frame(body, bg="#0e1d32", padx=16, pady=14, highlightbackground="#1e4f7d", highlightthickness=1)
        status_box.pack(fill="x")

        self.backend_status = self._status_line(status_box, "Servidor local")
        self.frontend_status = self._status_line(status_box, "Painel visual")
        self.ollama_status = self._status_line(status_box, "Ollama / IA local")

        controls = tk.Frame(body, bg="#07111f", pady=16)
        controls.pack(fill="x")

        self.start_button = self._button(controls, "Iniciar ANON", self.start_anon, "#0f6ea8")
        self.start_button.pack(side="left", padx=(0, 10))

        self.open_button = self._button(controls, "Abrir Painel", self.open_panel, "#16425f")
        self.open_button.pack(side="left", padx=(0, 10))

        self.stop_button = self._button(controls, "Encerrar ANON", self.stop_anon, "#78402f")
        self.stop_button.pack(side="left")

        hint = tk.Label(
            body,
            text=(
                "Use esta janela como ponto unico de abertura. "
                "Ela inicia os servicos locais e abre o painel no navegador automaticamente."
            ),
            fg="#b9c9d8",
            bg="#07111f",
            justify="left",
            wraplength=690,
            font=("Segoe UI", 10),
        )
        hint.pack(anchor="w", pady=(2, 12))

        log_label = tk.Label(
            body,
            text="Registro local de inicializacao",
            fg="#f1c84c",
            bg="#07111f",
            font=("Segoe UI", 10, "bold"),
        )
        log_label.pack(anchor="w")

        self.log_text = tk.Text(
            body,
            height=9,
            bg="#050b14",
            fg="#dce8f3",
            insertbackground="#ffffff",
            relief="flat",
            padx=12,
            pady=10,
            font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", expand=True, pady=(6, 0))
        self.log_text.configure(state="disabled")

        self._build_footer(body)

    def _build_footer(self, parent: tk.Frame) -> None:
        footer = tk.Frame(
            parent,
            bg="#0e1d32",
            padx=14,
            pady=11,
            highlightbackground="#1e4f7d",
            highlightthickness=1,
        )
        footer.pack(fill="x", pady=(12, 0))

        top_line = tk.Frame(footer, bg="#0e1d32")
        top_line.pack(fill="x")

        self.footer_clock = tk.Label(
            top_line,
            text="",
            fg="#dce8f3",
            bg="#0e1d32",
            anchor="w",
            font=("Segoe UI", 9, "bold"),
        )
        self.footer_clock.pack(side="left", fill="x", expand=True)

        version = tk.Label(
            top_line,
            text=f"Versao {self.app_version}",
            fg="#f1c84c",
            bg="#0e1d32",
            anchor="e",
            font=("Segoe UI", 9, "bold"),
        )
        version.pack(side="right")

        credit_line = tk.Frame(footer, bg="#0e1d32")
        credit_line.pack(fill="x", pady=(6, 0))

        tk.Label(
            credit_line,
            text=f"Copyright {time.strftime('%Y')} ANON - Uso institucional e interno. Criador e Programador - ",
            fg="#a9c4dc",
            bg="#0e1d32",
            anchor="w",
            font=("Segoe UI", 9),
        ).pack(side="left")

        creator = tk.Label(
            credit_line,
            text="Lukas Furtado",
            fg="#67b7ff",
            bg="#0e1d32",
            cursor="hand2",
            font=("Segoe UI", 9, "bold underline"),
        )
        creator.pack(side="left")
        creator.bind("<Button-1>", lambda _event: webbrowser.open(GITHUB_CREATOR_URL))

    def _refresh_footer_clock(self) -> None:
        if hasattr(self, "footer_clock"):
            self.footer_clock.configure(text=f"Data e hora local: {time.strftime('%d/%m/%Y %H:%M:%S')}")
        self.after(1000, self._refresh_footer_clock)

    def _status_line(self, parent: tk.Frame, label: str) -> tk.Label:
        row = tk.Frame(parent, bg="#0e1d32")
        row.pack(fill="x", pady=4)
        tk.Label(
            row,
            text=label,
            width=18,
            anchor="w",
            fg="#a9c4dc",
            bg="#0e1d32",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        value = tk.Label(
            row,
            text="verificando...",
            anchor="w",
            fg="#f1c84c",
            bg="#0e1d32",
            font=("Segoe UI", 10),
        )
        value.pack(side="left", fill="x", expand=True)
        return value

    def _button(self, parent: tk.Frame, text: str, command, color: str) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg="#ffffff",
            activebackground="#1a85c4",
            activeforeground="#ffffff",
            relief="flat",
            padx=18,
            pady=10,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )

    def log(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_queue.put(f"[{stamp}] {text}\n")

    def _drain_logs(self) -> None:
        try:
            while True:
                line = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", line)
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(250, self._drain_logs)

    def _refresh_status_loop(self) -> None:
        threading.Thread(target=self._refresh_status, daemon=True).start()
        self.after(2500, self._refresh_status_loop)

    def _refresh_status(self) -> None:
        backend = http_ok(BACKEND_HEALTH)
        frontend = http_ok(ANON_URL)
        ollama = http_ok(OLLAMA_HEALTH)
        self._set_status(self.backend_status, "ativo" if backend else "aguardando", backend)
        self._set_status(self.frontend_status, "ativo" if frontend else "aguardando", frontend)
        self._set_status(self.ollama_status, "ativo" if ollama else "nao detectado", ollama)

    def _set_status(self, widget: tk.Label, text: str, ok: bool) -> None:
        color = "#5ce0a5" if ok else "#f1c84c"
        self.after(0, lambda: widget.configure(text=text, fg=color))

    def start_anon(self) -> None:
        if self.starting:
            self.log("Inicializacao ja esta em andamento.")
            return
        self.starting = True
        self.start_button.configure(state="disabled")
        threading.Thread(target=self._start_worker, daemon=True).start()

    def _start_worker(self) -> None:
        try:
            self.log("Preparando abertura do ANON.")
            self._ensure_ollama()
            self._ensure_backend()
            self._ensure_frontend()
            self._wait_and_open()
        finally:
            self.starting = False
            self.after(0, lambda: self.start_button.configure(state="normal"))

    def _ensure_ollama(self) -> None:
        if http_ok(OLLAMA_HEALTH):
            self.log("Ollama detectado.")
            return
        ollama = shutil.which("ollama")
        if not ollama:
            self.log("Ollama nao foi encontrado. Abra o Ollama antes de anonimizar.")
            return
        self.log("Iniciando Ollama local.")
        self._spawn("ollama", [ollama, "serve"], ROOT)
        for _ in range(20):
            if http_ok(OLLAMA_HEALTH):
                self.log("Ollama ativo.")
                return
            time.sleep(1)
        self.log("Ollama ainda nao respondeu. O painel pode abrir, mas a IA dependera dele.")

    def _ensure_backend(self) -> None:
        if http_ok(BACKEND_HEALTH):
            self.log("Servidor local ja esta ativo.")
            return

        if BACKEND_PYTHON.exists():
            cmd = [str(BACKEND_PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
        else:
            cmd = self._python_fallback() + ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]

        self.log("Iniciando servidor local.")
        self._spawn("backend", cmd, BACKEND)

    def _ensure_frontend(self) -> None:
        if http_ok(ANON_URL):
            self.log("Painel visual ja esta ativo.")
            return

        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm:
            self.log("Node.js/npm nao foi encontrado. Instale o Node.js para abrir o painel visual.")
            return

        self.log("Iniciando painel visual.")
        self._spawn("frontend", [npm, "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"], FRONTEND)

    def _python_fallback(self) -> list[str]:
        if shutil.which("py"):
            return ["py", "-3"]
        if shutil.which("python"):
            return ["python"]
        return [sys.executable]

    def _spawn(self, name: str, cmd: list[str], cwd: Path) -> None:
        if name in self.processes and self.processes[name].poll() is None:
            return

        flags = 0
        startupinfo = None
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        process = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
            startupinfo=startupinfo,
            env=env,
        )
        self.processes[name] = process
        threading.Thread(target=self._pipe_output, args=(name, process), daemon=True).start()

    def _pipe_output(self, name: str, process: subprocess.Popen) -> None:
        if not process.stdout:
            return
        for line in process.stdout:
            cleaned = line.strip()
            if cleaned:
                self.log(f"{name}: {cleaned}")

    def _wait_and_open(self) -> None:
        self.log("Aguardando painel ficar pronto.")
        for _ in range(90):
            if http_ok(BACKEND_HEALTH) and http_ok(ANON_URL):
                self.log("ANON pronto. Abrindo painel.")
                self.open_panel()
                return
            time.sleep(1)
        self.log("Nao foi possivel confirmar abertura automatica. Use o botao Abrir Painel.")

    def open_panel(self) -> None:
        webbrowser.open(ANON_URL)
        self.opened_browser = True

    def stop_anon(self) -> None:
        stopped = False
        for name, process in list(self.processes.items()):
            if process.poll() is None:
                self.log(f"Encerrando {name}.")
                try:
                    process.terminate()
                except Exception as exc:
                    self.log(f"Nao foi possivel encerrar {name}: {exc}")
                stopped = True
        if not stopped:
            self.log("Nenhum processo iniciado por esta janela esta ativo.")

    def _on_close(self) -> None:
        if any(process.poll() is None for process in self.processes.values()):
            if not messagebox.askyesno("Encerrar ANON", "Deseja encerrar os servicos iniciados por esta janela?"):
                return
            self.stop_anon()
        self.destroy()


if __name__ == "__main__":
    app = AnonLauncher()
    app.mainloop()
