#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mix the battle BGM and the dialogue into the final soundtrack."""
import math
import numpy as np
import wave

SR = 44100


def read(path):
    with wave.open(path, "rb") as w:
        n, ch = w.getnframes(), w.getnchannels()
        a = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768.0
        a = a.reshape(-1, ch)
        assert w.getframerate() == SR, path
    return a


def filt(x, g):
    n = len(x)
    return np.fft.irfft(np.fft.rfft(x) * g(np.fft.rfftfreq(n, 1 / SR)), n)


bgm = read("bgm2.wav")
voc = read("voice.wav")
if voc.shape[1] == 1:
    voc = np.repeat(voc, 2, axis=1)

n = min(len(bgm), len(voc))
bgm, voc = bgm[:n], voc[:n]
vmono = voc.mean(axis=1)

# carve a little room for the voice in the BGM's 1.5-4 kHz range whenever
# he is actually speaking (spectral ducking, gentler than a full-band dip)
env = np.abs(vmono)
k = np.hanning(int(0.09 * SR))
k /= k.sum()
env = np.convolve(env, k, mode="same")
env /= env.max() + 1e-9
carve = 1.0 - 0.30 * np.clip(env * 2.2, 0, 1)

mid = np.stack([filt(bgm[:, c], lambda f: np.exp(-((np.log2(np.maximum(f, 1)) -
                                                    np.log2(2400)) ** 2) / 0.9))
                for c in range(2)], axis=1)
bgm = bgm - mid * (1.0 - carve)[:, None]

out = bgm * 0.82 + voc * 1.02
peak = np.abs(out).max()
out = np.tanh(out / max(peak, 1.0) * 1.06) * 0.96
out /= np.abs(out).max()
out *= 0.95

fo = int(0.30 * SR)
out[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 0.8

with wave.open("final_audio.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((np.clip(out, -1, 1) * 32767).astype("<i2").tobytes())

m = out.mean(axis=1)
print("final_audio.wav  %.2fs  peak %.3f  rms %.1f dBFS"
      % (len(out) / SR, np.abs(m).max(), 20 * math.log10(np.sqrt((m ** 2).mean()))))
for a, b, label in [(0, 4.5, "action"), (4.5, 10.5, "dialogue"), (10.5, 13.5, "panic+exit")]:
    s = m[int(a * SR):int(b * SR)]
    print("  %-11s %5.1f dBFS" % (label, 20 * math.log10(np.sqrt((s ** 2).mean()) + 1e-9)))
