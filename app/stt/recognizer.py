"""
recognizer.py
-------------
Mic capture + speech-to-text, wrapped in a single blocking call:

    text = recognizer.listen()

app/main.py's PipelineWorker calls this in a loop on a background QThread,
so "blocking" is fine — it just blocks that worker thread, never the GUI.

Pipeline:
    sounddevice captures raw audio -> a simple energy-based VAD decides
    where the phrase starts/ends -> faster-whisper transcribes the
    captured chunk -> plain text comes back (or None if nothing usable
    was captured, e.g. the user toggled the mic off mid-silence).

faster-whisper is loaded lazily (first call to listen()) so importing this
module — e.g. for tests — never pays the model-load cost or requires the
model files to be present.
"""

import threading

import numpy as np

from app.utils.config import config
from app.utils.logger import get_logger

log = get_logger(__name__)


class Recognizer:
    def __init__(
        self,
        model_size: str = None,
        device: str = None,
        compute_type: str = None,
        sample_rate: int = None,
    ):
        self.model_size = model_size or config.stt_model_size
        self.device = device or config.stt_device
        self.compute_type = compute_type or config.stt_compute_type
        self.sample_rate = sample_rate or config.sample_rate
        self.language = config.stt_language or None

        self._model = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def stop(self):
        """Ask a blocking listen() call to return as soon as possible."""
        self._stop_event.set()

    def _ensure_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            log.info("Loading faster-whisper model '%s' (%s/%s)...",
                      self.model_size, self.device, self.compute_type)
            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
            log.info("STT model loaded.")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def listen(self) -> str:
        """Block until one spoken phrase is captured and transcribed.

        Returns the transcribed text, or "" if the mic was stopped before
        any usable audio was captured (the caller should just loop again).
        """
        self._stop_event.clear()
        audio = self._record_phrase()
        if audio is None or len(audio) == 0:
            return ""

        self._ensure_model()
        segments, _info = self._model.transcribe(
            audio, language=self.language, beam_size=1, vad_filter=True
        )
        text = " ".join(seg.text.strip() for seg in segments).strip()
        return text

    # ------------------------------------------------------------------ #
    # Audio capture / VAD
    # ------------------------------------------------------------------ #
    def _record_phrase(self):
        """Capture audio from the default mic until we detect a phrase
        followed by enough silence (or hit the max-length safety cap),
        using simple RMS-based voice activity detection. Returns a
        float32 mono numpy array at self.sample_rate, or None if stopped
        before any speech was detected."""
        import sounddevice as sd

        block_duration = 0.05  # seconds per analysis chunk
        block_size = max(1, int(self.sample_rate * block_duration))

        frames = []
        speaking = False
        silence_run = 0.0
        speech_run = 0.0

        def rms(chunk: np.ndarray) -> float:
            return float(np.sqrt(np.mean(np.square(chunk)) + 1e-12))

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=block_size,
        ) as stream:
            while not self._stop_event.is_set():
                chunk, _overflow = stream.read(block_size)
                chunk = chunk[:, 0]
                level = rms(chunk)

                if level >= config.vad_silence_rms:
                    speaking = True
                    speech_run += block_duration
                    silence_run = 0.0
                    frames.append(chunk)
                elif speaking:
                    silence_run += block_duration
                    frames.append(chunk)
                    if silence_run >= config.vad_silence_duration:
                        break
                # else: still silence before any speech started — keep waiting

                if speech_run >= config.vad_max_phrase_seconds:
                    break

        if not speaking or speech_run < config.vad_min_phrase_seconds:
            return None

        return np.concatenate(frames) if frames else None
