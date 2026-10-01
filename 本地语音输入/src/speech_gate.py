"""Reject non-speech before final ASR, using a small CPU Silero VAD model."""
from pathlib import Path

import numpy as np
import sherpa_onnx

RATE = 16000
from paths import APP_ROOT

MODEL = APP_ROOT / 'models' / 'vad' / 'silero_vad.onnx'


class SpeechGate:
    def __init__(self):
        if not MODEL.is_file():
            raise FileNotFoundError('缺少静音检测模型：' + str(MODEL))
        config = sherpa_onnx.VadModelConfig()
        config.silero_vad.model = str(MODEL)
        config.silero_vad.threshold = 0.5
        config.silero_vad.min_speech_duration = 0.2
        config.silero_vad.min_silence_duration = 0.3
        config.sample_rate = RATE
        config.num_threads = 1
        config.provider = 'cpu'
        self.vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=30)

    def speech_audio(self, samples: np.ndarray) -> np.ndarray:
        """Return the speech envelope with 500ms padding, or empty on no speech.

        Keep internal pauses and whole-sentence context. Reset recurrent state for
        every recording so a previous utterance cannot make silence pass the gate.
        Errors propagate: an unavailable VAD must never enable automatic typing.
        """
        samples = np.asarray(samples, dtype=np.float32).reshape(-1)
        self.vad.reset()
        if len(samples) < RATE // 5 or not np.isfinite(samples).all():
            return np.empty(0, dtype=np.float32)
        # DC offset is not speech. This floor only filters near-digital silence;
        # distinguishing room noise from speech is the neural VAD's job.
        samples = samples - np.mean(samples)
        if float(np.sqrt(np.mean(samples * samples))) < 0.0001:
            return np.empty(0, dtype=np.float32)
        ranges = []
        padded = np.concatenate((samples, np.zeros(RATE // 2, dtype=np.float32)))
        for start in range(0, len(padded), 512):
            window = padded[start:start + 512]
            if len(window) < 512:
                window = np.pad(window, (0, 512 - len(window)))
            self.vad.accept_waveform(window)
            while not self.vad.empty():
                segment = self.vad.front
                ranges.append((segment.start, segment.start + len(segment.samples)))
                self.vad.pop()
        self.vad.flush()
        while not self.vad.empty():
            segment = self.vad.front
            ranges.append((segment.start, segment.start + len(segment.samples)))
            self.vad.pop()
        if not ranges:
            return np.empty(0, dtype=np.float32)
        # Allow for a VAD's delayed onset on soft first syllables; do not clip
        # the start of a word just to remove another fraction of silent audio.
        pad = int(0.5 * RATE)
        left = max(0, ranges[0][0] - pad)
        right = min(len(samples), ranges[-1][1] + pad)
        return np.ascontiguousarray(samples[left:right])
