import sounddevice as sd
import numpy as np

def rms(chunk):
    return float(np.sqrt(np.mean(np.square(chunk)) + 1e-12))

print("Speak normally. Threshold is 0.010 — watch if your voice crosses it.")
with sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=800) as stream:
    while True:
        chunk, _ = stream.read(800)
        print(f"RMS: {rms(chunk[:, 0]):.4f}")
