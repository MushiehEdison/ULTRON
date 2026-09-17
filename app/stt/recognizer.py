#!/usr/bin/env python3
"""
speech_to_text.py — Offline speech-to-text tool using OpenAI Whisper.

Two modes:
  1. File mode  — transcribe an existing audio file (wav, mp3, m4a, etc.)
  2. Live mode   — transcribe from your microphone in near real-time

Everything runs fully offline once the Whisper model is downloaded once.

Usage:
    python speech_to_text.py file  path/to/audio.mp3  --model small --language en --output transcript.txt
    python speech_to_text.py live  --model base --language en --output transcript.txt

Run `python speech_to_text.py --help` for all options.
"""

import argparse
import collections
import queue
import sys
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np


# --------------------------------------------------------------------------- #
# Whisper model handling
# --------------------------------------------------------------------------- #

_MODEL_CACHE = {}


def load_model(model_size: str):
    """Load (and cache) a Whisper model so repeated calls don't reload it."""
    if model_size in _MODEL_CACHE:
        return _MODEL_CACHE[model_size]

    try:
        import whisper
    except ImportError:
        sys.exit(
            "ERROR: the 'openai-whisper' package is not installed.\n"
            "Run:  pip install -r requirements.txt"
        )

    print(f"Loading Whisper model '{model_size}' (first run downloads it, "
          f"then it's cached locally)...")
    model = whisper.load_model(model_size)
    _MODEL_CACHE[model_size] = model
    print("Model loaded.\n")
    return model


# --------------------------------------------------------------------------- #
# File transcription
# --------------------------------------------------------------------------- #

def transcribe_file(path: str, model_size: str, language: str | None,
                     output: str | None, verbose: bool):
    audio_path = Path(path)
    if not audio_path.exists():
        sys.exit(f"ERROR: file not found: {audio_path}")

    model = load_model(model_size)

    print(f"Transcribing '{audio_path.name}'...\n")
    result = model.transcribe(
        str(audio_path),
        language=language,
        verbose=verbose,
        fp16=False,  # safe default for CPU; set True if you have a supported GPU
    )

    text = result["text"].strip()
    print("\n----- TRANSCRIPT -----")
    print(text)
    print("-----------------------\n")

    if output:
        _write_output(output, result)
        print(f"Saved to {output}")

    return result


def _write_output(output_path: str, result: dict):
    out = Path(output_path)
    if out.suffix.lower() == ".srt":
        _write_srt(out, result["segments"])
    else:
        out.write_text(result["text"].strip() + "\n", encoding="utf-8")


def _write_srt(out: Path, segments: list):
    def fmt(t: float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{fmt(seg['start'])} --> {fmt(seg['end'])}")
        lines.append(seg["text"].strip())
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Live microphone transcription
# --------------------------------------------------------------------------- #

SAMPLE_RATE = 16000        # Whisper expects 16kHz
FRAME_MS = 30              # VAD frame size in ms (must be 10/20/30 for webrtcvad)
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)
SILENCE_TIMEOUT_MS = 700   # how much trailing silence ends an utterance
MAX_UTTERANCE_S = 30       # safety cap so one segment can't grow forever


def transcribe_live(model_size: str, language: str | None, output: str | None,
                     mic_device: int | None, vad_aggressiveness: int):
    try:
        import sounddevice as sd
        import webrtcvad
    except ImportError:
        sys.exit(
            "ERROR: live mode needs 'sounddevice' and 'webrtcvad'.\n"
            "Run:  pip install -r requirements.txt\n"
            "Note: sounddevice also needs the system PortAudio library "
            "(see README for your OS)."
        )

    model = load_model(model_size)
    vad = webrtcvad.Vad(vad_aggressiveness)

    audio_q: "queue.Queue[bytes]" = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        audio_q.put(bytes(indata))

    print("Listening... speak into your microphone. Press Ctrl+C to stop.\n")

    full_transcript_parts = []
    ring = collections.deque(maxlen=int(300 / FRAME_MS))  # ~300ms pre-roll
    voiced_frames = []
    silence_ms = 0
    speaking = False
    utterance_started_at = None

    stream = sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=FRAME_SAMPLES,
        dtype="int16",
        channels=1,
        device=mic_device,
        callback=callback,
    )

    try:
        with stream:
            while True:
                frame = audio_q.get()
                is_speech = vad.is_speech(frame, SAMPLE_RATE)

                if not speaking:
                    ring.append(frame)
                    if is_speech:
                        speaking = True
                        utterance_started_at = time.time()
                        voiced_frames = list(ring)
                        ring.clear()
                        silence_ms = 0
                else:
                    voiced_frames.append(frame)
                    if is_speech:
                        silence_ms = 0
                    else:
                        silence_ms += FRAME_MS

                    too_long = (time.time() - utterance_started_at) >= MAX_UTTERANCE_S
                    if silence_ms >= SILENCE_TIMEOUT_MS or too_long:
                        segment_audio = b"".join(voiced_frames)
                        speaking = False
                        voiced_frames = []
                        silence_ms = 0

                        text = _transcribe_pcm_chunk(model, segment_audio, language)
                        if text:
                            timestamp = datetime.now().strftime("%H:%M:%S")
                            print(f"[{timestamp}] {text}")
                            full_transcript_parts.append(text)
    except KeyboardInterrupt:
        print("\nStopped listening.")
    finally:
        if output and full_transcript_parts:
            Path(output).write_text(
                "\n".join(full_transcript_parts) + "\n", encoding="utf-8"
            )
            print(f"Saved transcript to {output}")


def _transcribe_pcm_chunk(model, pcm_bytes: bytes, language: str | None) -> str:
    """Convert raw int16 PCM bytes to the float32 array Whisper expects."""
    audio_np = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    if audio_np.size < SAMPLE_RATE * 0.3:  # skip tiny blips (<0.3s)
        return ""
    result = model.transcribe(audio_np, language=language, fp16=False)
    return result["text"].strip()


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline speech-to-text using Whisper (file or live mic).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    common = dict(
        model=("--model", dict(default="small",
               choices=["tiny", "base", "small", "medium", "large"],
               help="Whisper model size: bigger = more accurate, slower.")),
        language=("--language", dict(default=None,
                  help="Force a language code (e.g. en, fr). Omit to auto-detect.")),
        output=("--output", dict(default=None,
                help="Save the transcript to this file (.txt or .srt).")),
    )

    p_file = sub.add_parser("file", help="Transcribe an existing audio file.")
    p_file.add_argument("path", help="Path to the audio file.")
    p_file.add_argument(common["model"][0], **common["model"][1])
    p_file.add_argument(common["language"][0], **common["language"][1])
    p_file.add_argument(common["output"][0], **common["output"][1])
    p_file.add_argument("--quiet", action="store_true",
                         help="Suppress Whisper's per-segment progress output.")

    p_live = sub.add_parser("live", help="Transcribe from the microphone in real time.")
    p_live.add_argument(common["model"][0], **common["model"][1])
    p_live.add_argument(common["language"][0], **common["language"][1])
    p_live.add_argument(common["output"][0], **common["output"][1])
    p_live.add_argument("--device", type=int, default=None,
                         help="Input device index (see --list-devices).")
    p_live.add_argument("--list-devices", action="store_true",
                         help="List available audio input devices and exit.")
    p_live.add_argument("--vad-aggressiveness", type=int, default=2, choices=[0, 1, 2, 3],
                         help="Voice activity detection sensitivity (0=lenient, 3=strict).")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "live" and getattr(args, "list_devices", False):
        import sounddevice as sd
        print(sd.query_devices())
        return

    if args.mode == "file":
        transcribe_file(
            path=args.path,
            model_size=args.model,
            language=args.language,
            output=args.output,
            verbose=not args.quiet,
        )
    elif args.mode == "live":
        transcribe_live(
            model_size=args.model,
            language=args.language,
            output=args.output,
            mic_device=args.device,
            vad_aggressiveness=args.vad_aggressiveness,
        )


if __name__ == "__main__":
    main()
