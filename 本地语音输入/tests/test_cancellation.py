import queue
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np
from app import DictationApp, RecordingSession
from qt_ui import SmoothDictationApp, Surface, Qt


class CancellationTests(unittest.TestCase):
    def make_app(self):
        app = DictationApp.__new__(DictationApp)
        app.events = queue.Queue()
        app.session = RecordingSession(queue.Queue(), True, True)
        app.recognition_lock = threading.Lock()
        app.recording, app.processing = True, False
        app.input_stream = Mock()
        app.root = SimpleNamespace(title=Mock(), after=Mock())
        app.collapse = Mock()
        app.last_result = '保留的上一条'
        app.paste_to_target = Mock()
        app.show_text = Mock()
        app.drain_events = Mock()
        return app

    def test_cancel_recording_preserves_result_and_stops_microphone(self):
        app = self.make_app()
        microphone = app.input_stream
        app.cancel_recording()
        self.assertTrue(app.session.cancelled.is_set())
        self.assertFalse(app.recording or app.processing)
        microphone.stop.assert_called_once()
        microphone.close.assert_called_once()
        self.assertIsNone(app.session.audio_queue.get_nowait())
        self.assertEqual(app.last_result, '保留的上一条')
        app.paste_to_target.assert_not_called()
        app.show_text.assert_not_called()

    def test_cancel_processing_drops_already_queued_result(self):
        app = self.make_app()
        app.recording, app.processing = False, True
        app.events.put(('transcript', ('原文', '不该输入', '已整理'), app.session))
        app.finish_transcript = Mock()
        self.assertTrue(app.request_cancel())
        SmoothDictationApp.drain_events(app)
        app.finish_transcript.assert_not_called()
        self.assertFalse(app.processing)

    def test_old_cancel_does_not_cancel_new_recording(self):
        app = self.make_app()
        old = app.session
        app.session = RecordingSession(queue.Queue(), True, True)
        app.cancel_recording(old)
        self.assertTrue(app.recording)
        self.assertFalse(app.session.cancelled.is_set())

    def test_idle_right_click_collapses_without_cancelling(self):
        app = self.make_app()
        app.recording = False
        SmoothDictationApp.right_click(app)
        app.collapse.assert_called_once()
        self.assertFalse(app.session.cancelled.is_set())
        self.assertTrue(app.events.empty())

    def test_active_right_click_cancels_immediately(self):
        app = self.make_app()
        app.right_click = lambda: SmoothDictationApp.right_click(app)
        app.menu = Mock()
        Surface.mousePressEvent(SimpleNamespace(owner=app),
                                SimpleNamespace(button=lambda: Qt.MouseButton.RightButton))
        self.assertTrue(app.session.cancelled.is_set())
        self.assertFalse(app.recording or app.processing)
        app.menu.popup.assert_not_called()

    def test_cancelled_worker_never_touches_recognizer(self):
        app = self.make_app()
        app.online = Mock()
        app.session.cancelled.set()
        app.recognition_worker(app.session)
        app.online.create_stream.assert_not_called()

    def test_cancel_during_native_decode_drops_late_result(self):
        app = self.make_app()
        app.session.audio_queue.put(np.ones(16000, dtype=np.float32))
        app.session.audio_queue.put(None)
        app.online = Mock()
        app.online.is_ready.return_value = False
        app.online.get_result.return_value = ''
        app.speech_gate = SimpleNamespace(speech_audio=lambda x: x)
        app.offline = Mock()
        app.offline.create_stream.return_value = SimpleNamespace(
            accept_waveform=Mock(), result=SimpleNamespace(text='不得输出'))
        app.offline.decode_stream.side_effect = lambda _: app.session.cancelled.set()
        app.punctuation, app.cleaner = Mock(), Mock()
        app.recognition_worker(app.session)
        self.assertTrue(app.events.empty())
        app.punctuation.add_punctuation.assert_not_called()
        app.cleaner.clean.assert_not_called()

    def test_old_result_ignored_after_new_session(self):
        app = self.make_app()
        old = app.session
        app.session = RecordingSession(queue.Queue(), True, True)
        app.events.put(('transcript', ('旧', '旧', ''), old))
        app.finish_transcript = Mock()
        SmoothDictationApp.drain_events(app)
        app.finish_transcript.assert_not_called()


if __name__ == '__main__':
    unittest.main()
