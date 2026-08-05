#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
"PLUS BOMBER!" - original heroic battle theme + SFX for the Pea Bomber short.

An original composition written for this video (D minor, 160 BPM, driving
rock drums under a brass fanfare), in the spirit of shonen-hero battle music.
Musical accents are locked to the picture cuts at 0.0 / 1.5 / 3.0 / 4.5 /
8.25 / 9.75 s.
"""
import math
import numpy as np

SR = 44100
BPM = 160.0
BEAT = 60.0 / BPM              # 0.375 s
DUR = 11.25                    # seconds, matches the 270-frame cut
N = int(DUR * SR)

rng = np.random.default_rng(20260805)
mix_music = np.zeros(N, np.float64)
mix_sfx = np.zeros(N, np.float64)


# ---------------------------------------------------------------- utilities
def b2s(beats):
    return int(beats * BEAT * SR)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def add(buf, sig, at, gain=1.0):
    i = int(at)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def adsr(n, a, d, s, r, sr=SR):
    a, d, r = int(a * sr), int(d * sr), int(r * sr)
    a = max(1, min(a, n))
    d = max(1, min(d, max(1, n - a)))
    sus = max(0, n - a - d - r)
    r = max(1, min(r, max(1, n - a - d)))
    env = np.concatenate([
        np.linspace(0, 1, a),
        np.linspace(1, s, d),
        np.full(sus, s),
        np.linspace(s, 0, r),
    ])
    if len(env) < n:
        env = np.concatenate([env, np.zeros(n - len(env))])
    return env[:n]


def lowpass(x, fc):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    X *= 1.0 / (1.0 + (f / fc) ** 4) ** 0.75
    return np.fft.irfft(X, n)


def highpass(x, fc):
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    k = (f / fc) ** 2
    X *= k / (1.0 + k)
    return np.fft.irfft(X, n)


def bandpass(x, lo, hi):
    return lowpass(highpass(x, lo), hi)


def saw(freq, n, harm=22, vib=0.0, vibf=5.5, detune=0.0):
    """Band-limited-ish sawtooth with optional vibrato + detune (cents)."""
    t = np.arange(n) / SR
    f = freq * 2 ** (detune / 1200.0)
    if vib:
        ramp = np.clip((t - 0.10) / 0.18, 0, 1)
        f = f * (1.0 + vib * ramp * np.sin(2 * np.pi * vibf * t))
    ph = 2 * np.pi * np.cumsum(np.full(n, 0.0) + f) / SR
    out = np.zeros(n)
    kmax = max(1, min(harm, int(SR * 0.45 / max(freq, 1))))
    for k in range(1, kmax + 1):
        out += np.sin(k * ph) / k
    return out * (2.0 / np.pi)


def sine(freq, n, ph0=0.0):
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * freq * t + ph0)


# ---------------------------------------------------------------- instruments
def brass(m, beats, vel=1.0):
    """Punchy synth-brass: detuned saws, filter envelope, late vibrato."""
    n = b2s(beats)
    f = midi(m)
    s = (saw(f, n, 24, vib=0.006, detune=-7)
         + saw(f, n, 24, vib=0.006, detune=+7)
         + 0.6 * saw(f, n, 18, vib=0.006))
    s /= 2.6
    env = adsr(n, 0.022, 0.09, 0.86, 0.10)
    # attack "blat": a short noise/upper-harmonic burst
    nb = min(n, int(0.035 * SR))
    s[:nb] += rng.normal(0, 0.30, nb) * np.linspace(1, 0, nb)
    s = lowpass(s, 2600 + 2600 * vel)
    return s * env * vel


def strings(m, beats, vel=1.0):
    n = b2s(beats)
    f = midi(m)
    s = (saw(f, n, 16, detune=-9) + saw(f, n, 16, detune=+9)) / 2.4
    s = lowpass(s, 2200)
    return s * adsr(n, 0.012, 0.05, 0.6, 0.05) * vel


def gtr(m, beats, vel=1.0):
    """Distorted power chord: root + 5th + octave, palm-muted envelope."""
    n = b2s(beats)
    f = midi(m)
    s = saw(f, n, 14) + saw(f * 1.4983, n, 14) * 0.85 + saw(f * 2, n, 12) * 0.6
    s = np.tanh(s * 3.2) * 0.5
    s = bandpass(s, 90, 5200)
    return s * adsr(n, 0.004, 0.06, 0.55, 0.05) * vel


def bass(m, beats, vel=1.0):
    n = b2s(beats)
    f = midi(m)
    s = 0.75 * saw(f, n, 12) + 0.9 * sine(f, n) + 0.35 * sine(f * 2, n)
    s = lowpass(s, 900)
    return s * adsr(n, 0.006, 0.07, 0.7, 0.05) * vel


def bell(m, beats, vel=1.0):
    """Glockenspiel sparkle for the birthday beat."""
    n = b2s(beats)
    f = midi(m)
    t = np.arange(n) / SR
    s = (sine(f, n) + 0.5 * sine(f * 2.76, n) + 0.28 * sine(f * 5.4, n))
    return s * np.exp(-7.0 * t) * 0.5 * vel


# ---------------------------------------------------------------- drums
def kick(vel=1.0):
    n = int(0.30 * SR)
    t = np.arange(n) / SR
    f = 120 * np.exp(-28 * t) + 46
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * np.exp(-13 * t)
    s += rng.normal(0, 1, n) * np.exp(-180 * t) * 0.35     # beater click
    return np.tanh(s * 1.7) * 0.9 * vel


def snare(vel=1.0):
    n = int(0.26 * SR)
    t = np.arange(n) / SR
    body = (np.sin(2 * np.pi * 195 * t) + np.sin(2 * np.pi * 278 * t)) * np.exp(-26 * t)
    nz = bandpass(rng.normal(0, 1, n), 900, 8500) * np.exp(-19 * t)
    return np.tanh((0.5 * body + 1.15 * nz) * 1.3) * 0.72 * vel


def hat(vel=1.0, open_=False):
    n = int((0.20 if open_ else 0.055) * SR)
    t = np.arange(n) / SR
    s = highpass(rng.normal(0, 1, n), 7000) * np.exp(-(9 if open_ else 55) * t)
    return s * 0.34 * vel


def crash(vel=1.0, dur=1.6):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = highpass(rng.normal(0, 1, n), 3500) * np.exp(-3.0 * t)
    s += highpass(rng.normal(0, 1, n), 900) * np.exp(-7.0 * t) * 0.5
    return s * 0.46 * vel


def timpani(m, vel=1.0, dur=0.85):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = midi(m)
    ph = 2 * np.pi * np.cumsum(f * (1 + 0.18 * np.exp(-30 * t))) / SR
    s = np.sin(ph) * np.exp(-5.0 * t)
    s += rng.normal(0, 1, n) * np.exp(-70 * t) * 0.25
    return lowpass(s, 1400) * 0.85 * vel


# ---------------------------------------------------------------- SFX
def whoosh(dur=0.7, lo=250, hi=4200, vel=1.0, rev=False):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    nz = rng.normal(0, 1, n)
    out = np.zeros(n)
    steps = 9
    for i in range(steps):
        a, b = i / steps, (i + 1) / steps
        seg = slice(int(a * n), int(b * n))
        k = (1 - (a + b) / 2) if rev else (a + b) / 2
        f = lo * (hi / lo) ** k
        out[seg] = bandpass(nz[seg], f * 0.55, f * 1.9)
    env = np.sin(np.pi * t) ** 1.4
    return out * env * 0.55 * vel


def boom(vel=1.0, dur=2.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(78 * np.exp(-4.5 * t) + 32) / SR) * np.exp(-2.6 * t)
    body = lowpass(rng.normal(0, 1, n), 420) * np.exp(-3.2 * t)
    crackle = bandpass(rng.normal(0, 1, n), 900, 7000) * np.exp(-9.0 * t) * 0.55
    debris = bandpass(rng.normal(0, 1, n), 1500, 9000) * np.exp(-1.6 * t) * 0.16
    s = 1.25 * sub + 1.0 * body + crackle + debris
    return np.tanh(s * 1.25) * 0.85 * vel


def sizzle(dur=0.6, vel=1.0):
    """Burning liquid / fuse ignition."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = bandpass(rng.normal(0, 1, n), 1200, 9000) * np.exp(-4.5 * t)
    s += bandpass(rng.normal(0, 1, n), 200, 900) * np.exp(-9.0 * t) * 0.8
    return s * 0.6 * vel


def rocket(dur=1.8, vel=1.0):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    nz = rng.normal(0, 1, n)
    low = lowpass(nz, 380) * 1.0
    mid = bandpass(nz, 500, 3000) * 0.7
    s = (low + mid) * (0.35 + 0.65 * np.sin(np.pi * np.clip(t * 1.25, 0, 1)) ** 0.8)
    # doppler-ish rise
    s *= (1.0 + 0.4 * t)
    return s * 0.45 * vel


def sparkle_fx(vel=1.0):
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for i, f in enumerate([1760, 2349, 2637, 3520, 4186]):
        st = int(i * 0.045 * SR)
        m = n - st
        tt = np.arange(m) / SR
        s[st:] += np.sin(2 * np.pi * f * tt) * np.exp(-9 * tt) * (0.7 ** i)
    return s * 0.35 * vel


# ---------------------------------------------------------------- arrangement
# chord per bar: (root midi for bass, chord tones for guitar/strings)
D, F, A, Bb, C, E, G = 62, 65, 69, 70, 72, 64, 67
BARS = [
    ("Dm", 38, [D, F, A]),      # bar 0  0.0 - 1.5   intro build
    ("Dm", 38, [D, F, A]),      # bar 1  1.5 - 3.0   attack
    ("Dm", 38, [D, F, A]),      # bar 2  3.0 - 4.5   explosion
    ("Bb", 34, [Bb, D, F]),     # bar 3  4.5 - 6.0   "I'm Pea Bomber!"
    ("C",  36, [C, E, G]),      # bar 4  6.0 - 7.5   happy birthday
    ("Dm", 38, [D, F, A]),      # bar 5  7.5 - 9.0
    ("Bb", 34, [Bb, D, F]),     # bar 6  9.0 - 10.5
    ("Dm", 38, [D, F, A]),      # bar 7 10.5 - 11.25 finale
]

# ---- brass melody: (start_beat, dur_beats, midi, velocity)
MELODY = [
    (4.00, 0.75, 69, 1.00), (4.75, 0.25, 70, 0.85), (5.00, 0.50, 69, 0.95),
    (5.50, 0.50, 65, 0.90), (6.00, 1.00, 74, 1.05), (7.00, 0.50, 72, 0.95),
    (7.50, 0.50, 69, 0.95),
    # bar 2 - the explosion
    (8.00, 1.50, 74, 1.15), (9.50, 0.50, 72, 1.00), (10.00, 0.50, 69, 1.00),
    (10.50, 0.50, 74, 1.05), (11.00, 1.00, 77, 1.15),
    # bar 3 - dialogue starts, brass eases back
    (12.00, 1.00, 77, 0.72), (13.00, 0.50, 74, 0.66), (13.50, 0.50, 77, 0.66),
    (14.00, 1.00, 70, 0.70), (15.00, 1.00, 69, 0.68),
    # bar 4 - happy birthday
    (16.00, 1.00, 67, 0.70), (17.00, 0.50, 69, 0.68), (17.50, 0.50, 72, 0.72),
    (18.00, 2.00, 76, 0.80),
    # bar 5 - cut accent on beat 22 (8.25 s)
    (20.00, 1.00, 74, 0.95), (21.00, 0.50, 77, 0.90), (21.50, 0.50, 76, 0.90),
    (22.00, 1.00, 74, 1.05), (23.00, 0.50, 69, 0.90), (23.50, 0.50, 70, 0.90),
    # bar 6 - blast off on beat 26 (9.75 s)
    (24.00, 1.00, 70, 1.00), (25.00, 1.00, 74, 1.00), (26.00, 1.00, 72, 1.15),
    (27.00, 0.50, 76, 1.05), (27.50, 0.50, 79, 1.10),
    # bar 7 - finale
    (28.00, 2.00, 81, 1.20),
]

BELLS = [  # birthday glockenspiel sparkle (bars 3-4)
    (16.00, 1.0, 86), (16.50, 1.0, 89), (17.00, 1.0, 91), (17.50, 1.0, 93),
    (18.00, 1.0, 89), (18.50, 1.0, 93), (19.00, 1.5, 96),
    (14.00, 1.0, 82), (14.50, 1.0, 86), (15.00, 1.0, 89),
]

print("arranging ...")

# --- brass
for st, dl, m, v in MELODY:
    add(mix_music, brass(m, dl + 0.10, v), b2s(st), 0.62)
    add(mix_music, brass(m + 12, dl + 0.10, v * 0.30), b2s(st), 0.20)   # octave over, air
    add(mix_music, brass(m - 12, dl + 0.10, v * 0.40), b2s(st), 0.20)   # octave under

# --- bells
for st, dl, m in BELLS:
    add(mix_music, bell(m, dl, 0.9), b2s(st), 0.30)

# --- rhythm section, bar by bar
for bi, (name, broot, tones) in enumerate(BARS):
    b0 = bi * 4
    if bi == 0:
        # intro: timpani + snare roll crescendo + riser
        add(mix_music, timpani(38, 1.0), b2s(0.0), 0.85)
        add(mix_music, timpani(38, 0.8), b2s(2.0), 0.75)
        add(mix_music, timpani(45, 0.9), b2s(3.0), 0.75)
        add(mix_music, crash(0.9, 1.8), b2s(0.0), 0.75)
        add(mix_music, brass(50, 0.9, 1.0), b2s(0.0), 0.40)
        roll = 16
        for k in range(roll):
            t = 2.0 + k * (2.0 / roll)
            add(mix_music, snare(0.16 + 0.80 * (k / roll)), b2s(t), 0.60)
        add(mix_music, whoosh(1.5, 200, 5200, 1.0), b2s(2.0), 0.55)
        continue

    # bass: driving eighths
    for k in range(8):
        v = 1.0 if k % 2 == 0 else 0.78
        add(mix_music, bass(broot, 0.48, v), b2s(b0 + k * 0.5), 0.34)
    # guitar: palm-muted eighths, accent on the downbeat
    for k in range(8):
        v = 1.0 if k in (0, 3, 6) else 0.72
        add(mix_music, gtr(broot + 12, 0.46, v), b2s(b0 + k * 0.5), 0.26)
    # strings: sixteenth ostinato
    for k in range(16):
        m = tones[k % len(tones)] + 12
        add(mix_music, strings(m, 0.22, 0.55 if k % 2 else 0.75), b2s(b0 + k * 0.25), 0.15)
    # sustained brass pad on the big bars
    if bi in (2, 7):
        for m in tones:
            add(mix_music, brass(m, 2.0, 0.55), b2s(b0), 0.16)

    # drum kit
    for k in range(8):
        add(mix_music, hat(0.85 if k % 2 == 0 else 0.6, open_=(k == 7)), b2s(b0 + k * 0.5), 0.55)
    for k in (0.0, 0.75, 1.5, 2.5, 3.25):
        add(mix_music, kick(1.0), b2s(b0 + k), 0.80)
    for k in (1.0, 3.0):
        add(mix_music, snare(1.0), b2s(b0 + k), 0.70)
    if bi in (2, 5, 6, 7):                      # crashes on the cut accents
        add(mix_music, crash(1.0 if bi == 2 else 0.8, 1.8), b2s(b0), 0.70)
    if bi == 5:                                  # accent on beat 22 (8.25 s)
        add(mix_music, crash(0.7, 1.2), b2s(22.0), 0.55)
        add(mix_music, snare(1.0), b2s(22.0), 0.70)
    if bi == 6:                                  # accent on beat 26 (9.75 s)
        add(mix_music, crash(0.9, 1.5), b2s(26.0), 0.65)
        add(mix_music, timpani(38, 0.9), b2s(26.0), 0.55)
    if bi == 2:
        add(mix_music, timpani(38, 1.0), b2s(8.0), 0.80)
    if bi == 7:                                  # final hit
        add(mix_music, timpani(38, 1.0, 1.4), b2s(28.0), 0.90)
        add(mix_music, kick(1.1), b2s(28.0), 0.90)

    # fills
    if bi == 1:
        for k, m in enumerate([0.0, 0.25, 0.5, 0.75]):
            add(mix_music, snare(0.55 + 0.15 * k), b2s(b0 + 3.0 + m), 0.55)
    if bi == 6:
        for k, m in enumerate([0.0, 0.25, 0.5, 0.75]):
            add(mix_music, snare(0.6 + 0.13 * k), b2s(b0 + 3.0 + m), 0.60)

# ---------------------------------------------------------------- sfx track
print("sfx ...")
add(mix_sfx, whoosh(0.85, 300, 5200, 1.0), int(0.02 * SR), 0.85)          # entrance
add(mix_sfx, sizzle(0.7, 0.9), int(1.60 * SR), 0.75)                      # liquid spray
add(mix_sfx, sizzle(0.55, 1.0), int(2.05 * SR), 0.85)                     # ignition 1
add(mix_sfx, boom(0.55, 1.2), int(2.09 * SR), 0.70)
add(mix_sfx, sizzle(0.5, 0.9), int(2.48 * SR), 0.80)                      # ignition 2
add(mix_sfx, boom(0.45, 1.0), int(2.52 * SR), 0.60)
add(mix_sfx, boom(1.15, 2.6), int(2.985 * SR), 1.00)                      # THE explosion
add(mix_sfx, whoosh(0.5, 2000, 400, 0.7, rev=True), int(2.80 * SR), 0.55)
add(mix_sfx, sparkle_fx(1.0), int(5.76 * SR), 0.75)                       # birthday sparkle
add(mix_sfx, sparkle_fx(0.6), int(6.10 * SR), 0.45)
add(mix_sfx, whoosh(0.45, 900, 2600, 0.5), int(8.26 * SR), 0.40)          # squirm sting
add(mix_sfx, rocket(1.6, 1.0), int(9.72 * SR), 0.85)                      # blast off
add(mix_sfx, whoosh(1.0, 400, 4800, 0.9), int(9.74 * SR), 0.60)

# ---------------------------------------------------------------- mixdown
print("mixdown ...")


def reverb(x, dur=0.75, wet=0.16, pre=0.02):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = rng.normal(0, 1, n) * np.exp(-5.2 * t)
    ir = lowpass(ir, 5200)
    ir[: int(pre * SR)] = 0
    ir /= np.abs(ir).sum() / 12.0
    L = len(x) + n
    Lf = 1 << (L - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, Lf) * np.fft.rfft(ir, Lf), Lf)[: len(x)]
    return x * (1 - wet) + y * wet


mix_music = reverb(mix_music, 0.8, 0.18)
mix_sfx = reverb(mix_sfx, 1.1, 0.22)

# gentle duck of the music under the dialogue beats so the picture reads
duck = np.ones(N)
for start, end, amt in ((4.55, 8.20, 0.72), (8.30, 9.70, 0.80)):
    a, b = int(start * SR), int(end * SR)
    ramp = int(0.12 * SR)
    duck[a:b] = amt
    duck[a:a + ramp] = np.linspace(1.0, amt, ramp)
    duck[b - ramp:b] = np.linspace(amt, 1.0, ramp)
mix_music *= duck

out = mix_music * 0.90 + mix_sfx * 0.80


def master_eq(x):
    """Tame the sub weight and lift the brass/presence band so the tune reads."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.ones_like(f)
    g *= 1.0 - 0.55 / (1.0 + (f / 70.0) ** 3)              # -7 dB shelf under ~70 Hz
    g *= 1.0 - 0.30 / (1.0 + (f / 200.0) ** 4)             # -3 dB mud scoop
    g *= 1.0 + 0.85 * np.exp(-((np.log2(np.maximum(f, 1)) - np.log2(1500)) ** 2) / 1.6)
    g *= 1.0 + 0.45 * np.exp(-((np.log2(np.maximum(f, 1)) - np.log2(5200)) ** 2) / 1.2)
    return np.fft.irfft(X * g, n)


out = master_eq(out)

# master: soft-clip, high-pass rumble, normalise
out = highpass(out, 38)
out = np.tanh(out * 1.15) * 0.97
peak = np.abs(out).max()
out = out / peak * 0.94

# fades
fi = int(0.02 * SR)
out[:fi] *= np.linspace(0, 1, fi)
fo = int(0.32 * SR)
out[-fo:] *= np.linspace(1, 0, fo) ** 0.8

st = np.stack([out, out], axis=1)          # simple stereo
# tiny width: delay the sides a hair
d = int(0.008 * SR)
st[d:, 1] = st[d:, 1] * 0.88 + out[:-d] * 0.12

pcm = (np.clip(st, -1, 1) * 32767).astype("<i2")

import wave
with wave.open("bgm.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

rms = np.sqrt((out ** 2).mean())
print("wrote bgm.wav  %.2fs  peak=%.3f  rms=%.3f (%.1f dBFS)"
      % (DUR, np.abs(out).max(), rms, 20 * math.log10(rms)))
