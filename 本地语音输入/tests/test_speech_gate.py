import queue
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np

from app import DictationApp, OFFLINE, read_wav
from speech_gate import RATE, SpeechGate
from local_cleanup import CleanupResult


class SpeechGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gate = SpeechGate()
        cls.speech, rate = read_wav(OFFLINE / 'test.wav')
        assert rate == RATE

    def test_silence_noise_and_offset(self):
        rng = np.random.default_rng(123)
        for data in (np.zeros(RATE * 5), np.ones(RATE * 3) * 0.02,
                     rng.normal(0, 0.003, RATE * 5), np.empty(0),
                     np.full(RATE, np.nan)):
            self.assertEqual(len(self.gate.speech_audio(data)), 0)

    def test_real_and_quiet_speech_and_reset(self):
        for scale in (1, 0.1):
            self.assertGreater(len(self.gate.speech_audio(self.speech * scale)), RATE // 5)
            self.assertEqual(len(self.gate.speech_audio(np.zeros(RATE * 2))), 0)

    def test_trim_surrounding_silence(self):
        padded = np.concatenate((np.zeros(RATE * 3), self.speech, np.zeros(RATE * 3)))
        trimmed = self.gate.speech_audio(padded)
        self.assertGreater(len(trimmed), RATE)
        self.assertLess(len(trimmed), len(padded) - RATE * 4)

    def make_worker(self, samples):
        app = DictationApp.__new__(DictationApp)
        stream = SimpleNamespace(accept_waveform=Mock())
        app.online = Mock()
        app.online.create_stream.return_value = stream
        app.online.is_ready.return_value = False
        app.online.get_result.return_value = '静音上猜出来的乱七八糟文字'
        app.offline = Mock()
        app.punctuation = Mock()
        app.cleaner = Mock()
        app.smart_cleanup_for_recording = True
        app.terminology_for_recording = True
        app.speech_gate = self.gate
        app.audio_queue = queue.Queue()
        app.audio_queue.put(samples)
        app.audio_queue.put(None)
        app.events = queue.Queue()
        return app

    def test_silence_skips_final_asr_and_cleanup(self):
        app = self.make_worker(np.zeros(RATE * 3, dtype=np.float32))
        app.recognition_worker()
        self.assertEqual(app.events.get_nowait(), ('final', ''))
        self.assertTrue(app.events.empty())
        app.offline.create_stream.assert_not_called()
        app.cleaner.clean.assert_not_called()

    def test_empty_final_never_uses_streaming_guess(self):
        app = self.make_worker(self.speech)
        app.offline.create_stream.return_value = SimpleNamespace(
            accept_waveform=Mock(), result=SimpleNamespace(text=''))
        app.recognition_worker()
        self.assertEqual(app.events.get_nowait(), ('final', ''))
        app.cleaner.clean.assert_not_called()

    def test_empty_result_does_not_type_or_show_text(self):
        app = DictationApp.__new__(DictationApp)
        app.root = SimpleNamespace(title=Mock())
        app.collapse = Mock()
        app.show_text = Mock()
        app.paste_to_target = Mock()
        app.last_result = '上一条有效结果'
        app.processing = True
        app.finish('')
        self.assertFalse(app.processing)
        app.collapse.assert_called_once()
        app.show_text.assert_not_called()
        app.paste_to_target.assert_not_called()
        self.assertEqual(app.last_result, '上一条有效结果')

    def term_worker(self, smart=True, terms=True):
        app = self.make_worker(self.speech)
        app.smart_cleanup_for_recording = smart
        app.terminology_for_recording = terms
        app.offline.create_stream.return_value = SimpleNamespace(
            accept_waveform=Mock(), result=SimpleNamespace(text='把代码上传到 get up。'))
        app.punctuation.add_punctuation.side_effect = lambda text: text
        app.cleaner.clean.side_effect = lambda text: CleanupResult(text, '已整理')
        return app

    def test_terms_before_cleanup_original_preserved(self):
        app = self.term_worker()
        app.recognition_worker()
        app.cleaner.clean.assert_called_once_with('把代码上传到 GitHub。')
        kind, (raw, final, status) = app.events.get_nowait()
        self.assertEqual(kind, 'transcript')
        self.assertEqual(raw, '把代码上传到 get up。')
        self.assertEqual(final, '把代码上传到 GitHub。')
        self.assertIn('已修正术语', status)

    def test_terms_work_without_smart_cleanup(self):
        app = self.term_worker(smart=False)
        app.recognition_worker()
        self.assertEqual(app.events.get_nowait()[1][1], '把代码上传到 GitHub。')
        app.cleaner.clean.assert_not_called()

    def test_terms_can_be_disabled(self):
        app = self.term_worker(terms=False)
        app.recognition_worker()
        app.cleaner.clean.assert_called_once_with('把代码上传到 get up。')
        self.assertEqual(app.events.get_nowait()[1][1], '把代码上传到 get up。')


if __name__ == '__main__':
    unittest.main()
