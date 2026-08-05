#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Animation toolkit for the Pea Bomber short.

Everything needed to turn still illustrations into 24fps anime-style motion:
a bilinear warp engine (for puppet-style character animation and lip sync),
procedural cel-shaded effects (fire, explosions, smoke, debris) drawn fresh
every frame, and the camera / line-boil helpers that sell the hand-drawn look.
"""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
FPS = 24


# ==========================================================================
# warping
# ==========================================================================
def grid():
    """Normalised (x, y) grids in 0..1."""
    gy, gx = np.mgrid[0:H, 0:W].astype(np.float32)
    return gx / W, gy / H


GX, GY = grid()


def remap(arr, mx, my):
    """Bilinear sample of arr (H,W,C) at source coords mx,my (pixels)."""
    x0 = np.floor(mx).astype(np.int32)
    y0 = np.floor(my).astype(np.int32)
    fx = (mx - x0)[:, :, None]
    fy = (my - y0)[:, :, None]
    x1, y1 = x0 + 1, y0 + 1
    np.clip(x0, 0, arr.shape[1] - 1, out=x0)
    np.clip(x1, 0, arr.shape[1] - 1, out=x1)
    np.clip(y0, 0, arr.shape[0] - 1, out=y0)
    np.clip(y1, 0, arr.shape[0] - 1, out=y1)
    a = arr[y0, x0]
    b = arr[y0, x1]
    c = arr[y1, x0]
    d = arr[y1, x1]
    top = a + (b - a) * fx
    bot = c + (d - c) * fx
    return top + (bot - top) * fy


class Field:
    """Accumulates displacement (in normalised units) from puppet controls."""

    def __init__(self):
        self.fx = np.zeros((H, W), np.float32)
        self.fy = np.zeros((H, W), np.float32)

    def blob(self, cx, cy, rx, ry, dx=0.0, dy=0.0, rot=0.0, sx=1.0, sy=1.0, power=1.0):
        """Local affine move with a soft gaussian falloff.

        cx..ry are normalised; dx/dy shift the region, rot rotates it (deg),
        sx/sy scale it about its centre (used for lip sync and squash).
        """
        lx = (GX - cx)
        ly = (GY - cy) * (H / W)                     # work in square-ish units
        rr = (lx / rx) ** 2 + (ly / (ry * H / W)) ** 2
        wgt = np.exp(-rr * 2.2) ** power
        r = math.radians(rot)
        cos, sin = math.cos(r), math.sin(r)
        tx = (lx * sx) * cos - (ly * sy) * sin
        ty = (lx * sx) * sin + (ly * sy) * cos
        self.fx += wgt * ((tx - lx) + dx)
        self.fy += wgt * ((ty - ly) * (W / H) + dy)
        return self

    def wave(self, amp, freq, phase, axis="x", vertical=True):
        """Gentle travelling ripple - cloth, flame, heat haze."""
        if vertical:
            s = np.sin(GY * freq * math.tau + phase) * amp
        else:
            s = np.sin(GX * freq * math.tau + phase) * amp
        if axis == "x":
            self.fx += s
        else:
            self.fy += s
        return self

    def noise(self, amp, seed, scale=9):
        """Low-frequency wobble - the hand-drawn 'boil'."""
        nz = value_noise(scale, scale * 2, seed)
        self.fx += (nz - 0.5) * 2 * amp
        nz2 = value_noise(scale, scale * 2, seed + 997)
        self.fy += (nz2 - 0.5) * 2 * amp
        return self

    def apply(self, arr):
        mx = GX * W - self.fx * W
        my = GY * H - self.fy * H
        return remap(arr, mx, my)


# ==========================================================================
# noise
# ==========================================================================
_noise_cache = {}


def value_noise(nx, ny, seed, size=(W, H)):
    """Smooth value noise in 0..1, built by upsampling a small random grid."""
    key = (nx, ny, seed, size)
    if key in _noise_cache:
        return _noise_cache[key]
    r = np.random.default_rng(seed)
    g = r.random((ny, nx)).astype(np.float32)
    img = Image.fromarray((g * 255).astype(np.uint8)).resize(size, Image.BICUBIC)
    out = np.asarray(img).astype(np.float32) / 255.0
    if len(_noise_cache) < 220:
        _noise_cache[key] = out
    return out


def fbm(seed, t, octaves=3, base=5, drift=(0.0, -0.35)):
    """Animated fractal noise - the base for fire and smoke."""
    acc = np.zeros((H, W), np.float32)
    amp = 1.0
    tot = 0.0
    for o in range(octaves):
        nx = base * (2 ** o)
        ny = nx * 2
        # advect by rolling the sampled field
        n0 = value_noise(nx, ny, seed + o * 131)
        sx = int(drift[0] * t * W * (o + 1) * 0.25)
        sy = int(drift[1] * t * H * (o + 1) * 0.25)
        acc += np.roll(np.roll(n0, sy, axis=0), sx, axis=1) * amp
        tot += amp
        amp *= 0.52
    return acc / tot


# ==========================================================================
# cel shading helpers
# ==========================================================================
def cel_bands(density, stops, colors, softness=0.012):
    """Posterise a scalar field into flat colour bands (RGBA)."""
    h, w = density.shape
    out = np.zeros((h, w, 4), np.float32)
    for i, (s, col) in enumerate(zip(stops, colors)):
        if i + 1 < len(stops):
            m = ((density >= s) & (density < stops[i + 1])).astype(np.float32)
        else:
            m = (density >= s).astype(np.float32)
        if softness > 0:
            m = np.asarray(Image.fromarray((m * 255).astype(np.uint8))
                           .filter(ImageFilter.GaussianBlur(1.1))).astype(np.float32) / 255.0
        for c in range(3):
            out[:, :, c] += m * col[c]
        out[:, :, 3] += m * col[3]
    np.clip(out, 0, 255, out=out)
    return out


FIRE_STOPS = [0.30, 0.44, 0.60, 0.82]
FIRE_COLS = [(120, 40, 10, 210),      # dark rim
             (255, 120, 20, 245),     # orange
             (255, 196, 50, 255),     # yellow
             (255, 250, 220, 255)]    # white core

SMOKE_STOPS = [0.34, 0.48, 0.64]
SMOKE_COLS = [(38, 40, 52, 130), (92, 96, 112, 160), (168, 174, 190, 185)]


def fireball(t, cx, cy, r0, r1, seed=1, cols=None, stops=None, wob=0.42):
    """Expanding cel-shaded explosion cloud with billowing lobes."""
    if t <= 0:
        return None
    R = (r0 + (r1 - r0) * (1 - (1 - min(t, 1.0)) ** 2))
    lx = (GX - cx)
    ly = (GY - cy) * (H / W)
    d = np.sqrt(lx * lx + ly * ly) / max(R, 1e-4)
    n = fbm(seed, t * 0.55, 3, 4, drift=(0.05, -0.22))
    dens = np.clip(1.35 - d + (n - 0.5) * wob, 0, 2)
    # fade the whole cloud out as it disperses
    dens *= max(0.0, 1.0 - max(0.0, t - 0.55) / 0.85)
    return cel_bands(dens, stops or FIRE_STOPS, cols or FIRE_COLS)


def smoke_cloud(t, cx, cy, r0, r1, seed=5, rise=0.10):
    if t <= 0:
        return None
    R = r0 + (r1 - r0) * min(t, 1.0) ** 0.7
    lx = (GX - cx)
    ly = (GY - (cy - rise * t)) * (H / W)
    d = np.sqrt(lx * lx + ly * ly) / max(R, 1e-4)
    n = fbm(seed, t * 0.4, 3, 3, drift=(0.03, -0.3))
    dens = np.clip(1.3 - d + (n - 0.5) * 0.55, 0, 2)
    dens *= max(0.0, 1.0 - max(0.0, t - 0.35) / 0.75)
    return cel_bands(dens, SMOKE_STOPS, SMOKE_COLS)


def flame_ribbon(t, pts, width, seed=3, cols=None, stops=None):
    """Cel-shaded flame following a poly-line (whip, jet plume, liquid stream)."""
    dens = np.zeros((H, W), np.float32)
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        steps = 9
        for s in range(steps):
            u = s / steps
            cx = x0 + (x1 - x0) * u
            cy = y0 + (y1 - y0) * u
            k = i / max(1, len(pts) - 2)
            rw = width * (1.0 - 0.55 * k)
            lx = (GX - cx)
            ly = (GY - cy) * (H / W)
            dens += np.exp(-((lx / rw) ** 2 + (ly / (rw * H / W)) ** 2) * 1.8) * 0.55
    n = fbm(seed, t * 1.5, 2, 7, drift=(0.25, -0.55))
    dens = np.clip(dens + (n - 0.5) * 0.65, 0, 2)
    return cel_bands(dens, stops or FIRE_STOPS, cols or FIRE_COLS)


# ==========================================================================
# particles
# ==========================================================================
class Debris:
    """Chunks of rubble flung out of the blast, with rotation and streaks."""

    def __init__(self, n, seed, cx=0.5, cy=0.45, speed=1.0):
        r = np.random.default_rng(seed)
        a = r.uniform(0, math.tau, n)
        v = r.uniform(0.35, 1.5, n) * speed
        self.cx, self.cy = cx, cy
        self.ang = a
        self.vx = np.cos(a) * v
        self.vy = np.sin(a) * v * 0.8 - 0.25
        self.size = r.uniform(7, 34, n)
        self.spin = r.uniform(-9, 9, n)
        self.shape = r.integers(3, 6, n)
        self.phase = r.uniform(0, math.tau, n)

    def draw(self, t, alpha=1.0, streak=True):
        if t <= 0:
            return None
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        gravity = 0.55
        for i in range(len(self.size)):
            x = (self.cx + self.vx[i] * t * 0.42) * W
            y = (self.cy + self.vy[i] * t * 0.42 + gravity * t * t * 0.30) * H
            if x < -80 or x > W + 80 or y > H + 80:
                continue
            a = int(255 * alpha * max(0.0, 1 - t / 1.8))
            if a <= 4:
                continue
            s = self.size[i]
            rot = self.phase[i] + self.spin[i] * t
            pts = []
            for k in range(self.shape[i]):
                aa = rot + k * math.tau / self.shape[i]
                pts.append((x + math.cos(aa) * s, y + math.sin(aa) * s * 0.85))
            if streak:
                d.line((x - self.vx[i] * 40, y - self.vy[i] * 40, x, y),
                       fill=(255, 190, 90, a // 3), width=max(2, int(s * 0.35)))
            d.polygon(pts, fill=(26, 22, 30, a), outline=(70, 50, 40, a))
        return ov


class Sparks:
    def __init__(self, n, seed, up=True, spread=1.0, warm=True, size=(2, 7)):
        r = np.random.default_rng(seed)
        self.x = r.uniform(-0.1, 1.1, n)
        self.y = r.uniform(-0.15, 1.25, n)
        self.vx = r.uniform(-0.06, 0.06, n) * spread
        self.vy = (r.uniform(-0.32, -0.08, n) if up else r.uniform(0.08, 0.30, n)) * spread
        self.s = r.uniform(size[0], size[1], n)
        self.ph = r.uniform(0, math.tau, n)
        self.warm = warm

    def draw(self, t, alpha=1.0):
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        col = (255, 205, 90) if self.warm else (175, 220, 255)
        for i in range(len(self.s)):
            x = (self.x[i] + self.vx[i] * t) % 1.2 - 0.1
            y = (self.y[i] + self.vy[i] * t) % 1.4 - 0.15
            tw = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 9 + self.ph[i]))
            a = int(240 * tw * alpha)
            if a <= 4:
                continue
            s = self.s[i] * (0.7 + 0.6 * tw)
            d.ellipse((x * W - s, y * H - s, x * W + s, y * H + s), fill=col + (a,))
        return ov.filter(ImageFilter.GaussianBlur(1.6))


def sweat_bead(x, y, s, a, tilt=0.0):
    """Returns a drawing callback for the classic anime sweat drop."""
    def draw(d):
        d.polygon([(x, y - s * 2.1 + tilt), (x - s * 0.58, y - s * 0.15),
                   (x + s * 0.58, y - s * 0.15)], fill=(198, 236, 255, a))
        d.ellipse((x - s * 0.62, y - s, x + s * 0.62, y + s),
                  fill=(198, 236, 255, a), outline=(255, 255, 255, a), width=3)
        d.ellipse((x - s * 0.30, y - s * 0.38, x - s * 0.02, y + s * 0.02),
                  fill=(255, 255, 255, a))
    return draw


# ==========================================================================
# camera / screen effects
# ==========================================================================
def speed_lines(intensity, focus=(0.5, 0.45), seed=1, color=(255, 255, 255),
                inner=0.24, count=200, thick=(2, 10)):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if intensity <= 0.01:
        return ov
    d = ImageDraw.Draw(ov)
    r = np.random.default_rng(seed)
    fx, fy = focus[0] * W, focus[1] * H
    diag = math.hypot(W, H)
    for _ in range(int(count * intensity)):
        ang = r.uniform(0, math.tau)
        r0 = diag * inner * r.uniform(0.75, 1.5)
        ln = diag * r.uniform(0.10, 0.45) * intensity
        x0, y0 = fx + math.cos(ang) * r0, fy + math.sin(ang) * r0
        x1, y1 = fx + math.cos(ang) * (r0 + ln), fy + math.sin(ang) * (r0 + ln)
        a = int(r.uniform(70, 210) * intensity)
        d.line((x0, y0, x1, y1), fill=color + (a,), width=int(r.integers(*thick)))
    return ov.filter(ImageFilter.GaussianBlur(1.1))


def shockwave(prog, cx=0.5, cy=0.42, color=(255, 226, 150), squash=0.62):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if prog <= 0 or prog >= 1:
        return ov
    d = ImageDraw.Draw(ov)
    r = (1 - (1 - prog) ** 3) * W * 1.5
    a = int(235 * (1 - prog) ** 1.3)
    wd = int(52 * (1 - prog) + 5)
    x, y = cx * W, cy * H
    d.ellipse((x - r, y - r * squash, x + r, y + r * squash),
              outline=color + (a,), width=max(2, wd))
    r2 = r * 0.7
    d.ellipse((x - r2, y - r2 * squash, x + r2, y + r2 * squash),
              outline=(255, 255, 255, int(a * 0.55)), width=max(2, wd // 2))
    return ov.filter(ImageFilter.GaussianBlur(5))


def directional_blur(img, dx, dy, samples=9):
    """Whip-pan smear."""
    if abs(dx) < 0.5 and abs(dy) < 0.5:
        return img
    acc = np.asarray(img).astype(np.float32)
    base = img
    for i in range(1, samples):
        k = i / (samples - 1)
        sh = base.transform(
            (W, H), Image.AFFINE, (1, 0, dx * k, 0, 1, dy * k), resample=Image.BILINEAR)
        acc += np.asarray(sh).astype(np.float32)
    return Image.fromarray(np.clip(acc / samples, 0, 255).astype(np.uint8))


def radial_blur(img, focus, amount, samples=7):
    if amount <= 0.001:
        return img
    fx, fy = focus
    acc = np.asarray(img).astype(np.float32)
    for i in range(1, samples):
        s = 1.0 + amount * i / (samples - 1)
        nw, nh = int(W * s), int(H * s)
        big = img.resize((nw, nh), Image.BILINEAR)
        ox = int(fx * nw - fx * W)
        oy = int(fy * nh - fy * H)
        acc += np.asarray(big.crop((ox, oy, ox + W, oy + H))).astype(np.float32)
    return Image.fromarray(np.clip(acc / samples, 0, 255).astype(np.uint8))


def silhouette(a, tone="hot"):
    """Anime impact frame: subject crushed to a flat silhouette on a colour flood."""
    g = a.mean(axis=2)
    g = np.clip((g - 105) * 3.2 + 105, 0, 255) / 255.0
    if tone == "hot":
        lo = np.array([48, 12, 6], np.float32)
        hi = np.array([255, 226, 120], np.float32)
    elif tone == "white":
        lo = np.array([20, 22, 40], np.float32)
        hi = np.array([255, 255, 255], np.float32)
    else:
        lo = np.array([10, 16, 54], np.float32)
        hi = np.array([222, 238, 255], np.float32)
    return lo + (hi - lo) * g[:, :, None]


def grade(a, contrast=1.05, sat=1.10, warm=0.0):
    m = a.mean(axis=2, keepdims=True)
    a = m + (a - m) * sat
    a = (a - 128.0) * contrast + 128.0
    if warm:
        a[:, :, 0] += 14 * warm
        a[:, :, 1] += 5 * warm
        a[:, :, 2] -= 10 * warm
    return a


def flash(a, amt, color=(255, 255, 255)):
    if amt <= 0.002:
        return a
    return a + (np.array(color, np.float32) - a) * float(amt)


def chroma_split(a, k):
    if k < 0.5:
        return a
    k = int(round(k))
    out = a.copy()
    out[:, :, 0] = np.roll(a[:, :, 0], k, axis=1)
    out[:, :, 2] = np.roll(a[:, :, 2], -k, axis=1)
    return out


def _vignette():
    ny = (GY - 0.5) * 2
    nx = (GX - 0.5) * 2
    r = np.sqrt(nx * nx + ny * ny * 0.72)
    return np.clip(1.0 - 0.72 * np.clip(r - 0.55, 0, None) ** 1.5, 0.55, 1.0)[:, :, None]


VIG = _vignette()


def blend(a, ov, additive=True, gain=1.0):
    if ov is None:
        return a
    o = ov if isinstance(ov, np.ndarray) else np.asarray(ov.convert("RGBA")).astype(np.float32)
    al = (o[:, :, 3:4] / 255.0) * gain
    rgb = o[:, :, :3]
    if additive:
        return a + rgb * al
    return a * (1 - al) + rgb * al


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def hold(f, n=2):
    """Quantise a frame index onto 2s/3s, the way TV anime is timed."""
    return (f // n) * n
