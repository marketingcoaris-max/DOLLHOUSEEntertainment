#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dialogue track for the Pea Bomber short.

Synthesises the hero's lines with pyopenjtalk, then shapes the delivery into
an energetic young man: pitched up, sped up, doubled, presence-boosted,
compressed and lightly saturated so it cuts through the battle BGM.

Also writes voice_timing.json (per-line start/end + a 24fps mouth-openness
envelope) so the animation can lip-sync to it.
"""
import json
import numpy as np
import pyopenjtalk
import wave

SR = 44100
FPS = 24
TTS_SR = 48000

# (key, text, start_sec, half_tone, speed, gain)
LINES = [
    ("l1", "俺はピーボンバー！",       4.62, 3.0, 1.25, 1.00),
    ("l2", "よう氷！",                 6.05, 3.2, 1.22, 1.00),
    ("l3", "ハッピーバースデー！",     7.08, 3.4, 1.20, 1.00),
    ("l4", "これからもよろしくな！",   8.58, 2.8, 1.28, 0.96),
    ("l5", "やべえ！",                10.30, 4.2, 1.35, 1.00),
    ("l6", "もれそう！",              11.22, 4.6, 1.32, 1.00),
]

DUR = 13.5
N = int(DUR * SR)
rng = np.random.default_rng(7)


# ------------------------------------------------------------------ helpers
def resample(x, src, dst):
    n = int(len(x) * dst / src)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def lowpass(x, fc, sr=SR):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / sr)
    return np.fft.irfft(X / (1.0 + (f / fc) ** 4) ** 0.75, n)


def highpass(x, fc, sr=SR):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / sr)
    k = (f / fc) ** 2
    return np.fft.irfft(X * k / (1.0 + k), n)


def peaking(x, fc, gain_db, q=1.0, sr=SR):
    """Gaussian-in-log-frequency bell, applied in the frequency domain."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / sr)
    lf = np.log2(np.maximum(f, 1.0))
    g = 1.0 + (10 ** (gain_db / 20.0) - 1.0) * np.exp(-((lf - np.log2(fc)) ** 2) / (2 * (1.0 / q) ** 2))
    return np.fft.irfft(X * g, n)


def compress(x, thresh=0.22, ratio=4.5, atk=0.004, rel=0.09, sr=SR):
    """Simple feed-forward compressor on a smoothed envelope."""
    env = np.abs(x)
    a = np.exp(-1.0 / (atk * sr))
    r = np.exp(-1.0 / (rel * sr))
    out = np.empty_like(env)
    prev = 0.0
    for i in range(len(env)):
        c = a if env[i] > prev else r
        prev = c * prev + (1 - c) * env[i]
        out[i] = prev
    gain = np.ones_like(out)
    over = out > thresh
    gain[over] = (thresh + (out[over] - thresh) / ratio) / np.maximum(out[over], 1e-9)
    return x * gain


def reverb(x, dur=0.34, wet=0.13, sr=SR):
    n = int(dur * sr)
    t = np.arange(n) / sr
    ir = rng.normal(0, 1, n) * np.exp(-11.0 * t)
    ir = lowpass(ir, 5200, sr)
    ir[: int(0.012 * sr)] = 0
    ir /= np.abs(ir).sum() / 9.0
    L = 1 << (len(x) + n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)[: len(x)]
    return x * (1 - wet) + y * wet


def shape(x):
    """Turn the flat HTS read into a bright, punchy shout."""
    x = x / (np.abs(x).max() + 1e-9)
    x = highpass(x, 95)
    x = peaking(x, 330, -3.5, 1.1)        # drop the boxy low-mid
    x = peaking(x, 1750, +3.0, 1.0)       # vowel clarity
    x = peaking(x, 3400, +5.0, 0.9)       # presence / shout
    x = peaking(x, 7000, +3.0, 1.2)       # air, hides the HMM buzz
    # doubling: two slightly detuned + delayed copies widen and de-buzz it
    d1 = resample(x, SR, int(SR * 1.006))
    d2 = resample(x, SR, int(SR * 0.994))
    m = max(len(x), len(d1), len(d2))
    acc = np.zeros(m)
    acc[: len(x)] += x
    o1 = int(0.011 * SR)
    o2 = int(0.019 * SR)
    acc[o1: o1 + len(d1)] += d1[: m - o1] * 0.34
    acc[o2: o2 + len(d2)] += d2[: m - o2] * 0.30
    x = acc / 1.55
    x = compress(x, 0.20, 5.0)
    x = np.tanh(x * 1.7) * 0.72           # a little grit for the shouty edge
    x = reverb(x, 0.34, 0.12)
    return x / (np.abs(x).max() + 1e-9)


# ------------------------------------------------------------------ synth
track = np.zeros(N)
timing = []
print("synthesising dialogue ...")

for key, text, start, half_tone, speed, gain in LINES:
    wav, sr = pyopenjtalk.tts(text, speed=speed, half_tone=half_tone)
    x = resample(wav.astype(np.float64) / 32768.0, sr, SR)
    x = shape(x) * gain
    i = int(start * SR)
    j = min(N, i + len(x))
    track[i:j] += x[: j - i]
    dur = len(x) / SR
    timing.append(dict(key=key, text=text, start=start, end=start + dur, dur=dur))
    print("  %-3s %-14s %5.2f - %5.2f  (%.2fs)" % (key, text, start, start + dur, dur))

# master
track = np.tanh(track * 1.12) * 0.93
track /= np.abs(track).max() + 1e-9
track *= 0.94

with wave.open("voice.wav", "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((track * 32767).astype("<i2").tobytes())

# ------------------------------------------------------------------ lip sync
# mouth openness per video frame, from a smoothed envelope of the voice
nf = int(DUR * FPS)
env = np.abs(track)
win = int(SR / FPS)
mouth = np.zeros(nf)
for f in range(nf):
    seg = env[f * win:(f + 1) * win]
    mouth[f] = float(np.sqrt((seg ** 2).mean())) if len(seg) else 0.0
if mouth.max() > 0:
    mouth = mouth / mouth.max()
mouth = np.clip(mouth * 1.45, 0, 1) ** 0.68
# slight smoothing so the jaw does not chatter
k = np.array([0.22, 0.56, 0.22])
mouth = np.convolve(mouth, k, mode="same")

with open("voice_timing.json", "w") as fp:
    json.dump(dict(fps=FPS, dur=DUR, lines=timing, mouth=[round(v, 4) for v in mouth]), fp,
              ensure_ascii=False, indent=1)

speak = [(t["start"], t["end"]) for t in timing]
print("wrote voice.wav (%.2fs) + voice_timing.json" % DUR)
print("speaking windows:", [("%.2f-%.2f" % s) for s in speak])
