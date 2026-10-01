import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


APP_NAME = "自媒体一键分发"
APP_HOST = "127.0.0.1"
APP_PORT = 5409
APP_URL = f"http://{APP_HOST}:{APP_PORT}/"


def package_paths() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        package_root = Path(sys.executable).resolve().parent
        return package_root, package_root / "程序文件"
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root, repo_root


class Launcher:
    def __init__(self) -> None:
        self.package_root, self.program_dir = package_paths()
        self.backend = None
        self.log_handle = None
        self.closing = False

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("460x170")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.configure(bg="#f7f5f8")
        self._center_window()

        title = tk.Label(
            self.root,
            text=APP_NAME,
            font=("Microsoft YaHei UI", 17, "bold"),
            fg="#292638",
            bg="#f7f5f8",
        )
        title.pack(pady=(28, 10))

        self.status = tk.Label(
            self.root,
            text="正在启动，请稍候……",
            font=("Microsoft YaHei UI", 11),
            fg="#6d5dfc",
            bg="#f7f5f8",
        )
        self.status.pack()

        hint = tk.Label(
            self.root,
            text="点右上角 × 即可完全退出软件",
            font=("Microsoft YaHei UI", 9),
            fg="#8a94a6",
            bg="#f7f5f8",
        )
        hint.pack(pady=(12, 0))

    def _center_window(self) -> None:
        self.root.update_idletasks()
        width = 460
        height = 170
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def set_status(self, text: str, color: str = "#6d5dfc") -> None:
        if self.closing:
            return
        self.root.after(0, lambda: self.status.configure(text=text, fg=color))

    def start(self) -> None:
        threading.Thread(target=self._start_backend, daemon=True).start()
        self.root.mainloop()

    def _start_backend(self) -> None:
        runtime_python = self.program_dir / "runtime" / "python" / "python.exe"
        main_file = self.program_dir / "main.py"
        if not runtime_python.exists() or not main_file.exists():
            self._fatal("软件文件不完整，请重新解压完整安装包。")
            return

        self._stop_stale_backend()
        if self._port_in_use():
            self._fatal(f"端口 {APP_PORT} 已被其他程序占用，请关闭占用程序后重试。")
            return

        for folder in ("videoFile", "cookiesFile", "db", "logs", "avatars", ".starter"):
            (self.program_dir / folder).mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env.update({
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONPATH": os.pathsep.join([
                str(self.program_dir),
                str(self.program_dir / "uploader"),
                str(self.program_dir / "myUtils"),
                str(self.program_dir / "utils"),
            ]),
            "PLAYWRIGHT_BROWSERS_PATH": str(self.program_dir / "runtime" / "playwright-browsers"),
        })

        log_path = self.program_dir / "logs" / "launcher.log"
        self.log_handle = log_path.open("a", encoding="utf-8")
        creation_flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            self.backend = subprocess.Popen(
                [str(runtime_python), str(main_file)],
                cwd=str(self.program_dir),
                env=env,
                stdout=self.log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
            )
            (self.program_dir / ".starter" / "backend.pid").write_text(
                str(self.backend.pid),
                encoding="ascii",
            )
        except Exception as exc:
            self._fatal(f"启动失败：{exc}")
            return

        deadline = time.time() + 45
        while time.time() < deadline and not self.closing:
            if self.backend.poll() is not None:
                self._fatal("后台服务启动失败，详情请查看程序文件中的 logs/launcher.log。")
                return
            try:
                with urllib.request.urlopen(APP_URL, timeout=1) as response:
                    if response.status == 200:
                        self.set_status("软件运行中", "#20a464")
                        webbrowser.open(APP_URL, new=1)
                        return
            except Exception:
                time.sleep(0.35)

        if not self.closing:
            self._fatal("启动超时，详情请查看程序文件中的 logs/launcher.log。")

    def _fatal(self, message: str) -> None:
        self.set_status("启动失败", "#d84a55")
        self.root.after(0, lambda: messagebox.showerror(APP_NAME, message, parent=self.root))

    def _port_in_use(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex((APP_HOST, APP_PORT)) == 0

    def _stop_stale_backend(self) -> None:
        pid_file = self.program_dir / ".starter" / "backend.pid"
        if not pid_file.exists():
            return
        try:
            pid = int(pid_file.read_text(encoding="ascii").strip())
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=8,
                check=False,
            )
        except Exception:
            pass
        try:
            pid_file.unlink(missing_ok=True)
        except Exception:
            pass

    def close(self) -> None:
        if self.closing:
            return
        self.closing = True
        self.status.configure(text="正在退出……", fg="#7c8594")
        self.root.update_idletasks()

        if self.backend and self.backend.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(self.backend.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=10,
                    check=False,
                )
            except Exception:
                try:
                    self.backend.kill()
                except Exception:
                    pass

        try:
            (self.program_dir / ".starter" / "backend.pid").unlink(missing_ok=True)
        except Exception:
            pass
        if self.log_handle:
            try:
                self.log_handle.close()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    Launcher().start()
