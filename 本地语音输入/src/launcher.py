"""Product entry point: independent executable, diagnostics and single instance."""
import argparse
import ctypes
import io
import json
from pathlib import Path
import sys
import traceback

from paths import VERSION, user_file

_mutex = None


def self_test(report):
    import contextlib
    from app import self_test as test_asr, read_wav, OFFLINE
    from speech_gate import SpeechGate, RATE
    from local_cleanup import LocalCleaner
    from terminology import correct_terms
    import numpy as np

    checks = {}
    checks['terminology_repair'] = correct_terms('把源码上传到 get up，调用 a p i。') == '把源码上传到 GitHub，调用 API。'
    checks['ordinary_english_preserved'] = all(correct_terms(text) == text for text in ('I get up at 8.', '上传代码。I get up at 8.', '模型例句是 I get up at 8.'))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        checks['recognition'] = test_asr() == 0
    gate = SpeechGate()
    samples, _ = read_wav(OFFLINE / 'test.wav')
    checks['silence_rejected'] = len(gate.speech_audio(np.zeros(RATE * 2))) == 0
    checks['speech_accepted'] = len(gate.speech_audio(samples)) > 0
    cleaner = LocalCleaner()
    try:
        cleaned = cleaner.clean('嗯，呃，我我想试一下 Wispr Flow，不要换 sherpa-onnx。')
        checks['cleanup_engine'] = cleaned.status == '已整理'
        checks['english_and_negation_preserved'] = all(word in cleaned.text for word in ('Wispr Flow', '不要', 'sherpa-onnx'))
    finally:
        cleaner.close()
    result = {'version': VERSION, 'passed': all(checks.values()), 'checks': checks,
              'asr_sample_output': output.getvalue()}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if result['passed'] else 1


def main():
    global _mutex
    parser = argparse.ArgumentParser(description='本地语音输入 ' + VERSION)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.self_test:
        report = args.report or user_file('self-test.json')
        try:
            return self_test(report)
        except Exception:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps({'version': VERSION, 'passed': False,
                'error': traceback.format_exc()}, ensure_ascii=False, indent=2), encoding='utf-8')
            return 1
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    _mutex = kernel32.CreateMutexW(None, False, 'Local\\SherpaOnnxDictationTwoPass')
    if kernel32.GetLastError() == 183:
        # Repeated launch is a quiet no-op; never create duplicate mouse hooks.
        return 0
    try:
        from qt_ui import SmoothDictationApp
        SmoothDictationApp().run()
        return 0
    except Exception:
        log = user_file('startup-error.txt')
        log.write_text(traceback.format_exc(), encoding='utf-8')
        ctypes.windll.user32.MessageBoxW(None, '启动失败。诊断文件：\n' + str(log), '本地语音输入', 0x10)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
