#!/usr/bin/env python3
"""
stt.py — A command-line Speech-to-Text tool.

Backends:
  1. google   -> SpeechRecognition + Google Web Speech API (online, no API key needed)
  2. whisper  -> OpenAI Whisper (offline, more accurate, works on audio files or mic)
  3. vosk     -> Vosk (offline, TRUE live streaming: prints words as you speak them,
                 not just after you finish a sentence)

If what you want is words appearing on screen WHILE you're still talking (like live
captions), use --live (vosk backend). google/whisper only give you the finished text
after a phrase ends - they can't stream partial words.

Usage examples:
    python stt.py --live                                # true live captions, word-by-word
    python stt.py --live --vosk-model-path ./vosk-model-small-en-us-0.15
    python stt.py --mic --backend google                # one phrase, transcribed after you pause
    python stt.py --continuous --backend google         # repeated phrase-by-phrase transcription
    python stt.py --file recording.wav --backend google
    python stt.py --file recording.mp3 --backend whisper --model base
    python stt.py --interactive

Install dependencies first:
    pip install SpeechRecognition pyaudio
    # For whisper backend:
    pip install openai-whisper
    # whisper also needs ffmpeg installed on your system (not via pip):
    #   Ubuntu/Debian: sudo apt install ffmpeg
    #   Mac:           brew install ffmpeg
    #   Windows:       download from ffmpeg.org and add to PATH
    # For vosk (--live) backend:
    pip install vosk
    # Then download a model (one-time) and unzip it, e.g. the small English model:
    #   https://alphacephei.com/vosk/models -> vosk-model-small-en-us-0.15.zip
    #   unzip it, and point --vosk-model-path at the unzipped folder.
"""

import argparse
import os
import sys


def transcribe_google(audio_path=None, mic_timeout=None, phrase_time_limit=None,
                       language="en-US", pause_threshold=0.8):
    """Transcribe using SpeechRecognition + Google Web Speech API (free, online, no key).

    Voice-activated mic behavior:
      - mic_timeout=None means it waits indefinitely for you to start talking (no premature timeout).
      - pause_threshold controls how many seconds of silence mark the end of a phrase,
        i.e. it stops automatically as soon as you stop talking.
    """
    try:
        import speech_recognition as sr
    except ImportError:
        print("SpeechRecognition is not installed. Run: pip install SpeechRecognition pyaudio")
        sys.exit(1)

    recognizer = sr.Recognizer()
    recognizer.pause_threshold = pause_threshold  # how long a pause = "done talking"

    if audio_path:
        if not os.path.isfile(audio_path):
            print(f"File not found: {audio_path}")
            sys.exit(1)
        with sr.AudioFile(audio_path) as source:
            audio = recognizer.record(source)
    else:
        with sr.Microphone() as source:
            print("Adjusting for ambient noise... (stay quiet for a moment)")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("Listening... start talking whenever you're ready (it'll stop automatically when you pause).")
            try:
                audio = recognizer.listen(source, timeout=mic_timeout, phrase_time_limit=phrase_time_limit)
            except sr.WaitTimeoutError:
                return "[No speech detected - timed out waiting for you to start talking. Try again and speak sooner/louder.]"
            print("Processing...")

    try:
        text = recognizer.recognize_google(audio, language=language)
        return text
    except sr.UnknownValueError:
        return "[Could not understand audio]"
    except sr.RequestError as e:
        return f"[Google API error: {e}]"


def transcribe_whisper(audio_path, model_size="base", language=None):
    """Transcribe an audio file using OpenAI Whisper (offline, needs ffmpeg installed)."""
    try:
        import whisper
    except ImportError:
        print("openai-whisper is not installed. Run: pip install openai-whisper")
        sys.exit(1)

    if not os.path.isfile(audio_path):
        print(f"File not found: {audio_path}")
        sys.exit(1)

    print(f"Loading Whisper model '{model_size}' (first run downloads it, may take a while)...")
    model = whisper.load_model(model_size)

    print("Transcribing...")
    kwargs = {}
    if language:
        kwargs["language"] = language
    result = model.transcribe(audio_path, **kwargs)
    return result["text"].strip()


def live_captions_vosk(model_path, samplerate=16000):
    """TRUE live/streaming transcription: prints words as you speak them (partial results),
    then locks in the finished line once you pause. Runs until Ctrl+C.

    Needs: pip install vosk pyaudio
    Needs a downloaded Vosk model folder (see module docstring for the link).
    """
    try:
        import vosk
        import pyaudio
    except ImportError:
        print("Missing dependency. Run: pip install vosk pyaudio")
        sys.exit(1)

    if not os.path.isdir(model_path):
        print(f"Vosk model folder not found: {model_path}")
        print("Download one from https://alphacephei.com/vosk/models, unzip it, "
              "and pass its path with --vosk-model-path.")
        sys.exit(1)

    vosk.SetLogLevel(-1)  # silence vosk's own debug logging
    model = vosk.Model(model_path)
    recognizer = vosk.KaldiRecognizer(model, samplerate)

    mic = pyaudio.PyAudio()
    stream = mic.open(format=pyaudio.paInt16, channels=1, rate=samplerate,
                       input=True, frames_per_buffer=4000)
    stream.start_stream()

    print("Live captions started - just start talking, words will appear as you speak.")
    print("Press Ctrl+C to stop.\n")

    last_partial = ""
    try:
        while True:
            data = stream.read(4000, exception_on_overflow=False)

            if recognizer.AcceptWaveform(data):
                # A pause was detected - this phrase is finalized.
                import json
                result = json.loads(recognizer.Result())
                final_text = result.get("text", "").strip()
                if final_text:
                    # Clear the in-progress partial line, then print the locked-in line.
                    print("\r" + " " * (len(last_partial) + 4) + "\r", end="")
                    print(final_text)
                last_partial = ""
            else:
                import json
                partial = json.loads(recognizer.PartialResult())
                partial_text = partial.get("partial", "").strip()
                if partial_text and partial_text != last_partial:
                    print("\r" + " " * (len(last_partial) + 4) + "\r", end="")
                    print(f"...{partial_text}", end="", flush=True)
                    last_partial = partial_text
    except KeyboardInterrupt:
        print("\nStopped listening.")
    finally:
        stream.stop_stream()
        stream.close()
        mic.terminate()


def continuous_listen(backend="google", language="en-US", pause_threshold=0.8, model_size="base"):
    """Keep the mic open and transcribe continuously: as soon as you finish one phrase
    (a pause is detected), that phrase gets transcribed and printed, and it immediately
    starts listening for your next one — no need to press anything in between.
    Press Ctrl+C to stop.
    """
    try:
        import speech_recognition as sr
    except ImportError:
        print("SpeechRecognition is not installed. Run: pip install SpeechRecognition pyaudio")
        sys.exit(1)

    recognizer = sr.Recognizer()
    recognizer.pause_threshold = pause_threshold

    whisper_model = None
    if backend == "whisper":
        try:
            import whisper
        except ImportError:
            print("openai-whisper is not installed. Run: pip install openai-whisper")
            sys.exit(1)
        print(f"Loading Whisper model '{model_size}'...")
        whisper_model = whisper.load_model(model_size)

    def handle_phrase(recognizer_, audio):
        # Runs in a background thread each time a pause ends a phrase.
        try:
            if backend == "google":
                text = recognizer_.recognize_google(audio, language=language)
            else:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(audio.get_wav_data())
                    tmp_path = tmp.name
                result = whisper_model.transcribe(tmp_path, language=language.split("-")[0])
                text = result["text"].strip()
                os.remove(tmp_path)
            if text:
                print(f"> {text}")
        except sr.UnknownValueError:
            pass  # silence/noise that wasn't recognizable speech - just ignore it
        except sr.RequestError as e:
            print(f"[Google API error: {e}]")
        except Exception as e:
            print(f"[Transcription error: {e}]")

    with sr.Microphone() as source:
        print("Adjusting for ambient noise... (stay quiet for a moment)")
        recognizer.adjust_for_ambient_noise(source, duration=1)

    print("Listening continuously. Just start talking - each pause will print a transcribed line.")
    print("Press Ctrl+C to stop.\n")

    stop_listening = recognizer.listen_in_background(sr.Microphone(), handle_phrase)

    try:
        while True:
            import time
            time.sleep(0.2)
    except KeyboardInterrupt:
        stop_listening(wait_for_stop=False)
        print("\nStopped listening.")


def record_from_mic_voice_activated(out_path="mic_recording.wav", pause_threshold=0.8):
    """Record from the mic, starting as soon as speech is detected and stopping on silence.
    Used to feed whisper (which needs an audio file, not a live stream)."""
    try:
        import speech_recognition as sr
    except ImportError:
        print("SpeechRecognition is not installed. Run: pip install SpeechRecognition pyaudio")
        sys.exit(1)

    recognizer = sr.Recognizer()
    recognizer.pause_threshold = pause_threshold
    with sr.Microphone() as source:
        print("Adjusting for ambient noise... (stay quiet for a moment)")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Listening... start talking whenever you're ready (it'll stop automatically when you pause).")
        try:
            audio = recognizer.listen(source, timeout=None)
        except sr.WaitTimeoutError:
            print("No speech detected.")
            return None

    with open(out_path, "wb") as f:
        f.write(audio.get_wav_data())
    print(f"Saved recording to: {out_path}")
    return out_path


def interactive_mode():
    """A simple REPL-style loop, similar to a chat interface."""
    print("=== Speech-to-Text (interactive mode) ===")
    print("Commands:")
    print("  /listen            - listen once via microphone and transcribe (google backend)")
    print("  /continuous        - keep listening and transcribing phrase after phrase (Ctrl+C to stop)")
    print("  /live              - TRUE live captions, words appear as you speak (needs vosk model)")
    print("  /file <path>       - transcribe an existing audio file")
    print("  /backend google|whisper")
    print("  /model <size>      - whisper model size: tiny, base, small, medium, large")
    print("  /lang <code>       - language code (e.g. en-US for google, en for whisper)")
    print("  /pause <seconds>   - silence duration that ends a phrase (default 0.8s)")
    print("  /voskmodel <path>  - set path to your unzipped vosk model folder (for /live)")
    print("  quit               - exit\n")

    backend = "google"
    model_size = "base"
    lang = "en-US"
    pause_threshold = 0.8
    vosk_model_path = "./vosk-model-small-en-us-0.15"

    while True:
        try:
            user_in = input("Command> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_in:
            continue
        if user_in.lower() in ("quit", "exit"):
            print("Goodbye!")
            break
        if user_in.startswith("/backend"):
            parts = user_in.split()
            if len(parts) == 2 and parts[1] in ("google", "whisper"):
                backend = parts[1]
                print(f"Backend set to: {backend}")
            else:
                print("Usage: /backend google|whisper")
            continue
        if user_in.startswith("/model"):
            parts = user_in.split()
            if len(parts) == 2:
                model_size = parts[1]
                print(f"Whisper model set to: {model_size}")
            else:
                print("Usage: /model tiny|base|small|medium|large")
            continue
        if user_in.startswith("/lang"):
            parts = user_in.split()
            if len(parts) == 2:
                lang = parts[1]
                print(f"Language set to: {lang}")
            else:
                print("Usage: /lang <code>")
            continue
        if user_in.startswith("/pause"):
            parts = user_in.split()
            if len(parts) == 2:
                try:
                    pause_threshold = float(parts[1])
                    print(f"Pause threshold set to: {pause_threshold}s of silence ends a phrase")
                except ValueError:
                    print("Usage: /pause <seconds, e.g. 0.8>")
            else:
                print("Usage: /pause <seconds, e.g. 0.8>")
            continue
        if user_in.startswith("/voskmodel"):
            parts = user_in.split(maxsplit=1)
            if len(parts) == 2:
                vosk_model_path = parts[1].strip()
                print(f"Vosk model path set to: {vosk_model_path}")
            else:
                print("Usage: /voskmodel <path to unzipped model folder>")
            continue
        if user_in.startswith("/live"):
            live_captions_vosk(vosk_model_path)
            continue
        if user_in.startswith("/continuous"):
            continuous_listen(backend=backend, language=lang, pause_threshold=pause_threshold,
                               model_size=model_size)
            continue
        if user_in.startswith("/listen"):
            if backend == "google":
                text = transcribe_google(language=lang, pause_threshold=pause_threshold)
            else:
                path = record_from_mic_voice_activated(pause_threshold=pause_threshold)
                text = transcribe_whisper(path, model_size=model_size,
                                           language=lang.split("-")[0] if lang else None)
            print(f"\nTranscript: {text}\n")
            continue
        if user_in.startswith("/file"):
            parts = user_in.split(maxsplit=1)
            if len(parts) == 2:
                path = parts[1].strip()
                if backend == "google":
                    text = transcribe_google(audio_path=path, language=lang)
                else:
                    text = transcribe_whisper(path, model_size=model_size,
                                               language=lang.split("-")[0] if lang else None)
                print(f"\nTranscript: {text}\n")
            else:
                print("Usage: /file <path to audio file>")
            continue

        print("Unknown command. Type /listen, /continuous, /live, /file <path>, /backend, /model, /lang, or quit.")


def main():
    parser = argparse.ArgumentParser(description="Speech-to-Text CLI tool")
    parser.add_argument("--mic", action="store_true", help="Record from microphone and transcribe once")
    parser.add_argument("--continuous", action="store_true",
                         help="Keep listening and transcribing phrase after phrase until Ctrl+C")
    parser.add_argument("--live", action="store_true",
                         help="TRUE live captions: prints words as you speak them (uses vosk), until Ctrl+C")
    parser.add_argument("--vosk-model-path", type=str, default="./vosk-model-small-en-us-0.15",
                         help="Path to an unzipped vosk model folder (for --live)")
    parser.add_argument("--file", type=str, help="Path to an audio file to transcribe")
    parser.add_argument("--backend", choices=["google", "whisper"], default="google",
                         help="Transcription backend (default: google)")
    parser.add_argument("--model", type=str, default="base",
                         help="Whisper model size: tiny, base, small, medium, large (whisper backend only)")
    parser.add_argument("--lang", type=str, default="en-US",
                         help="Language code, e.g. en-US (google) or en (whisper)")
    parser.add_argument("--pause-threshold", type=float, default=0.8,
                         help="Seconds of silence that mark the end of speech (default: 0.8)")
    parser.add_argument("--max-seconds", type=int, default=None,
                         help="Optional safety cap on phrase length in seconds (default: unlimited)")
    parser.add_argument("--interactive", action="store_true", help="Start interactive chat-like mode")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
        return

    if args.live:
        live_captions_vosk(args.vosk_model_path)
        return

    if args.continuous:
        continuous_listen(backend=args.backend, language=args.lang,
                           pause_threshold=args.pause_threshold, model_size=args.model)
        return

    if args.mic:
        if args.backend == "google":
            text = transcribe_google(mic_timeout=None, phrase_time_limit=args.max_seconds,
                                      language=args.lang, pause_threshold=args.pause_threshold)
        else:
            path = record_from_mic_voice_activated(pause_threshold=args.pause_threshold)
            text = transcribe_whisper(path, model_size=args.model, language=args.lang.split("-")[0])
        print(f"\nTranscript: {text}")
        return

    if args.file:
        if args.backend == "google":
            text = transcribe_google(audio_path=args.file, language=args.lang)
        else:
            text = transcribe_whisper(args.file, model_size=args.model, language=args.lang.split("-")[0])
        print(f"\nTranscript: {text}")
        return

    print("No input source given. Use --mic, --file <path>, or --interactive.")


if __name__ == "__main__":
    main()
