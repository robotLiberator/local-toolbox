from __future__ import annotations



import ctypes


import json



import os


import queue


import sys


import threading


import time


import wave


from pathlib import Path


import numpy as np



import sherpa_onnx


import sounddevice as sd


from pynput import keyboard


from text_cleanup import clean_stutters


from local_cleanup import save_enabled
from terminology import correct_terms



from paths import APP_ROOT as ROOT


STREAMING = ROOT / "models" / "streaming"


OFFLINE = ROOT / "models" / "offline"


PUNCTUATION = ROOT / "models" / "punctuation"


SAMPLE_RATE = 16_000


HOTKEY = "<ctrl>+<alt>+<space>"


_INSTANCE_MUTEX = None


class RecordingSession:
    """Own the audio and cancellation state of exactly one recording."""
    def __init__(self, audio_queue, smart_cleanup, terminology):
        self.audio_queue = audio_queue
        self.smart_cleanup = smart_cleanup
        self.terminology = terminology
        self.cancelled = threading.Event()


def build_recognizers() -> tuple[
    sherpa_onnx.OnlineRecognizer,
    sherpa_onnx.OfflineRecognizer,
    sherpa_onnx.OfflinePunctuation,
]:
    required = [
        STREAMING / "tokens.txt",
        STREAMING / "encoder.int8.onnx",
        STREAMING / "decoder.int8.onnx",
        STREAMING / "joiner.int8.onnx",
        OFFLINE / "tokens.txt",
        OFFLINE / "model.int8.onnx",
        PUNCTUATION / "model.int8.onnx",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise FileNotFoundError("缺少模型文件：\n" + "\n".join(missing))

    online = sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=str(STREAMING / "tokens.txt"),
        encoder=str(STREAMING / "encoder.int8.onnx"),
        decoder=str(STREAMING / "decoder.int8.onnx"),
        joiner=str(STREAMING / "joiner.int8.onnx"),
        num_threads=4,
        sample_rate=SAMPLE_RATE,
        feature_dim=80,
        decoding_method="greedy_search",
        provider="cpu",
    )
    offline = sherpa_onnx.OfflineRecognizer.from_paraformer(
        paraformer=str(OFFLINE / "model.int8.onnx"),
        tokens=str(OFFLINE / "tokens.txt"),
        num_threads=6,
        sample_rate=SAMPLE_RATE,
        feature_dim=80,
        decoding_method="greedy_search",
        provider="cpu",
    )
    punctuation_config = sherpa_onnx.OfflinePunctuationConfig(
        model=sherpa_onnx.OfflinePunctuationModelConfig(
            ct_transformer=str(PUNCTUATION / "model.int8.onnx"),
            num_threads=2,
            provider="cpu",
        )
    )
    punctuation = sherpa_onnx.OfflinePunctuation(punctuation_config)
    return online, offline, punctuation


class DictationApp:
    """Shared recognition, drag, hotkey and input controller; UI lives in qt_ui."""

    def work_area(self) -> tuple[int, int, int, int]:
        class Rect(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        rect = Rect()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
        return rect.left, rect.top, rect.right, rect.bottom


    def load_position(self) -> tuple[int, int]:
        left, top, right, bottom = self.work_area()
        fallback = (right - 82, bottom - 82)
        try:
            saved = json.loads(self.position_path.read_text(encoding="utf-8"))
            x, y = int(saved["x"]), int(saved["y"])
            return self.clamp_bubble(x, y)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return fallback


    def save_position(self) -> None:
        try:
            self.position_path.write_text(
                json.dumps({"x": self.bubble_x, "y": self.bubble_y}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass


    def clamp_bubble(self, x: int, y: int) -> tuple[int, int]:
        left, top, right, bottom = self.work_area()
        return max(left, min(x, right - 64)), max(top, min(y, bottom - 64))


    def bubble_hit(self, x: int, y: int) -> bool:
        x -= self.bubble_ox
        y -= self.bubble_oy
        return 0 <= x <= 64 and 0 <= y <= 64


    def on_press(self, event: object) -> None:
        if not self.bubble_hit(event.x, event.y):
            self.press_info = None
            return
        self.press_info = (event.x_root, event.y_root, self.bubble_x, self.bubble_y)
        self.dragging = False


    def on_drag(self, event: object) -> None:
        if self.press_info is None:
            return
        start_x, start_y, bubble_x, bubble_y = self.press_info
        dx, dy = event.x_root - start_x, event.y_root - start_y
        if not self.dragging and dx * dx + dy * dy < 25:
            return
        self.dragging = True
        self.bubble_x, self.bubble_y = self.clamp_bubble(bubble_x + dx, bubble_y + dy)
        self.place_widget()


    def on_release(self, event: object) -> None:
        if self.dragging:
            self.save_position()
            self.press_info = None
            self.dragging = False
            return
        was_bubble = self.press_info is not None
        self.press_info = None
        if was_bubble:
            self.toggle()
            return
        if self.expanded:
            if self.close_bounds[0] <= event.x <= self.close_bounds[2] and self.close_bounds[1] <= event.y <= self.close_bounds[3]:
                self.collapse()
            elif self.copy_bounds[0] <= event.x <= self.copy_bounds[2] and self.copy_bounds[1] <= event.y <= self.copy_bounds[3]:
                self.copy_result()
            return


    def start_mouse_hook(self) -> None:
        from ctypes import wintypes

        class Point(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class MouseHookData(ctypes.Structure):
            _fields_ = [
                ("pt", Point),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", wintypes.WPARAM),
            ]

        result_type = ctypes.c_ssize_t
        callback_type = ctypes.WINFUNCTYPE(result_type, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, callback_type, ctypes.c_void_p, wintypes.DWORD]
        user32.CallNextHookEx.restype = result_type
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]

        def hook_proc(code: int, message: int, data_ptr: int) -> int:
            if code >= 0 and message in (0x020B, 0x020C):
                data = ctypes.cast(data_ptr, ctypes.POINTER(MouseHookData)).contents
                button = (data.mouseData >> 16) & 0xFFFF
                if button == 2:
                    if message == 0x020B:
                        self.events.put(("toggle", None))
                    return 1
            return user32.CallNextHookEx(self.mouse_hook, code, message, data_ptr)

        self.mouse_hook_callback = callback_type(hook_proc)

        def hook_loop() -> None:
            self.mouse_hook_thread_id = kernel32.GetCurrentThreadId()
            self.mouse_hook = user32.SetWindowsHookExW(
                14, self.mouse_hook_callback, kernel32.GetModuleHandleW(None), 0
            )
            if not self.mouse_hook:
                self.events.put(("hook_error", int(kernel32.GetLastError())))
                return
            self.events.put(("hook_ready", None))
            message = wintypes.MSG()
            while self.mouse_hook and user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))

        threading.Thread(target=hook_loop, daemon=True, name="XButton2Hook").start()


    def track_external_window(self) -> None:
        user32 = ctypes.windll.user32
        hwnd = int(user32.GetForegroundWindow())
        if hwnd:
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value != os.getpid():
                self.last_external_window = hwnd
        self.root.after(100, self.track_external_window)


    def toggle(self) -> None:
        if self.processing:
            return
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()


    def start_recording(self) -> None:
        self.smart_cleanup_for_recording = self.smart_cleanup.get()
        self.terminology_for_recording = self.terminology_enabled.get()
        self.target_window = self.last_external_window
        self.collapse()
        self.recording = True
        self.root.title("本地语音输入 - 录音中")
        self.audio_queue = queue.Queue()
        session = RecordingSession(self.audio_queue, self.smart_cleanup_for_recording,
                                   self.terminology_for_recording)
        self.session = session
        self.show_waveform()
        try:
            self.input_stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=1600,
                callback=self.audio_callback,
            )
            self.input_stream.start()
        except Exception as exc:
            self.recording = False
            self.show_text(f"无法打开麦克风：{exc}")
            return
        threading.Thread(target=self.recognition_worker, args=(session,), daemon=True).start()

    def request_cancel(self):
        session = getattr(self, "session", None)
        if session is None or not (self.recording or self.processing):
            return False
        # Invalidate pending results before the UI drains them.
        session.cancelled.set()
        self.events.put(("cancel", session))
        return True

    def cancel_recording(self, session=None):
        current = getattr(self, "session", None)
        if current is None or (session is not None and session is not current):
            return
        if not (self.recording or self.processing):
            return
        current.cancelled.set()
        self.recording = self.processing = False
        if self.input_stream is not None:
            self.input_stream.stop()
            self.input_stream.close()
            self.input_stream = None
        current.audio_queue.put(None)
        self.wave_target = self.wave_level = 0.0
        self.root.title("本地语音输入 - 已取消")
        self.collapse()


    def stop_recording(self) -> None:
        self.recording = False
        self.processing = True
        self.root.title("本地语音输入 - 识别中")
        if self.input_stream is not None:
            self.input_stream.stop()
            self.input_stream.close()
            self.input_stream = None
        self.audio_queue.put(None)


    def audio_callback(self, indata: np.ndarray, frames: int, time_info: object, status: object) -> None:
        if status:
            self.events.put(("status", f"音频提示：{status}"))
        if self.recording:
            samples = indata[:, 0].copy()
            self.audio_queue.put(samples)
            rms = float(np.sqrt(np.mean(np.square(samples))))
            self.events.put(("level", min(1.0, rms * 18.0)))


    def recognition_worker(self, session=None) -> None:
        if session is None:
            self._recognize_session(None)
            return
        # ONNX/VAD/cleanup objects are shared. A cancelled native call can finish
        # in the background, but must not run concurrently with the next round.
        with self.recognition_lock:
            if not session.cancelled.is_set():
                self._recognize_session(session)

    def _recognize_session(self, session) -> None:
        audio_queue = session.audio_queue if session else self.audio_queue
        smart_cleanup = session.smart_cleanup if session else self.smart_cleanup_for_recording
        terminology = session.terminology if session else self.terminology_for_recording
        def cancelled():
            return session is not None and session.cancelled.is_set()
        def emit(kind, payload):
            if not cancelled():
                self.events.put((kind, payload, session) if session else (kind, payload))
        stream = self.online.create_stream()
        chunks: list[np.ndarray] = []
        last_partial = ""
        try:
            while True:
                chunk = audio_queue.get()
                if cancelled():
                    return
                if chunk is None:
                    break
                chunks.append(chunk)
                stream.accept_waveform(SAMPLE_RATE, chunk)
                while self.online.is_ready(stream):
                    self.online.decode_stream(stream)
                partial = self.online.get_result(stream).strip()
                if partial and partial != last_partial:
                    last_partial = partial

            if not chunks:
                emit("final", "")
                return

            samples = np.concatenate(chunks)
            if len(samples) < SAMPLE_RATE // 4:
                emit("final", "")
                return
            samples = self.speech_gate.speech_audio(samples)
            if cancelled():
                return
            if not len(samples):
                emit("final", "")
                return
            second_pass = self.offline.create_stream()
            second_pass.accept_waveform(SAMPLE_RATE, samples)
            self.offline.decode_stream(second_pass)
            if cancelled():
                return
            final_text = second_pass.result.text.strip()
            if final_text:
                final_text = self.punctuation.add_punctuation(final_text).strip()
            # A speculative streaming hypothesis is not a valid final result.
            # Never fall back to it when the final recognizer returns empty.
            raw_text = final_text
            if not raw_text:
                emit("final", "")
                return
            corrected = correct_terms(raw_text) if terminology else raw_text
            term_status = "；已修正术语" if corrected != raw_text else ""
            if cancelled():
                return
            if smart_cleanup and raw_text:
                cleaned = self.cleaner.clean(corrected)
                emit("transcript", (raw_text, cleaned.text, cleaned.status + term_status))
            else:
                emit("transcript", (raw_text, corrected, "未开启整理" + term_status))
        except Exception as exc:
            emit("error", str(exc))


    def show_waveform(self) -> None:
        self.wave_target = 0.0
        self.wave_level = 0.0
        self.draw_widget()


    def animate_waveform(self) -> None:
        if self.recording:
            self.wave_level += (self.wave_target-self.wave_level)*0.45
            self.wave_target *= 0.85
        if self.recording or self.processing or self.expanded:
            self.draw_widget()
        self.root.after(60 if self.recording or self.processing else 200, self.animate_waveform)


    def finish(self, value: str) -> None:
        self.processing = False
        self.root.title("本地语音输入 - 已完成")
        if not value:
            self.wave_target = self.wave_level = 0.0
            self.root.title("本地语音输入 - 未检测到有效语音")
            self.collapse()
            return
        if self.cleanup_stutters.get():
            value = clean_stutters(value)
        self.last_result = value
        self.show_text(value)
        if self.auto_paste.get():
            self.paste_to_target(value)


    def finish_transcript(self, payload) -> None:
        self.last_raw_result, value, self.cleanup_status = payload
        self.finish(value)
        self.last_cleaned_result = self.last_result
        self.root.title("本地语音输入 - " + self.cleanup_status)


    def cleanup_changed(self) -> None:
        enabled = self.smart_cleanup.get()
        save_enabled(enabled)
        if enabled:
            self.cleaner.warm_up()


    def show_raw_result(self) -> None:
        if self.last_raw_result and not self.recording and not self.processing:
            self.show_text(self.last_raw_result)


    def show_cleaned_result(self) -> None:
        if self.last_cleaned_result and not self.recording and not self.processing:
            self.show_text(self.last_cleaned_result)
        else:
            self.expand()


    def paste_to_target(self, value: str) -> None:
        if not self.target_window or not ctypes.windll.user32.IsWindow(self.target_window):
            return
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow(self.target_window)
        time.sleep(0.12)

        from ctypes import wintypes

        ulong_ptr = wintypes.WPARAM

        class KeyboardInput(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ulong_ptr),
            ]

        class MouseInput(ctypes.Structure):
            _fields_ = [
                ("dx", wintypes.LONG),
                ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ulong_ptr),
            ]

        class HardwareInput(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

        class InputUnion(ctypes.Union):
            _fields_ = [("mi", MouseInput), ("ki", KeyboardInput), ("hi", HardwareInput)]

        class Input(ctypes.Structure):
            _anonymous_ = ("union",)
            _fields_ = [("type", wintypes.DWORD), ("union", InputUnion)]

        utf16 = value.encode("utf-16-le")
        code_units = [int.from_bytes(utf16[i : i + 2], "little") for i in range(0, len(utf16), 2)]
        events = (Input * (len(code_units) * 2))()
        for index, code_unit in enumerate(code_units):
            events[index * 2].type = 1
            events[index * 2].ki = KeyboardInput(0, code_unit, 0x0004, 0, 0)
            events[index * 2 + 1].type = 1
            events[index * 2 + 1].ki = KeyboardInput(0, code_unit, 0x0004 | 0x0002, 0, 0)
        sent = user32.SendInput(len(events), events, ctypes.sizeof(Input))
        if sent != len(events):
            return


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as f:
        if f.getnchannels() != 1 or f.getsampwidth() != 2:
            raise ValueError("自检音频必须是单声道 16-bit WAV")
        rate = f.getframerate()
        data = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    return data, rate


def self_test() -> int:
    started = time.perf_counter()
    online, offline, punctuation = build_recognizers()
    load_seconds = time.perf_counter() - started
    samples, rate = read_wav(OFFLINE / "test.wav")

    stream = online.create_stream()
    for pos in range(0, len(samples), 1600):
        stream.accept_waveform(rate, samples[pos : pos + 1600])
        while online.is_ready(stream):
            online.decode_stream(stream)
    stream.input_finished()
    while online.is_ready(stream):
        online.decode_stream(stream)
    first_pass = online.get_result(stream)

    stream2 = offline.create_stream()
    stream2.accept_waveform(rate, samples)
    decode_started = time.perf_counter()
    offline.decode_stream(stream2)
    decode_seconds = time.perf_counter() - decode_started
    raw_text = stream2.result.text
    final_text = punctuation.add_punctuation(raw_text)
    print(f"模型加载：{load_seconds:.2f} 秒")
    print("第一遍：" + first_pass)
    print("第二遍：" + final_text)
    print(f"二次修正：{decode_seconds:.3f} 秒；音频：{len(samples) / rate:.2f} 秒")
    return 0 if final_text else 1


