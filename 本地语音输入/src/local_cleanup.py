"""Local llama.cpp text-only cleanup. No cloud, GPU, or transcript logging."""
from __future__ import annotations

import atexit
import ctypes
from dataclasses import dataclass
from difflib import SequenceMatcher
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request

from paths import APP_ROOT as ROOT, user_file

SETTINGS = user_file("cleanup_settings.json")


def load_enabled() -> bool:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8")).get("enabled", True) is not False
    except (OSError, ValueError, AttributeError):
        return True


def save_enabled(enabled: bool) -> None:
    try:
        SETTINGS.write_text(json.dumps({"enabled": bool(enabled)}), encoding="utf-8")
    except OSError:
        pass


@dataclass
class CleanupResult:
    text: str
    status: str
    seconds: float = 0.0


def is_safe_edit(original: str, edited: str) -> bool:
    """Reject obvious loss, hallucination, changed numbers/English/negation.

    This is a conservative guard, not a proof of semantic equivalence.
    """
    if not edited.strip() or len(edited) > len(original) * 1.2 + 12:
        return False
    if len(edited) < len(original) * 0.45:
        return False
    tokens = lambda s: set(re.findall(r"[A-Za-z][A-Za-z0-9_.+/-]*|\d+(?:\.\d+)?", s))
    if tokens(original) != tokens(edited):
        return False
    for char in "不没无别未":
        if original.count(char) != edited.count(char):
            return False
    if re.match(r"^嗯[，,\s]*(?:我同意|好的|对[，。！!]|是的)", original) and not edited.startswith("嗯"):
        return False
    compact = lambda s: re.sub(r"[\s，。！？、,.!?：:；;\"“”]", "", s)
    if SequenceMatcher(None, compact(original), compact(edited), autojunk=False).ratio() < 0.65:
        return False
    if any(mark in edited for mark in ("<think>", "</think>", "```")):
        return False
    return True


class LocalCleaner:
    def __init__(self):
        self.process = None
        self.lock = threading.Lock()
        self.closed = False
        self.token = secrets.token_urlsafe(24)
        self.base_url = ""
        # Do not send loopback requests through system HTTP proxies.
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.status = "未加载"
        atexit.register(self.close)

    def request(self, route, payload=None, timeout=2):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.base_url + route, data=data,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        with self.http.open(req, timeout=timeout) as response:
            return json.load(response)

    def start(self):
        with self.lock:
            if self.closed:
                raise RuntimeError("cleaner closed")
            if self.process and self.process.poll() is None:
                return
            executable = ROOT / "runtime" / "llama" / "llama-server.exe"
            model = ROOT / "models" / "cleanup" / "Qwen3.5-0.8B-Q4_0.gguf"
            if not executable.is_file() or not model.is_file():
                raise FileNotFoundError("本地整理引擎或模型缺失")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            self.base_url = f"http://127.0.0.1:{port}"
            env = os.environ.copy()
            # Frozen Qt/Python DLL paths must not contaminate the external engine.
            env.pop('QT_PLUGIN_PATH', None)
            env.pop('QT_QPA_PLATFORM_PLUGIN_PATH', None)
            env["LLAMA_API_KEY"] = self.token
            command = [
                str(executable), "-m", str(model), "--host", "127.0.0.1", "--port", str(port),
                "-c", "4096", "-t", "6", "-tb", "6", "-ngl", "0", "-np", "1",
                "--no-webui", "--reasoning", "off", "--chat-template-kwargs", '{"enable_thinking":false}',
            ]
            frozen = getattr(sys, 'frozen', False) and os.name == 'nt'
            if frozen:
                ctypes.windll.kernel32.SetDllDirectoryW(None)
            try:
                self.process = subprocess.Popen(command, cwd=str(executable.parent), env=env,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            finally:
                if frozen:
                    ctypes.windll.kernel32.SetDllDirectoryW(str(sys._MEIPASS))
            self.status = "加载中"

    def ready(self, timeout=25):
        self.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not self.closed:
            if self.process.poll() is not None:
                raise RuntimeError("本地整理引擎已退出")
            try:
                if self.request("/health").get("status") == "ok":
                    self.status = "就绪"
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
        raise TimeoutError("本地整理模型加载超时")

    def warm_up(self):
        def run():
            try:
                self.ready()
            except Exception:
                self.status = "不可用（仍可原始听写）"
        threading.Thread(target=run, daemon=True).start()

    def clean(self, text: str) -> CleanupResult:
        started = time.monotonic()
        if not text.strip() or len(text) > 1800:
            return CleanupResult(text, "跳过（空文本或长文本）")
        try:
            self.ready()
            prompt = (ROOT / "cleanup_prompt.txt").read_text(encoding="utf-8")
            result = self.request("/v1/chat/completions", {
                "messages": [{"role": "system", "content": prompt},
                             {"role": "user", "content": json.dumps({"transcript": text}, ensure_ascii=False)}],
                "temperature": 0, "max_tokens": min(2048, max(128, len(text) * 2 + 64)),
                "chat_template_kwargs": {"enable_thinking": False},
                "response_format": {"type": "json_object", "schema": {
                    "type": "object", "properties": {"text": {"type": "string"}},
                    "required": ["text"], "additionalProperties": False}},
            }, timeout=20)
            choice = result["choices"][0]
            edited = json.loads(choice["message"]["content"])["text"].strip()
            if choice.get("finish_reason") != "stop" or not is_safe_edit(text, edited):
                return CleanupResult(text, "保留原文（保护检查）", time.monotonic() - started)
            return CleanupResult(edited, "已整理", time.monotonic() - started)
        except Exception:
            self.status = "不可用（仍可原始听写）"
            return CleanupResult(text, "保留原文（整理失败）", time.monotonic() - started)

    def close(self):
        with self.lock:
            self.closed = True
            if self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
