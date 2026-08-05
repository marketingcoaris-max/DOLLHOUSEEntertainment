#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
"PLUS BOMBER!! (Battle Ver.)" - original shonen-battle BGM for the short.

Heavier rewrite: palm-muted distorted guitar gallop, double-kick drums,
16th hi-hats, brass fanfare and taiko/timpani hits. D minor, 160 BPM,
9 bars = 13.5 s, accents locked to the picture cuts.
"""
import math
import numpy as np
import wave

SR = 44100
BPM = 160.0
BEAT = 60.0 / BPM               # 0.375 s -> bar = 1.5 s
DUR = 13.5                      # 9 bars, matches the 324-frame cut
N = int(DUR * SR)

rng = np.random.default_rng(31415)
gtr_bus = np.zeros(N)
drum_bus = np.zeros(N)
lead_bus = np.zeros(N)
low_bus = np.zeros(N)
sfx_bus = np.zeros(N)


# ---------------------------------------------------------------- utilities
def b2s(beats):
    return int(beats * BEAT * SR)


def midi(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def add(buf, sig, at, gain=1.0):
    i = int(at)
    if i >= len(buf) or i < 0:
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def env_ad(n, a, d, curve=1.0):
    a = max(1, int(a * SR))
    out = np.ones(n)
    out[:a] = np.linspace(0, 1, a)
    t = np.arange(n) / SR
    out *= np.exp(-t / max(d, 1e-4)) ** curve
    return out


def adsr(n, a, d, s, r):
    a, d, r = max(1, int(a * SR)), max(1, int(d * SR)), max(1, int(r * SR))
    sus = max(0, n - a - d - r)
    e = np.concatenate([np.linspace(0, 1, a), np.linspace(1, s, d),
                        np.full(sus, s), np.linspace(s, 0, r)])
    if len(e) < n:
        e = np.concatenate([e, np.zeros(n - len(e))])
    return e[:n]


def _filt(x, g):
    n = len(x)
    return np.fft.irfft(np.fft.rfft(x) * g(np.fft.rfftfreq(n, 1 / SR)), n)


def lowpass(x, fc, order=4):
    return _filt(x, lambda f: 1.0 / (1.0 + (f / fc) ** order) ** 0.75)


def highpass(x, fc):
    return _filt(x, lambda f: (f / fc) ** 2 / (1.0 + (f / fc) ** 2))


def bandpass(x, lo, hi):
    return lowpass(highpass(x, lo), hi)


def peaking(x, fc, db, q=1.0):
    def g(f):
        lf = np.log2(np.maximum(f, 1.0))
        return 1.0 + (10 ** (db / 20) - 1) * np.exp(-((lf - np.log2(fc)) ** 2) / (2 * (1 / q) ** 2))
    return _filt(x, g)


def saw(freq, n, harm=26, detune=0.0, vib=0.0):
    t = np.arange(n) / SR
    f = freq * 2 ** (detune / 1200.0)
    if vib:
        f = f * (1 + vib * np.clip((t - 0.10) / 0.18, 0, 1) * np.sin(2 * np.pi * 5.4 * t))
    ph = 2 * np.pi * np.cumsum(np.full(n, 0.0) + f) / SR
    out = np.zeros(n)
    k = max(1, min(harm, int(SR * 0.45 / max(freq, 1))))
    for i in range(1, k + 1):
        out += np.sin(i * ph) / i
    return out * (2 / np.pi)


def square(freq, n, harm=20):
    ph = 2 * np.pi * freq * np.arange(n) / SR
    out = np.zeros(n)
    k = max(1, min(harm, int(SR * 0.45 / max(freq, 1))))
    for i in range(1, k + 1, 2):
        out += np.sin(i * ph) / i
    return out * (4 / np.pi) * 0.5


# ---------------------------------------------------------------- guitar
def cab(x):
    """Speaker-cabinet colouring: the thing that makes distortion read as guitar."""
    x = highpass(x, 95)
    x = peaking(x, 240, +2.0, 1.0)
    x = peaking(x, 900, -4.0, 1.2)          # scoop the honk
    x = peaking(x, 2400, +5.5, 1.0)         # bite
    x = lowpass(x, 5200, order=6)           # cone rolloff
    return x


def gtr_note(m, beats, mute=True, vel=1.0, gain=7.0):
    """Palm-muted / open power chord through a distortion + cab chain."""
    n = b2s(beats)
    f = midi(m)
    raw = (saw(f, n, 22) + 0.9 * saw(f * 1.4983, n, 20)      # root + fifth
           + 0.5 * saw(f * 2.0, n, 16) + 0.35 * square(f, n))
    raw = peaking(raw, 700, +4.0, 0.9)                        # pre-gain mid push
    d = np.tanh(raw * gain) * 0.55
    d = cab(d)
    if mute:
        e = env_ad(n, 0.002, 0.055, 1.0) * adsr(n, 0.002, 0.02, 0.55, 0.03)
    else:
        e = adsr(n, 0.004, 0.10, 0.72, 0.08)
    return d * e * vel


def gtr_chug(m, beats, vel=1.0):
    return gtr_note(m, beats, mute=True, vel=vel, gain=9.0)


# ---------------------------------------------------------------- other voices
def brass(m, beats, vel=1.0):
    n = b2s(beats)
    f = midi(m)
    s = (saw(f, n, 24, detune=-8, vib=0.006) + saw(f, n, 24, detune=+8, vib=0.006)
         + 0.55 * saw(f, n, 18))
    s /= 2.6
    nb = min(n, int(0.03 * SR))
    s[:nb] += rng.normal(0, 0.28, nb) * np.linspace(1, 0, nb)
    s = lowpass(s, 2800 + 2400 * vel)
    return s * adsr(n, 0.02, 0.08, 0.86, 0.09) * vel


def bass(m, beats, vel=1.0):
    n = b2s(beats)
    f = midi(m)
    s = 0.85 * saw(f, n, 14) + 0.9 * np.sin(2 * np.pi * f * np.arange(n) / SR)
    s = np.tanh(s * 1.6) * 0.6
    s = lowpass(s, 1100)
    return s * adsr(n, 0.005, 0.06, 0.75, 0.04) * vel


def strings(m, beats, vel=1.0):
    n = b2s(beats)
    f = midi(m)
    s = (saw(f, n, 16, detune=-10) + saw(f, n, 16, detune=+10)) / 2.4
    return lowpass(s, 2400) * adsr(n, 0.010, 0.04, 0.6, 0.04) * vel


# ---------------------------------------------------------------- drums
def kick(vel=1.0):
    n = int(0.26 * SR)
    t = np.arange(n) / SR
    f = 135 * np.exp(-32 * t) + 47
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-15 * t)
    s += rng.normal(0, 1, n) * np.exp(-220 * t) * 0.4
    s = peaking(s, 65, +3.0, 1.2)
    return np.tanh(s * 2.0) * 0.92 * vel


def snare(vel=1.0, crack=1.0):
    n = int(0.24 * SR)
    t = np.arange(n) / SR
    body = (np.sin(2 * np.pi * 200 * t) + np.sin(2 * np.pi * 287 * t)) * np.exp(-27 * t)
    nz = bandpass(rng.normal(0, 1, n), 1100, 9500) * np.exp(-20 * t)
    s = 0.45 * body + 1.25 * nz * crack
    s = peaking(s, 3000, +3.0, 1.0)
    return np.tanh(s * 1.5) * 0.75 * vel


def hat(vel=1.0, open_=False):
    n = int((0.22 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    s = highpass(rng.normal(0, 1, n), 7500) * np.exp(-(8 if open_ else 62) * t)
    return s * 0.30 * vel


def ride(vel=1.0):
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    s = highpass(rng.normal(0, 1, n), 5000) * np.exp(-9 * t) * 0.5
    s += np.sin(2 * np.pi * 830 * t) * np.exp(-16 * t) * 0.25
    return s * 0.34 * vel


def crash(vel=1.0, dur=1.7):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = highpass(rng.normal(0, 1, n), 3200) * np.exp(-2.9 * t)
    s += highpass(rng.normal(0, 1, n), 800) * np.exp(-7 * t) * 0.45
    return s * 0.5 * vel


def taiko(m=36, vel=1.0, dur=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = midi(m)
    s = np.sin(2 * np.pi * np.cumsum(f * (1 + 0.22 * np.exp(-26 * t))) / SR) * np.exp(-5.5 * t)
    s += rng.normal(0, 1, n) * np.exp(-60 * t) * 0.3
    return lowpass(s, 1500) * 0.9 * vel


# ---------------------------------------------------------------- sfx
def whoosh(dur=0.7, lo=250, hi=4200, vel=1.0, rev=False):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    nz = rng.normal(0, 1, n)
    out = np.zeros(n)
    for i in range(9):
        a, b = i / 9, (i + 1) / 9
        seg = slice(int(a * n), int(b * n))
        k = (1 - (a + b) / 2) if rev else (a + b) / 2
        f = lo * (hi / lo) ** k
        out[seg] = bandpass(nz[seg], f * 0.55, f * 1.9)
    return out * np.sin(np.pi * t) ** 1.4 * 0.55 * vel


def boom(vel=1.0, dur=2.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sub = np.sin(2 * np.pi * np.cumsum(82 * np.exp(-4.5 * t) + 31) / SR) * np.exp(-2.5 * t)
    body = lowpass(rng.normal(0, 1, n), 430) * np.exp(-3.0 * t)
    crk = bandpass(rng.normal(0, 1, n), 900, 7000) * np.exp(-8.5 * t) * 0.55
    deb = bandpass(rng.normal(0, 1, n), 1500, 9000) * np.exp(-1.5 * t) * 0.18
    return np.tanh((1.3 * sub + body + crk + deb) * 1.25) * 0.88 * vel


def sizzle(dur=0.6, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = bandpass(rng.normal(0, 1, n), 1200, 9000) * np.exp(-4.5 * t)
    s += bandpass(rng.normal(0, 1, n), 200, 900) * np.exp(-9 * t) * 0.8
    return s * 0.6 * vel


def rocket(dur=1.9, vel=1.0):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    nz = rng.normal(0, 1, n)
    s = (lowpass(nz, 380) + bandpass(nz, 500, 3000) * 0.7)
    s *= (0.35 + 0.65 * np.sin(np.pi * np.clip(t * 1.25, 0, 1)) ** 0.8) * (1 + 0.45 * t)
    return s * 0.46 * vel


# ---------------------------------------------------------------- arrangement
D2, D3, A3, Bb2, C3, F3, G2 = 38, 50, 57, 34, 36, 41, 31
# bar -> (guitar/bass root, chord tones for strings/brass pads)
BARS = [
    (38, [62, 65, 69]),   # 0  0.0- 1.5  Dm   intro
    (38, [62, 65, 69]),   # 1  1.5- 3.0  Dm   ignition
    (38, [62, 65, 69]),   # 2  3.0- 4.5  Dm   EXPLOSION
    (34, [58, 62, 65]),   # 3  4.5- 6.0  Bb   "I'm Pea Bomber!"
    (36, [60, 64, 67]),   # 4  6.0- 7.5  C    "Yo Kori!"
    (34, [58, 62, 65]),   # 5  7.5- 9.0  Bb   "Happy birthday!"
    (36, [60, 64, 67]),   # 6  9.0-10.5  C    "Take care of me!"
    (38, [62, 65, 69]),   # 7 10.5-12.0  Dm   panic
    (38, [62, 65, 69]),   # 8 12.0-13.5  Dm   blast off
]

# ducking: dialogue windows where the band steps back
DUCK = [(4.55, 5.98, 0.60), (5.98, 7.06, 0.62), (7.02, 8.52, 0.60),
        (8.52, 10.10, 0.60), (10.24, 11.15, 0.52), (11.16, 12.12, 0.48)]

# brass fanfare (start_beat, dur_beats, midi, vel)
MELODY = [
    (4.0, 0.75, 69, 1.00), (4.75, 0.25, 70, 0.85), (5.0, 0.5, 69, 0.95),
    (5.5, 0.5, 65, 0.90), (6.0, 1.0, 74, 1.05), (7.0, 0.5, 72, 0.95),
    (7.5, 0.5, 69, 0.95),
    (8.0, 1.5, 74, 1.20), (9.5, 0.5, 72, 1.05), (10.0, 0.5, 69, 1.05),
    (10.5, 0.5, 74, 1.10), (11.0, 1.0, 77, 1.20),
    # dialogue bars: sparse punctuation only, so the voice owns the middle
    (12.0, 0.5, 74, 0.42), (15.0, 1.0, 70, 0.40),
    (18.0, 0.5, 72, 0.40), (21.0, 1.0, 74, 0.42),
    (24.0, 0.5, 72, 0.40), (27.0, 1.0, 76, 0.45),
    # panic bar
    (28.0, 0.5, 69, 0.55), (29.0, 0.5, 70, 0.55),
    # finale
    (32.0, 1.0, 81, 1.20), (33.0, 0.5, 79, 1.10), (33.5, 0.5, 81, 1.15),
    (34.0, 2.0, 86, 1.25),
]

print("arranging ...")

for st, dl, m, v in MELODY:
    add(lead_bus, brass(m, dl + 0.08, v), b2s(st), 0.62)
    add(lead_bus, brass(m + 12, dl + 0.08, v * 0.28), b2s(st), 0.18)
    add(lead_bus, brass(m - 12, dl + 0.08, v * 0.38), b2s(st), 0.18)

# 16th gallop riff pattern (1 = chug, 2 = accent chord, 0 = rest)
RIFF_HEAVY = [2, 1, 1, 2, 0, 1, 2, 1, 2, 1, 1, 2, 0, 1, 1, 1]
RIFF_LIGHT = [2, 0, 0, 1, 0, 0, 2, 0, 2, 0, 0, 1, 0, 0, 1, 0]

for bi, (root, tones) in enumerate(BARS):
    b0 = bi * 4
    heavy = bi in (1, 2, 7, 8)

    if bi == 0:
        # intro: taiko + snare roll crescendo + riser, no riff yet
        add(drum_bus, taiko(36, 1.0, 1.2), b2s(0.0), 0.95)
        add(drum_bus, crash(0.95, 1.9), b2s(0.0), 0.80)
        add(lead_bus, brass(50, 0.9, 1.0), b2s(0.0), 0.45)
        add(low_bus, bass(38, 1.0, 1.0), b2s(0.0), 0.55)
        add(drum_bus, taiko(36, 0.85, 0.9), b2s(2.0), 0.80)
        add(drum_bus, taiko(43, 0.85, 0.8), b2s(3.0), 0.75)
        for k in range(16):
            add(drum_bus, snare(0.14 + 0.85 * (k / 16), crack=0.9), b2s(2.0 + k * 0.125), 0.55)
        add(sfx_bus, whoosh(1.5, 200, 5400, 1.0), b2s(2.0), 0.55)
        continue

    riff = RIFF_HEAVY if heavy else RIFF_LIGHT
    gv = 1.0 if heavy else 0.62
    for k, step in enumerate(riff):
        if step == 0:
            continue
        at = b2s(b0 + k * 0.25)
        if step == 2:
            add(gtr_bus, gtr_note(root + 12, 0.30, mute=False, vel=1.0 * gv), at, 0.34)
        else:
            add(gtr_bus, gtr_chug(root + 12, 0.22, vel=0.85 * gv), at, 0.30)

    # bass follows the riff in eighths
    for k in range(8):
        add(low_bus, bass(root, 0.46, 1.0 if k % 2 == 0 else 0.8), b2s(b0 + k * 0.5), 0.44)

    # strings ostinato keeps the orchestral half alive
    for k in range(16):
        m = tones[k % len(tones)] + 12
        add(lead_bus, strings(m, 0.20, 0.5 if k % 2 else 0.7), b2s(b0 + k * 0.25),
            0.13 if heavy else 0.09)

    # ---- kit
    if heavy:
        for k in (0.0, 0.25, 0.75, 1.0, 1.5, 1.75, 2.0, 2.5, 2.75, 3.0, 3.5, 3.75):
            add(drum_bus, kick(1.0), b2s(b0 + k), 0.78)       # double-kick drive
    else:
        for k in (0.0, 0.75, 1.5, 2.0, 2.75, 3.5):
            add(drum_bus, kick(0.95), b2s(b0 + k), 0.70)
    for k in (1.0, 3.0):
        add(drum_bus, snare(1.0), b2s(b0 + k), 0.74)
    if heavy:
        add(drum_bus, snare(0.55, crack=0.7), b2s(b0 + 2.5), 0.40)
    for k in range(16):                                       # 16th hats
        v = 1.0 if k % 4 == 0 else (0.62 if k % 2 == 0 else 0.42)
        add(drum_bus, hat(v, open_=(k == 14)), b2s(b0 + k * 0.25), 0.5 if heavy else 0.36)
    if not heavy:
        for k in range(8):
            add(drum_bus, ride(0.5 if k % 2 else 0.75), b2s(b0 + k * 0.5), 0.30)

    if bi in (2, 8):
        add(drum_bus, crash(1.0, 1.9), b2s(b0), 0.78)
        add(drum_bus, taiko(36, 1.0, 1.1), b2s(b0), 0.80)
    if bi in (3, 7):
        add(drum_bus, crash(0.62, 1.2), b2s(b0), 0.48)
    # fills into the big moments
    if bi in (1, 7):
        for k, off in enumerate([0.0, 0.25, 0.5, 0.75]):
            add(drum_bus, snare(0.55 + 0.16 * k), b2s(b0 + 3.0 + off), 0.58)
    if bi == 8:
        add(drum_bus, taiko(36, 1.0, 1.4), b2s(34.0), 0.95)
        add(drum_bus, crash(1.0, 2.0), b2s(34.0), 0.80)
        add(drum_bus, kick(1.1), b2s(34.0), 0.85)

# ---------------------------------------------------------------- sfx cues
print("sfx ...")
add(sfx_bus, whoosh(0.85, 300, 5200, 1.0), int(0.02 * SR), 0.85)
add(sfx_bus, sizzle(0.7, 0.9), int(1.58 * SR), 0.75)
add(sfx_bus, sizzle(0.55, 1.0), int(2.05 * SR), 0.85)
add(sfx_bus, boom(0.5, 1.2), int(2.09 * SR), 0.65)
add(sfx_bus, sizzle(0.5, 0.9), int(2.48 * SR), 0.80)
add(sfx_bus, boom(0.42, 1.0), int(2.52 * SR), 0.55)
add(sfx_bus, whoosh(0.5, 2000, 400, 0.7, rev=True), int(2.80 * SR), 0.55)
add(sfx_bus, boom(1.15, 2.8), int(2.985 * SR), 1.00)          # the big one
add(sfx_bus, whoosh(0.4, 700, 2400, 0.45), int(10.22 * SR), 0.35)   # panic sting
add(sfx_bus, rocket(1.7, 1.0), int(12.06 * SR), 0.85)         # blast off
add(sfx_bus, whoosh(1.0, 400, 5000, 0.9), int(12.08 * SR), 0.60)

# ---------------------------------------------------------------- mixdown
print("mixdown ...")


def reverb(x, dur=0.8, wet=0.16, pre=0.02, damp=5200):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = lowpass(rng.normal(0, 1, n) * np.exp(-5.0 * t), damp)
    ir[: int(pre * SR)] = 0
    ir /= np.abs(ir).sum() / 12.0
    L = 1 << (len(x) + n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, L) * np.fft.rfft(ir, L), L)[: len(x)]
    return x * (1 - wet) + y * wet


gtr_bus = reverb(gtr_bus, 0.5, 0.10)
lead_bus = reverb(lead_bus, 0.9, 0.20)
drum_bus = reverb(drum_bus, 0.55, 0.11)
sfx_bus = reverb(sfx_bus, 1.1, 0.20)

band = gtr_bus * 0.92 + drum_bus * 0.85 + lead_bus * 0.80 + low_bus * 0.85

# duck the band under each spoken line
duck = np.ones(N)
ramp = int(0.10 * SR)
for a_s, b_s, amt in DUCK:
    a, b = int(a_s * SR), int(b_s * SR)
    duck[a:b] = np.minimum(duck[a:b], amt)
    duck[a:a + ramp] = np.minimum(duck[a:a + ramp], np.linspace(1.0, amt, ramp))
    duck[max(0, b - ramp):b] = np.maximum(duck[max(0, b - ramp):b], np.linspace(amt, 1.0, ramp))
# smooth the duck curve so it does not pump
kern = np.hanning(int(0.06 * SR))
kern /= kern.sum()
duck = np.convolve(duck, kern, mode="same")
band *= duck

out = band + sfx_bus * 0.85


def master_eq(x):
    def g(f):
        lf = np.log2(np.maximum(f, 1.0))
        k = np.ones_like(f)
        k *= 1.0 - 0.50 / (1.0 + (f / 68.0) ** 3)
        k *= 1.0 - 0.26 / (1.0 + (f / 210.0) ** 4)
        k *= 1.0 + 0.70 * np.exp(-((lf - np.log2(1600)) ** 2) / 1.6)
        k *= 1.0 + 0.40 * np.exp(-((lf - np.log2(5000)) ** 2) / 1.2)
        return k
    return _filt(x, g)


out = master_eq(out)
out = highpass(out, 36)
out = np.tanh(out * 1.18) * 0.97
out /= np.abs(out).max()
out *= 0.93

fi, fo = int(0.02 * SR), int(0.30 * SR)
out[:fi] *= np.linspace(0, 1, fi)
out[-fo:] *= np.linspace(1, 0, fo) ** 0.8

st = np.stack([out, out], axis=1)
d = int(0.008 * SR)
st[d:, 1] = st[d:, 1] * 0.88 + out[:-d] * 0.12

with wave.open("bgm2.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes((np.clip(st, -1, 1) * 32767).astype("<i2").tobytes())

rms = np.sqrt((out ** 2).mean())
print("wrote bgm2.wav  %.2fs  peak=%.3f  rms=%.3f (%.1f dBFS)"
      % (DUR, np.abs(out).max(), rms, 20 * math.log10(rms)))
