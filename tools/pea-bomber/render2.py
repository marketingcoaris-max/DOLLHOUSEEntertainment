#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pea Bomber - 24fps anime-style short, v2.

No on-screen text: the story is carried by the voice track, the character
animation (puppet warping + lip sync driven by voice_timing.json) and
hand-drawn-style effects animation drawn fresh every frame.

324 frames @ 24fps = 13.5 s, cut against the 160 BPM score.
"""
import json
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from anim import (W, H, FPS, Field, remap, GX, GY, fireball, smoke_cloud, flame_ribbon,
                  Debris, Sparks, sweat_bead, speed_lines, shockwave, directional_blur,
                  radial_blur, silhouette, grade, flash, chroma_split, VIG, blend,
                  ease_out, ease_in_out, lerp, hold, cel_bands, fbm)

TOTAL = 324
SUPER = 1.30
BW, BH = int(W * SUPER), int(H * SUPER)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
OUT = os.path.join(HERE, "frames2")
os.makedirs(OUT, exist_ok=True)

with open(os.path.join(HERE, "voice_timing.json")) as fp:
    VT = json.load(fp)
MOUTH = VT["mouth"]


def mouth_at(f):
    return MOUTH[f] if 0 <= f < len(MOUTH) else 0.0


# --------------------------------------------------------------------- setup
def cover(img, w, h):
    iw, ih = img.size
    s = max(w / iw, h / ih)
    nw, nh = int(math.ceil(iw * s)), int(math.ceil(ih * s))
    img = img.resize((nw, nh), Image.LANCZOS)
    l, t = (nw - w) // 2, (nh - h) // 2
    return img.crop((l, t, l + w, t + h))


def load(name):
    return cover(Image.open(os.path.join(SRC, name)).convert("RGB"), BW, BH)


IMG = {}


def img(name):
    if name not in IMG:
        IMG[name] = load(name)
    return IMG[name]


class Cam:
    """Crop window over the oversampled base, plus base->screen mapping."""

    def __init__(self, zoom, dx, dy, rot=0.0):
        pad = 1.12 if rot else 1.0
        cw, ch = BW / zoom / pad, BH / zoom / pad
        sx, sy = (BW - cw) / 2.0, (BH - ch) / 2.0
        cx = BW / 2.0 + dx * sx
        cy = BH / 2.0 + dy * sy
        self.l = max(0.0, min(BW - cw, cx - cw / 2.0))
        self.t = max(0.0, min(BH - ch, cy - ch / 2.0))
        self.cw, self.ch = cw, ch
        self.rot = rot
        self.pad = pad

    def crop(self, base):
        box = (self.l, self.t, self.l + self.cw, self.t + self.ch)
        if self.rot:
            big = base.resize((int(W * self.pad), int(H * self.pad)), Image.LANCZOS, box=box)
            big = big.rotate(self.rot, resample=Image.BICUBIC)
            ox, oy = (big.width - W) // 2, (big.height - H) // 2
            return big.crop((ox, oy, ox + W, oy + H))
        return base.resize((W, H), Image.LANCZOS, box=box)

    def to_out(self, u, v):
        """Base-image normalised (u,v) -> screen normalised (x,y)."""
        x = (u * BW - self.l) / self.cw
        y = (v * BH - self.t) / self.ch
        if self.rot:
            r = math.radians(-self.rot)
            x, y = x - 0.5, (y - 0.5) * (H / W)
            xr = x * math.cos(r) - y * math.sin(r)
            yr = x * math.sin(r) + y * math.cos(r)
            x, y = xr + 0.5, yr * (W / H) + 0.5
        return x, y


# --------------------------------------------------------------- FX handles
SPARK_WARM = Sparks(80, 21, up=True, spread=1.0)
SPARK_SLOW = Sparks(52, 42, up=True, spread=0.5)
SPARK_TRAIL = Sparks(70, 63, up=False, spread=1.0)
DEBRIS = Debris(64, 77, cx=0.55, cy=0.22, speed=1.25)
DEBRIS2 = Debris(30, 91, cx=0.30, cy=0.55, speed=0.8)

LIQUID_COLS = [(150, 70, 6, 200), (255, 168, 20, 240),
               (255, 226, 90, 255), (255, 252, 226, 255)]

# base-image anchor points, read off the source art
FACE = dict(head=(0.43, 0.24), eyes=(0.46, 0.325), mouth=(0.50, 0.418),
            jaw=(0.49, 0.455), fist=(0.24, 0.60), torso=(0.55, 0.66))


def boil(fld, f, amp=0.0016):
    """Hand-drawn line wobble, re-rolled every third frame."""
    fld.noise(amp, seed=1000 + (f // 3) * 7, scale=11)
    return fld


def shake(f, start, amp, decay=7.0, seed=0):
    t = (f - start) / FPS
    if t < 0:
        return 0.0, 0.0
    k = amp * math.exp(-decay * t)
    r = np.random.default_rng(int(f) * 977 + seed)
    return float(r.uniform(-1, 1) * k), float(r.uniform(-1, 1) * k)


def talk_pose(fld, cam, f, intensity=1.0):
    """Lip sync + head/jaw follow-through for the dialogue shots."""
    m = mouth_at(f)
    mx, my = cam.to_out(*FACE["mouth"])
    jx, jy = cam.to_out(*FACE["jaw"])
    hx, hy = cam.to_out(*FACE["head"])
    sc = 1.0 / max(cam.cw / BW, 1e-6)          # blobs grow as the camera pushes in
    # jaw drops and the mouth stretches open on loud syllables
    # rest pose is closed: the drawing has his mouth permanently open, so the
    # region is squashed when silent and stretched past the original when loud
    fld.blob(mx, my, 0.078 * sc, 0.058 * sc, dy=0.012 * m * intensity * sc,
             sy=0.60 + 0.58 * m * intensity)
    fld.blob(jx, jy, 0.115 * sc, 0.075 * sc, dy=0.009 * m * intensity * sc)
    # head lifts a little when he shouts, plus a slow idle bob
    hb = math.sin(hold(f, 2) * 0.42) * 0.0035 + m * 0.006 * intensity
    fld.blob(hx, hy, 0.30 * sc, 0.24 * sc, dy=-hb * sc,
             rot=math.sin(hold(f, 2) * 0.31) * 0.9 * intensity)
    return fld


def blink(fld, cam, f, period=52, offset=0):
    """Two-frame eyelid squash."""
    k = (f + offset) % period
    if k > 2:
        return fld
    amt = [0.45, 0.20, 0.55][k]
    ex, ey = cam.to_out(*FACE["eyes"])
    sc = 1.0 / max(cam.cw / BW, 1e-6)
    fld.blob(ex, ey, 0.20 * sc, 0.055 * sc, sy=amt)
    return fld


def breathe(fld, cam, f, amp=0.004):
    tx, ty = cam.to_out(*FACE["torso"])
    sc = 1.0 / max(cam.cw / BW, 1e-6)
    k = math.sin(hold(f, 2) * 0.26)
    fld.blob(tx, ty, 0.42 * sc, 0.36 * sc, sy=1.0 + amp * k, dy=-amp * 0.4 * k * sc)
    return fld


# ======================================================================
# the shot list
# ======================================================================
def render(f):
    ovs_add, ovs_norm = [], []
    fl, flc = 0.0, (255, 255, 255)
    chroma = 0.0
    sil = None
    post_rblur = 0.0
    rfocus = (0.5, 0.45)
    pan_blur = None
    warm = 0.0

    # ---------------------------------------------------------- S1 entrance
    if f < 36:
        p = f / 35.0
        base = img("01_flight.png")
        e = ease_out(min(1.0, p * 1.7))
        zoom = lerp(1.26, 1.05, e)
        sx, sy = shake(f, 0, 0.05, 9.0, 1)
        cam = Cam(zoom, lerp(0.30, 0.0, e) + sx, lerp(-0.30, 0.02, e) + sy,
                  rot=lerp(-3.2, 0.0, e))
        frame = cam.crop(base)
        if f < 5:                                   # whip-pan entry smear
            pan_blur = (lerp(150, 0, f / 5.0), lerp(-40, 0, f / 5.0))
        fld = Field()
        # hair / cloth flutter and a little forward drive
        hx, hy = cam.to_out(0.55, 0.30)
        fld.blob(hx, hy, 0.34, 0.30, dy=math.sin(hold(f, 2) * 0.55) * 0.004,
                 rot=math.sin(hold(f, 2) * 0.37) * 1.1)
        fld.wave(0.0022, 2.6, f * 0.55, axis="x")
        boil(fld, f)
        arr = fld.apply(np.asarray(frame).astype(np.float32))

        # the flame whip: an arc that sweeps as he swings it
        gx, gy = cam.to_out(0.27, 0.40)
        sweep = math.sin(f * 0.30) * 0.10
        pts = [(gx, gy)]
        for k in range(1, 9):
            a = math.pi * (0.95 - 1.05 * k / 8) + sweep
            r = 0.16 + 0.052 * k
            pts.append((gx + math.cos(a) * r * 1.35, gy - abs(math.sin(a)) * r * 1.5 - 0.02 * k))
        ovs_add.append((flame_ribbon(f / FPS, pts, 0.034 + 0.006 * math.sin(f * 0.7), seed=3), 0.95))
        ovs_add.append((SPARK_WARM.draw(f / FPS, 0.75), 0.9))
        ovs_add.append((speed_lines(max(0.0, 0.85 - p * 1.7), (0.5, 0.4), 3,
                                    (255, 236, 200), inner=0.22, count=170), 0.75))
        fl = max(0.0, 0.42 - f * 0.16)
        flc = (255, 232, 190)
        chroma = 5.0 * max(0.0, 1 - p * 3)
        warm = 0.25

    # ------------------------------------------------------ S2 igniting bombs
    elif f < 72:
        i = f - 36
        p = i / 35.0
        base = img("02_bomb.png")
        zoom = lerp(1.04, 1.22, ease_in_out(p))
        sx, sy = shake(f, 36, 0.028, 5.0, 2)
        for st in (14, 24):
            a, b = shake(f, 36 + st, 0.052, 11.0, 3)
            sx += a
            sy += b
        cam = Cam(zoom, lerp(0.12, -0.22, ease_in_out(p)) + sx,
                  lerp(0.18, -0.04, ease_in_out(p)) + sy)
        frame = cam.crop(base)
        fld = Field()
        ax, ay = cam.to_out(0.62, 0.30)
        fld.blob(ax, ay, 0.30, 0.26, rot=math.sin(hold(f, 2) * 0.5) * 0.8,
                 dy=math.sin(hold(f, 2) * 0.42) * 0.003)
        fld.wave(0.0018, 3.1, f * 0.7, axis="x")
        boil(fld, f)
        arr = fld.apply(np.asarray(frame).astype(np.float32))

        # burning liquid jet from the gun toward the bombs
        gx, gy = cam.to_out(0.52, 0.40)
        bx, by = cam.to_out(0.10, 0.60)
        pts = []
        for k in range(9):
            u = k / 8
            wob = math.sin(f * 0.85 + k * 0.9) * 0.012 * (1 - u)
            pts.append((lerp(gx, bx, u), lerp(gy, by, u) + wob + 0.05 * u * u))
        ovs_add.append((flame_ribbon(f / FPS, pts, 0.030, seed=9,
                                     cols=LIQUID_COLS), 0.85))
        # two ignitions
        for st, (bu, bv), rr, sd in ((14, (0.10, 0.60), 0.30, 41), (24, (0.26, 0.13), 0.24, 57)):
            if i >= st:
                t = (i - st) / 16.0
                ox, oy = cam.to_out(bu, bv)
                ovs_add.append((fireball(t, ox, oy, 0.03, rr, seed=sd), 1.0))
                if t < 1.0:
                    ovs_add.append((shockwave(min(1.0, t * 1.5), ox, oy,
                                              (255, 214, 120)), 0.7))
                if i - st < 4:
                    fl = max(fl, 0.40 * (1 - (i - st) / 4.0))
                    flc = (255, 224, 140)
        ovs_add.append((SPARK_WARM.draw(f / FPS, 0.95), 1.0))
        chroma = 3.0 * (1 - p)
        warm = 0.18

    # ---------------------------------------------------------- S3 explosion
    elif f < 108:
        i = f - 72
        p = i / 35.0
        base = img("03_explosion.png")
        zoom = lerp(1.38, 1.08, ease_out(min(1.0, p * 1.4)))
        sx, sy = shake(f, 72, 0.105, 5.0, 4)
        cam = Cam(zoom, lerp(-0.08, 0.04, ease_out(p)) + sx,
                  lerp(0.14, -0.10, ease_out(p)) + sy)
        frame = cam.crop(base)
        fld = Field()
        # the blast shoves him: squash on impact, then settle
        k = math.exp(-4.0 * (i / FPS))
        cx, cy = cam.to_out(0.58, 0.45)
        fld.blob(cx, cy, 0.45, 0.40, sx=1.0 + 0.05 * k, sy=1.0 - 0.05 * k,
                 dx=0.02 * k, rot=-2.5 * k)
        fld.wave(0.0026 * (0.3 + k), 2.4, f * 0.8, axis="x")
        boil(fld, f, 0.0022)
        arr = fld.apply(np.asarray(frame).astype(np.float32))

        ex, ey = cam.to_out(0.55, 0.17)
        t = i / 22.0
        ovs_add.append((fireball(t, ex, ey, 0.05, 0.95, seed=11), 1.0))
        if i > 12:
            ovs_norm.append((smoke_cloud((i - 12) / 26.0, ex, ey - 0.05, 0.20, 0.78, seed=23),
                             0.55))
        ovs_add.append((shockwave(min(1.0, i / 14.0), ex, ey), 1.0))
        ovs_norm.append((DEBRIS.draw(i / FPS * 1.15, 1.0), 1.0))
        ovs_add.append((speed_lines(max(0.0, 1.1 - p * 1.5), (ex, ey), 12,
                                    (255, 232, 180), inner=0.15, count=230), 1.0))
        ovs_add.append((SPARK_WARM.draw(f / FPS, 1.0), 1.1))
        if i < 2:
            sil = "white"
        elif i < 4:
            sil = "hot"
        fl = max(fl, (0.30 if i < 4 else 0.55) * math.exp(-6.5 * (i / FPS)))
        flc = (255, 240, 205)
        post_rblur = 0.0 if i < 4 else 0.15 * math.exp(-4.0 * (i / FPS))
        rfocus = (ex, ey)
        chroma = 9.0 * math.exp(-5.0 * (i / FPS))
        warm = 0.30

    # ------------------------------------------------------- S4 the speech
    elif f < 247:
        base = img("04_thumbsup.png")
        # sub-cuts, each landing on a line of dialogue
        if f < 144:                    # "I'm Pea Bomber!"
            i, n = f - 108, 36
            q = i / (n - 1)
            zoom, dx, dy, rot = lerp(1.02, 1.09, q), 0.0, lerp(0.06, -0.02, q), 0.0
            cut = 108
        elif f < 170:                  # "Yo, Kori!"
            i, n = f - 144, 26
            q = i / (n - 1)
            zoom, dx, dy, rot = lerp(1.34, 1.40, q), lerp(0.05, -0.02, q), -0.44, -1.5
            cut = 144
        elif f < 204:                  # "Happy birthday!!"
            i, n = f - 170, 34
            q = i / (n - 1)
            zoom, dx, dy, rot = lerp(1.16, 1.06, ease_out(q)), 0.0, lerp(-0.12, -0.02, q), 0.0
            cut = 170
        else:                          # "Let's keep at it!"
            i, n = f - 204, 43
            q = i / (n - 1)
            zoom, dx, dy, rot = lerp(1.10, 1.22, ease_in_out(q)), lerp(-0.04, 0.06, q), \
                lerp(-0.04, 0.10, q), 1.2
            cut = 204
        sx, sy = shake(f, cut, 0.035, 10.0, 5)
        cam = Cam(zoom, dx + sx, dy + sy, rot=rot)
        frame = cam.crop(base)
        fld = Field()
        talk_pose(fld, cam, f)
        blink(fld, cam, f, 52, 11)
        breathe(fld, cam, f)
        if f >= 204:                   # pushes the thumbs-up toward camera
            fx_, fy_ = cam.to_out(*FACE["fist"])
            k = ease_in_out(q)
            fld.blob(fx_, fy_, 0.30, 0.26, sx=1 + 0.10 * k, sy=1 + 0.10 * k,
                     dy=-0.012 * k, dx=0.010 * k)
        boil(fld, f)
        arr = fld.apply(np.asarray(frame).astype(np.float32))

        ovs_add.append((SPARK_SLOW.draw(f / FPS, 0.55), 0.85))
        fl = max(0.0, 0.30 - (f - cut) * 0.14)
        # "happy birthday" gets an anime radial burst behind him
        if 170 <= f < 204:
            t = (f - 170) / 14.0
            if t < 1.4:
                ovs_add.append((speed_lines(max(0.0, 1.0 - t * 0.75), (0.5, 0.42), 61,
                                            (255, 224, 140), inner=0.30, count=190), 0.55))
            ovs_add.append((SPARK_WARM.draw(f / FPS, 0.55), 0.75))
            warm = 0.25
        if f >= 204:
            warm = 0.12

    # ------------------------------------------------------------- S5 panic
    elif f < 288:
        i = f - 247
        base = img("04_thumbsup.png")
        # fast trembling: high-frequency camera + body wobble
        tr = math.sin(i * 2.4) * 0.05 + math.sin(i * 5.1) * 0.026
        zoom = 1.26 + math.sin(i * 3.2) * 0.02
        cam = Cam(zoom, 0.05 + tr, -0.30 + math.sin(i * 4.1 + 1.1) * 0.045,
                  rot=math.sin(i * 3.1) * 2.4)
        frame = cam.crop(base)
        fld = Field()
        talk_pose(fld, cam, f, intensity=1.15)
        # whole body judders and squashes
        bx, by = cam.to_out(0.45, 0.55)
        j = math.sin(i * 6.2)
        fld.blob(bx, by, 0.50, 0.45, sx=1 + 0.022 * j, sy=1 - 0.022 * j,
                 dx=0.004 * math.sin(i * 7.7), rot=1.6 * math.sin(i * 5.3))
        boil(fld, f, 0.0026)
        arr = fld.apply(np.asarray(frame).astype(np.float32))

        # sweat beads
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        r = np.random.default_rng(3)
        for k in range(6):
            x0 = float(r.uniform(0.18, 0.84)) * W
            y0 = float(r.uniform(0.13, 0.40)) * H
            delay = float(r.uniform(0, 12))
            tt = ((i - delay) % 20) / 20.0
            if i < delay:
                continue
            a = int(235 * max(0.0, 1 - tt))
            sweat_bead(x0, y0 + tt * 430, float(r.uniform(17, 27)), a)(d)
        ovs_norm.append((ov, 0.95))
        # trembling motion streaks
        ov2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(ov2)
        for k in range(18):
            side = -1 if k % 2 == 0 else 1
            x = W * (0.5 + side * float(r.uniform(0.30, 0.52)))
            y = float(r.uniform(0.08, 0.88)) * H
            L = float(r.uniform(70, 230))
            a = int(185 * (0.5 + 0.5 * math.sin(i * 2.6 + k)))
            d2.line((x - L / 2, y, x + L / 2, y), fill=(255, 255, 255, a),
                    width=int(r.integers(3, 8)))
        ovs_add.append((ov2, 0.75))
        if i < 4:
            fl = max(fl, 0.34 * (1 - i / 4.0))
            flc = (215, 236, 255)
        chroma = 2.5 + 2.2 * abs(math.sin(i * 3.0))

    # ------------------------------------------------------------- S6 exit
    else:
        i = f - 288
        n = TOTAL - 288
        p = i / (n - 1)
        base = img("05_leave.png")
        e = ease_out(p)
        cam = Cam(lerp(1.30, 1.00, e), lerp(-0.10, 0.0, e) + shake(f, 288, 0.05, 8.0, 8)[0],
                  lerp(0.44, -0.06, e) + shake(f, 288, 0.05, 8.0, 8)[1])
        frame = cam.crop(base)
        fld = Field()
        hx, hy = cam.to_out(0.48, 0.28)
        fld.blob(hx, hy, 0.26, 0.24, dy=-0.004 * math.sin(hold(f, 2) * 0.6),
                 rot=math.sin(hold(f, 2) * 0.4) * 0.8)
        fld.wave(0.0020, 2.8, f * 0.8, axis="x")
        boil(fld, f)
        arr = fld.apply(np.asarray(frame).astype(np.float32))

        # jet plume streaming off the pack and boots
        jx, jy = cam.to_out(0.36, 0.44)
        tx, ty = cam.to_out(0.05, 0.80)
        pts = []
        for k in range(8):
            u = k / 7
            wob = math.sin(f * 1.1 + k) * 0.010 * u
            pts.append((lerp(jx, tx, u) + wob, lerp(jy, ty, u) + wob * 0.5))
        ovs_add.append((flame_ribbon(f / FPS, pts, 0.028 + 0.005 * math.sin(f * 0.9),
                                     seed=13), 0.95))
        ovs_add.append((speed_lines(max(0.18, 0.9 - p * 0.75), (0.40, 0.62), 9,
                                    (255, 228, 175), inner=0.17, count=210), 0.9))
        ovs_add.append((SPARK_TRAIL.draw(f / FPS, 0.9), 1.0))
        fl = max(0.0, 0.40 - i * 0.18)
        flc = (255, 236, 200)
        post_rblur = 0.06 * (1 - ease_out(min(1.0, p * 1.6)))
        rfocus = (0.42, 0.62)
        warm = 0.2

    # ------------------------------------------------------------ composite
    if pan_blur:
        arr = np.asarray(directional_blur(
            Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)), *pan_blur)).astype(np.float32)
    if post_rblur > 0.002:
        arr = np.asarray(radial_blur(
            Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)),
            rfocus, post_rblur, 6)).astype(np.float32)
    if sil:
        arr = silhouette(arr, sil)
    arr = grade(arr, 1.05, 1.10, warm)
    arr = arr * VIG
    if chroma:
        arr = chroma_split(arr, chroma)
    for ov, g in ovs_add:
        arr = blend(arr, ov, True, g)
    for ov, g in ovs_norm:
        arr = blend(arr, ov, False, g)
    if fl > 0.002:
        arr = flash(arr, fl, flc)

    if f < 3:
        arr *= (f + 1) / 4.0
    tail = TOTAL - 1 - f
    if tail < 8:
        arr *= max(0.0, tail / 8.0) ** 0.9

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _job(f):
    render(f).save(os.path.join(OUT, "f%04d.jpg" % f), quality=94, subsampling=1)
    return f


if __name__ == "__main__":
    import sys
    import multiprocessing as mp
    if len(sys.argv) > 1:                       # render a subset for checking
        for f in [int(x) for x in sys.argv[1:]]:
            _job(f)
            print("frame", f)
        raise SystemExit
    n = max(1, min(8, os.cpu_count() or 2))
    print("rendering %d frames on %d workers ..." % (TOTAL, n))
    with mp.Pool(n) as pool:
        for k, f in enumerate(pool.imap_unordered(_job, range(TOTAL), chunksize=3)):
            if k % 40 == 0:
                print("  %3d / %d" % (k, TOTAL), flush=True)
    print("done ->", OUT)
