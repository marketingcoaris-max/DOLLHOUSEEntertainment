"""Builds the 15 s soundtrack: Japanese voiceover (Open JTalk), 132 BPM music and synced SFX.

usage: python3 audio.py out.wav
"""
import sys
import numpy as np
import pyopenjtalk
from scipy import signal

SR = 48000
DUR = 15.0
N = int(SR * DUR)
rng = np.random.default_rng(7)


def tt(d):
    return np.arange(int(d * SR)) / SR


def place(buf, x, t0, gain=1.0):
    i = int(round(t0 * SR))
    if i >= len(buf):
        return
    j = min(len(buf), i + len(x))
    buf[i:j] += gain * x[: j - i]


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, hi], 'band', fs=SR, output='sos'), x)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'high', fs=SR, output='sos'), x)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'low', fs=SR, output='sos'), x)


def sweep_noise(d, f0, f1, q=3.0):
    """Noise through a band-pass whose centre glides from f0 to f1 (processed in short blocks)."""
    n = rng.standard_normal(int(d * SR))
    out = np.zeros_like(n)
    blk = 256
    zi = None
    for k in range(0, len(n), blk):
        p = k / len(n)
        fc = f0 * (f1 / f0) ** p
        bw = fc / q
        sos = signal.butter(2, [max(20, fc - bw / 2), min(SR / 2 - 100, fc + bw / 2)], 'band', fs=SR, output='sos')
        if zi is None:
            zi = signal.sosfilt_zi(sos) * 0
        out[k:k + blk], zi = signal.sosfilt(sos, n[k:k + blk], zi=zi)
    return out


# ---------------- SFX ----------------
def glass_tick(g=1.0):
    t = tt(0.12)
    x = (np.sin(2 * np.pi * 2900 * t) * 0.6 + np.sin(2 * np.pi * 5300 * t) * 0.35 + np.sin(2 * np.pi * 7900 * t) * 0.15) * np.exp(-t * 55)
    x += hp(rng.standard_normal(len(t)), 4000) * np.exp(-t * 400) * 0.4
    return x * g


def sub_hit(g=1.0, f0=70, f1=36, d=0.7):
    t = tt(d)
    f = f1 + (f0 - f1) * np.exp(-t * 9)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t * 4.5)
    x += lp(rng.standard_normal(len(t)), 300) * np.exp(-t * 18) * 0.5
    return x * g


def ui_snap(g=1.0, f=1400):
    t = tt(0.07)
    x = bp(rng.standard_normal(len(t)), 2000, 6000) * np.exp(-t * 160) * 0.8
    x += np.sin(2 * np.pi * f * t) * np.exp(-t * 90) * 0.6
    x += np.sin(2 * np.pi * 180 * t) * np.exp(-t * 60) * 0.5
    return x * g


def whoosh(d, f0, f1, g=1.0, shape=0.5):
    x = sweep_noise(d, f0, f1, q=2.0)
    t = tt(d)[: len(x)]
    env = np.sin(np.pi * np.clip(t / d, 0, 1) ** shape) ** 2
    return x * env * g


def pulse(g=1.0, f=220, d=0.25):
    t = tt(d)
    sq = np.sign(np.sin(2 * np.pi * f * t)) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 37 * t)))
    return lp(sq, 2500) * np.exp(-t * 14) * g


def zap(d=0.6, g=1.0):
    t = tt(d)
    f = 300 + 2600 * (t / d) ** 1.5
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.4 + sweep_noise(d, 800, 7000, 4) * 0.8
    return x * np.sin(np.pi * t / d) ** 2 * g


def chime(g=1.0):
    t = tt(1.6)
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t * dcy) for f, a, dcy in [(1568, .5, 3), (2349, .35, 3.6), (3136, .25, 4.2), (4699, .12, 6)])
    return x * g


def data_sweep(d, g=1.0):
    t = tt(d)
    f = 600 * (8 ** (t / d))
    x = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.15 + sweep_noise(d, 900, 6000, 5)
    return lp(x, 9000) * np.sin(np.pi * t / d) ** 2 * g


sfx = np.zeros(N)
place(sfx, whoosh(0.5, 6000, 900, 0.5), 0.0)
for i in range(7):
    place(sfx, glass_tick(0.25), 0.02 + i * 0.034 + 0.26)
place(sfx, glass_tick(0.5), 0.55)
place(sfx, pulse(0.35, 330), 0.85)
place(sfx, whoosh(0.55, 400, 5000, 0.9, 0.7), 1.33)
place(sfx, glass_tick(0.8), 1.78)
place(sfx, sub_hit(0.5, 80, 45, 0.4), 1.78)
place(sfx, data_sweep(0.45, 0.25), 2.0)
place(sfx, zap(0.62, 0.35), 2.4)
place(sfx, whoosh(0.4, 600, 4000, 0.5), 2.88)
place(sfx, glass_tick(0.5), 3.05)
for i, t0 in enumerate([3.2, 3.28, 3.36]):
    place(sfx, ui_snap(0.55, 1300 + i * 250), t0)
place(sfx, whoosh(0.3, 300, 6000, 0.7, 0.9), 4.38)
place(sfx, sub_hit(0.75), 4.65)
place(sfx, glass_tick(0.4), 4.7)
place(sfx, whoosh(0.35, 3000, 600, 0.35), 4.95)
place(sfx, ui_snap(0.5, 1000), 5.3)
place(sfx, ui_snap(0.45, 1500), 5.43)
for i in range(3):
    place(sfx, ui_snap(0.35, 1700 + i * 200), 5.52 + i * 0.06)
place(sfx, pulse(0.3, 440, 0.15), 5.6)
place(sfx, data_sweep(0.35, 0.25), 5.66)
place(sfx, zap(0.3, 0.3), 5.95)
place(sfx, whoosh(0.42, 500, 7000, 0.8, 0.8), 6.15)
place(sfx, glass_tick(0.6), 6.56)
place(sfx, pulse(0.35, 520, 0.2), 6.85)
for i in range(3):
    place(sfx, glass_tick(0.3), 6.95 + i * 0.08)
place(sfx, sub_hit(0.9, 90, 32, 0.9), 7.85)
for i, t0 in enumerate([8.2, 8.4, 8.6]):
    place(sfx, ui_snap(0.5, 1100 + 200 * i), t0)
place(sfx, ui_snap(0.4, 1900), 8.7)
place(sfx, sub_hit(0.85, 60, 30, 1.0), 8.72)   # Jev = ... reveal: low hit
place(sfx, chime(0.32), 8.74)                  # + clean high chime
place(sfx, whoosh(0.5, 2500, 500, 0.35), 9.35)
place(sfx, glass_tick(0.3), 9.52)
place(sfx, glass_tick(0.3), 9.7)
place(sfx, data_sweep(0.5, 0.22), 10.0)
place(sfx, glass_tick(0.35), 10.5)
place(sfx, whoosh(0.6, 800, 3000, 0.3), 12.0)
for i, t0 in enumerate([12.6, 12.7, 12.8, 12.9]):
    place(sfx, ui_snap(0.22, 1500 + 150 * i), t0)
place(sfx, data_sweep(0.5, 0.15), 13.3)
place(sfx, glass_tick(0.35), 13.8)

# ---------------- music (132 BPM) ----------------
BPM = 132
B = 60 / BPM
S16 = B / 4
mus = np.zeros(N)


def kick(g=1.0):
    t = tt(0.4)
    f = 45 + 110 * np.exp(-t * 32)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 8)
    x += np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 400) * 0.15
    return np.tanh(x * 1.6) * g


def hat(g=1.0):
    t = tt(0.05)
    return hp(rng.standard_normal(len(t)), 8000) * np.exp(-t * 120) * g


def perc(g=1.0):
    t = tt(0.16)
    return (bp(rng.standard_normal(len(t)), 900, 3200) * np.exp(-t * 45) * 0.8 + np.sin(2 * np.pi * 210 * t) * np.exp(-t * 35) * 0.5) * g


def click(g=1.0, f=4200):
    t = tt(0.01)
    return np.sin(2 * np.pi * f * t) * np.exp(-t * 700) * g


def bass(f, d, g=1.0):
    t = tt(d)
    x = signal.sawtooth(2 * np.pi * f * t) * 0.5 + np.sin(2 * np.pi * f * t)
    x = lp(x, 260 + 900 * np.exp(-0.0)) * np.exp(-t * 7)
    return np.tanh(x * 1.4) * g


def pad(freqs, d, g=1.0, bright=1200):
    t = tt(d)
    x = np.zeros(len(t))
    for f in freqs:
        for det in (-0.12, 0, 0.11):
            x += signal.sawtooth(2 * np.pi * f * (1 + det / 100 * 3) * t + rng.uniform(0, 6))
    x = lp(x / (len(freqs) * 3), bright, 2)
    att = np.clip(t / 0.25, 0, 1)
    rel = np.clip((d - t) / 0.3, 0, 1)
    return x * att * rel * g


Am9 = [110, 130.81, 164.81, 196.0, 246.94]
Fmaj9 = [87.31, 130.81, 164.81, 196.0, 220.0]
Cmaj9 = [130.81, 164.81, 196.0, 246.94, 293.66, 392.0]
G6 = [98.0, 146.83, 196.0, 246.94, 329.63]

place(mus, pad(Am9, 3.7, 0.5, 900), 0.0)
place(mus, pad(Fmaj9, 4.0, 0.5, 1100), 3.64)
place(mus, pad(Am9, 2.9, 0.55, 1600), 7.85)
place(mus, pad(Fmaj9, 1.5, 0.55, 1600), 10.7)
place(mus, pad(G6, 1.2, 0.55, 1800), 12.15)
place(mus, pad(Cmaj9, 1.9, 0.75, 2600), 13.3)  # harmonic lift under the end card

steps = int(DUR / S16) + 1
for k in range(steps):
    t0 = k * S16
    beat, sub = divmod(k, 4)
    in_groove = 1.4 <= t0 < 7.6 or 7.85 <= t0 < 13.3
    dense = t0 >= 7.85
    root = 55.0 if (t0 < 3.64 or 7.85 <= t0 < 10.7) else (43.65 if t0 < 12.15 else 49.0)
    if in_groove:
        if sub == 0:
            place(mus, kick(0.9 if dense else 0.7), t0)
        if sub == 2:
            place(mus, bass(root, S16 * 1.8, 0.55 if dense else 0.4), t0)
        if dense and sub == 3 and beat % 2 == 1:
            place(mus, bass(root * 2, S16 * 0.9, 0.25), t0)
        if beat % 2 == 1 and sub == 0:
            place(mus, perc(0.32), t0)
        hg = [0.18, 0.08, 0.3, 0.1][sub] * (1.3 if dense else 1.0)
        if dense or t0 > 4.65 or sub == 2:
            place(mus, hat(hg), t0)
        if (k * 7) % 5 == 0:
            place(mus, click(0.18, 3800 + 400 * (k % 3)), t0 + S16 * 0.5)
    elif t0 < 1.4 and sub in (0, 3) and beat % 2 == 0:
        place(mus, click(0.18, 4200), t0)
    elif t0 >= 13.3 and sub == 0 and beat % 2 == 0:
        place(mus, click(0.12, 3600), t0)
# glitch stutters
for t0 in (3.62, 6.12, 9.08, 11.8):
    for i in range(4):
        place(mus, click(0.2, 2400 + 600 * i), t0 + i * S16 / 2)
# build + drop at 7.85
place(mus, sweep_noise(0.75, 300, 9000, 3) * np.linspace(0, 1, int(0.75 * SR)) ** 2 * 0.35, 7.08)
place(mus, kick(1.0), 7.85)
place(mus, sub_hit(0.6, 55, 40, 1.4), 7.85)
place(mus, hp(rng.standard_normal(int(1.2 * SR)), 5000) * np.exp(-tt(1.2) * 4) * 0.12, 7.85)
# final resolution hit
place(mus, kick(0.6), 13.3)
place(mus, sub_hit(0.3, 50, 41, 1.5), 13.3)

# ---------------- voiceover ----------------
VO = [
    (0.25, 1.25, ['ジェブって何？']),
    (1.55, 4.30, ['たとえば', '「請求が二重です」。', 'どの担当に送る？']),
    (4.55, 7.80, ['ジェブは', '用意された選択肢から判断し', '確率と一緒に返します。']),
    (7.96, 11.80, ['選択肢', 'はい', 'いいえ', '点数。', '文章を書くより', '判断するためのエーアイ。']),
    (12.05, 14.10, ['それが', 'ジェブです。']),
]


def trim(x):
    a = np.abs(x) > 250
    i = np.argmax(a)
    j = len(a) - np.argmax(a[::-1])
    return x[max(0, i - 240):j + 600]


def say(chunks, speed):
    parts = []
    for c in chunks:
        x, sr = pyopenjtalk.tts(c, speed=speed, half_tone=0.5)
        assert sr == SR
        parts.append(trim(x.astype(np.float64)))
        gap = 0.12 if c.endswith('。') else 0.05
        parts.append(np.zeros(int(gap / speed * SR)))
    return np.concatenate(parts[:-1])


vo = np.zeros(N)
vo_env = np.zeros(N)


def tempo(x, r):
    """Pitch-preserving time compression via ffmpeg atempo."""
    import subprocess, tempfile, os
    from scipy.io import wavfile as wf
    d = tempfile.mkdtemp()
    wf.write(os.path.join(d, 'i.wav'), SR, (x / (np.max(np.abs(x)) + 1e-9) * 30000).astype(np.int16))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(d, 'i.wav'), '-af', f'atempo={r:.4f}', os.path.join(d, 'o.wav')], check=True)
    return wf.read(os.path.join(d, 'o.wav'))[1].astype(np.float64)


for t0, t1, chunks in VO:
    x = say(chunks, 1.1)
    r = len(x) / SR / (t1 - t0)
    if r > 1:
        x = tempo(x, r)
    print(f'VO {t0:5.2f}-{t1:5.2f} tempo x{max(r,1)*1.1:.2f} len {len(x)/SR:.2f}s  {"".join(chunks)}')
    x = x / (np.max(np.abs(x)) + 1e-9)
    place(vo, x, t0)
    place(vo_env, np.ones(len(x)), t0)

# voice polish: gentle low cut and presence lift
vo = hp(vo, 90)
vo = vo + 0.25 * bp(vo, 2500, 6000)

# ---------------- mix ----------------
duck = np.convolve(vo_env, np.ones(int(0.12 * SR)) / int(0.12 * SR), mode='same')
duck = np.clip(duck, 0, 1)
mus_gain = 0.5 - 0.27 * duck
mix_m = mus * mus_gain
sfx_gain = 0.85 - 0.3 * duck
mix_s = sfx * sfx_gain

# end fade (last 0.35 s)
fade = np.ones(N)
fn = int(0.35 * SR)
fade[-fn:] = np.linspace(1, 0, fn) ** 1.5

# stereo: small Haas widening on music/pads, sfx panned slightly by time, VO centred
L = (mix_m + np.roll(mix_m, int(0.004 * SR)) * 0.3) + mix_s * 0.95 + vo * 0.9
Rr = (mix_m * 1.0 + np.roll(mix_m, int(0.007 * SR)) * 0.3) + mix_s * 1.0 + vo * 0.9
st = np.stack([L, Rr], 1) * fade[:, None]
st = np.tanh(st / (np.max(np.abs(st)) + 1e-9) * 1.1) * 0.89

from scipy.io import wavfile
wavfile.write(sys.argv[1], SR, (st * 32767).astype(np.int16))
print('wrote', sys.argv[1], st.shape[0] / SR, 's')
