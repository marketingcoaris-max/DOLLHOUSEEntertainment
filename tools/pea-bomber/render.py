#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pea Bomber - hero animation frame renderer.
Builds an anime-style action sequence out of 5 still illustrations.
"""
import math, os, random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

W, H = 1080, 1920
FPS = 24
TOTAL = 270                       # 11.25 s
SUPER = 1.28                      # base canvas oversample for pan/zoom room
BW, BH = int(W * SUPER), int(H * SUPER)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
OUT = os.path.join(HERE, "frames")
os.makedirs(OUT, exist_ok=True)

FONT_PATH = "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf"
FONT_GO = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def cover(img, w, h):
    iw, ih = img.size
    s = max(w / iw, h / ih)
    nw, nh = int(math.ceil(iw * s)), int(math.ceil(ih * s))
    img = img.resize((nw, nh), Image.LANCZOS)
    l, t = (nw - w) // 2, (nh - h) // 2
    return img.crop((l, t, l + w, t + h))


def load_base(name):
    im = Image.open(os.path.join(SRC, name)).convert("RGB")
    return cover(im, BW, BH)


def frame_from(base, zoom, dx, dy, rot=0.0):
    """Crop a window out of the oversampled base -> 1080x1920."""
    cw, ch = BW / zoom, BH / zoom
    pad = 1.0
    if rot:
        pad = 1.10
        cw, ch = cw / pad, ch / pad
    sx, sy = (BW - cw) / 2.0, (BH - ch) / 2.0
    cx = BW / 2.0 + dx * sx
    cy = BH / 2.0 + dy * sy
    l = max(0.0, min(BW - cw, cx - cw / 2.0))
    t = max(0.0, min(BH - ch, cy - ch / 2.0))
    box = (l, t, l + cw, t + ch)
    if rot:
        big = base.resize((int(W * pad), int(H * pad)), Image.LANCZOS, box=box)
        big = big.rotate(rot, resample=Image.BICUBIC)
        ox, oy = (big.width - W) // 2, (big.height - H) // 2
        return big.crop((ox, oy, ox + W, oy + H))
    return base.resize((W, H), Image.LANCZOS, box=box)


def to_np(img):
    return np.asarray(img).astype(np.float32)


def to_img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ---- colour / light -------------------------------------------------------
def grade(a, contrast=1.06, sat=1.12, lift=0.0):
    m = a.mean(axis=2, keepdims=True)
    a = m + (a - m) * sat
    a = (a - 128.0) * contrast + 128.0 + lift
    return a


def flash(a, amt, color=(255, 255, 255)):
    if amt <= 0:
        return a
    c = np.array(color, dtype=np.float32)
    return a + (c - a) * float(amt)


def vignette_mask():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    nx = (xx - W / 2) / (W / 2)
    ny = (yy - H / 2) / (H / 2)
    r = np.sqrt(nx * nx + ny * ny * 0.72)
    v = np.clip(1.0 - 0.30 * np.clip(r - 0.55, 0, None) ** 1.5 * 2.4, 0.55, 1.0)
    return v[:, :, None]


VIG = vignette_mask()


def radial_blur(img, focus, amount, samples=7):
    """Cheap zoom-blur: stack progressively scaled copies about a focus point."""
    if amount <= 0.001:
        return img
    fx, fy = focus
    acc = to_np(img)
    for i in range(1, samples):
        s = 1.0 + amount * i / (samples - 1)
        nw, nh = int(W * s), int(H * s)
        big = img.resize((nw, nh), Image.BILINEAR)
        ox = int(fx * nw - fx * W)
        oy = int(fy * nh - fy * H)
        acc += to_np(big.crop((ox, oy, ox + W, oy + H)))
    return to_img(acc / samples)


def chroma_split(a, k):
    if k < 0.5:
        return a
    k = int(round(k))
    out = a.copy()
    out[:, :, 0] = np.roll(a[:, :, 0], k, axis=1)
    out[:, :, 2] = np.roll(a[:, :, 2], -k, axis=1)
    return out


def impact_frame(img, tone="hot"):
    """Anime 'impact frame': posterised two-tone flash."""
    g = np.asarray(img.convert("L")).astype(np.float32)
    g = (g - 110) * 2.6 + 110
    g = np.clip(g, 0, 255) / 255.0
    if tone == "hot":
        lo = np.array([28, 10, 46], np.float32)
        hi = np.array([255, 232, 150], np.float32)
    else:
        lo = np.array([8, 14, 48], np.float32)
        hi = np.array([235, 245, 255], np.float32)
    return lo + (hi - lo) * g[:, :, None]


# ---- overlay drawing ------------------------------------------------------
def blend_overlay(a, ov, additive=True, gain=1.0):
    """ov: RGBA PIL image."""
    o = to_np(ov.convert("RGBA"))
    al = (o[:, :, 3:4] / 255.0) * gain
    rgb = o[:, :, :3]
    if additive:
        return a + rgb * al
    return a * (1 - al) + rgb * al


def speed_lines(intensity, focus=(0.5, 0.45), seed=1, color=(255, 255, 255),
                inner=0.24, count=190, thick=(2, 9), spread=1.0):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if intensity <= 0.01:
        return ov
    d = ImageDraw.Draw(ov)
    rnd = random.Random(seed)
    fx, fy = focus[0] * W, focus[1] * H
    diag = math.hypot(W, H)
    for i in range(int(count * intensity)):
        ang = rnd.uniform(0, math.tau)
        r0 = diag * inner * rnd.uniform(0.75, 1.5) * spread
        ln = diag * rnd.uniform(0.10, 0.42) * intensity
        x0, y0 = fx + math.cos(ang) * r0, fy + math.sin(ang) * r0
        x1, y1 = fx + math.cos(ang) * (r0 + ln), fy + math.sin(ang) * (r0 + ln)
        a = int(rnd.uniform(60, 200) * intensity)
        d.line((x0, y0, x1, y1), fill=color + (a,), width=rnd.randint(*thick))
    return ov.filter(ImageFilter.GaussianBlur(1.2))


def shockwave(prog, cx=0.5, cy=0.42, color=(255, 226, 150)):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if prog <= 0 or prog >= 1:
        return ov
    d = ImageDraw.Draw(ov)
    r = ease_out(prog) * W * 1.45
    a = int(230 * (1 - prog) ** 1.4)
    wdt = int(lerp(46, 6, prog))
    x, y = cx * W, cy * H
    d.ellipse((x - r, y - r * 0.62, x + r, y + r * 0.62),
              outline=color + (a,), width=max(2, wdt))
    r2 = r * 0.72
    d.ellipse((x - r2, y - r2 * 0.62, x + r2, y + r2 * 0.62),
              outline=(255, 255, 255, int(a * 0.6)), width=max(2, wdt // 2))
    return ov.filter(ImageFilter.GaussianBlur(6))


class Embers:
    """Rising sparks / floating cinders."""

    def __init__(self, n, seed, up=True, spread=1.0, size=(2, 7), warm=True):
        rnd = random.Random(seed)
        self.p = []
        for _ in range(n):
            self.p.append(dict(
                x=rnd.uniform(-0.1, 1.1), y=rnd.uniform(-0.15, 1.25),
                vx=rnd.uniform(-0.06, 0.06) * spread,
                vy=(rnd.uniform(-0.30, -0.08) if up else rnd.uniform(0.06, 0.26)) * spread,
                s=rnd.uniform(*size), ph=rnd.uniform(0, math.tau),
                warm=warm, hue=rnd.random()))

    def draw(self, t, alpha=1.0, rainbow=False):
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for p in self.p:
            x = (p["x"] + p["vx"] * t) % 1.2 - 0.1
            y = (p["y"] + p["vy"] * t) % 1.4 - 0.15
            tw = 0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 9 + p["ph"]))
            a = int(235 * tw * alpha)
            if a <= 3:
                continue
            if rainbow:
                hh = (p["hue"] + t * 0.2) % 1.0
                col = tuple(int(255 * c) for c in _hsv(hh, 0.55, 1.0))
            else:
                col = (255, 208, 96) if p["warm"] else (170, 220, 255)
            s = p["s"] * (0.7 + 0.6 * tw)
            d.ellipse((x * W - s, y * H - s, x * W + s, y * H + s), fill=col + (a,))
        return ov.filter(ImageFilter.GaussianBlur(2.0))


def _hsv(h, s, v):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    return [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]


def confetti(t, seed=7, n=90):
    """Birthday burst: rotating ribbons of colour."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rnd = random.Random(seed)
    for _ in range(n):
        ang = rnd.uniform(0, math.tau)
        sp = rnd.uniform(0.35, 1.15)
        life = rnd.uniform(0.75, 1.4)
        if t > life:
            continue
        r = ease_out(min(1.0, t / life)) * sp * W * 0.9
        x = W * 0.5 + math.cos(ang) * r
        y = H * 0.44 + math.sin(ang) * r * 0.85 + 240 * t * t
        a = int(255 * max(0.0, 1 - t / life))
        col = tuple(int(255 * c) for c in _hsv(rnd.random(), 0.62, 1.0))
        L = rnd.uniform(10, 30)
        rot = ang + t * rnd.uniform(4, 10)
        d.line((x, y, x + math.cos(rot) * L, y + math.sin(rot) * L),
               fill=col + (a,), width=rnd.randint(4, 9))
    return ov


def sparkle_stars(t, seed=11, n=26, region=(0.05, 0.05, 0.95, 0.75)):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rnd = random.Random(seed)
    for i in range(n):
        x = rnd.uniform(region[0], region[2]) * W
        y = rnd.uniform(region[1], region[3]) * H
        ph = rnd.uniform(0, math.tau)
        k = 0.5 + 0.5 * math.sin(t * 6.5 + ph)
        if k < 0.35:
            continue
        s = rnd.uniform(12, 34) * k
        a = int(245 * k)
        col = (255, 250, 210, a)
        d.line((x - s, y, x + s, y), fill=col, width=3)
        d.line((x, y - s, x, y + s), fill=col, width=3)
        d.line((x - s * .45, y - s * .45, x + s * .45, y + s * .45), fill=(255, 255, 255, a // 2), width=2)
        d.line((x - s * .45, y + s * .45, x + s * .45, y - s * .45), fill=(255, 255, 255, a // 2), width=2)
    return ov.filter(ImageFilter.GaussianBlur(1.0))


def sweat_drops(t, seed=3, n=5):
    """Anime sweat beads for the squirming beat."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rnd = random.Random(seed)
    for i in range(n):
        x = rnd.uniform(0.18, 0.85) * W
        y0 = rnd.uniform(0.16, 0.42) * H
        delay = rnd.uniform(0, 0.5)
        tt = (t - delay) % 0.85
        if t < delay:
            continue
        y = y0 + tt * 520
        a = int(230 * max(0.0, 1 - tt / 0.85))
        s = rnd.uniform(16, 27)
        d.ellipse((x - s * .62, y - s, x + s * .62, y + s), fill=(200, 238, 255, a),
                  outline=(255, 255, 255, a), width=3)
        d.polygon([(x, y - s * 2.0), (x - s * .55, y - s * .2), (x + s * .55, y - s * .2)],
                  fill=(200, 238, 255, a))
        d.ellipse((x - s * .30, y - s * .35, x - s * .02, y + s * .05), fill=(255, 255, 255, a))
    return ov


def jitter_lines(t, seed=5, n=16, alpha=1.0):
    """Trembling motion streaks."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rnd = random.Random(seed)
    for i in range(n):
        side = -1 if i % 2 == 0 else 1
        x = W * (0.5 + side * rnd.uniform(0.30, 0.52))
        y = rnd.uniform(0.10, 0.85) * H
        L = rnd.uniform(60, 210)
        a = int(190 * alpha * (0.5 + 0.5 * math.sin(t * 26 + i)))
        d.line((x - L / 2, y, x + L / 2, y), fill=(255, 255, 255, a), width=rnd.randint(3, 7))
    return ov


def bottom_scrim(strength=0.72, top=0.60):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    a = np.zeros((H, W, 4), np.float32)
    yy = np.linspace(0, 1, H)[:, None]
    k = np.clip((yy - top) / (1 - top), 0, 1) ** 1.5 * strength
    a[:, :, 3] = (k * 255)
    return Image.fromarray(a.astype(np.uint8), "RGBA")


# ---- typography -----------------------------------------------------------
_font_cache = {}


def font(size, path=FONT_PATH):
    key = (size, path)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


def text_layer(lines, size, fill, stroke, stroke_w, glow=None, spacing=1.16,
               align="center", path=FONT_PATH, faux_bold=3):
    f = font(size, path)
    pad = stroke_w * 2 + 60 + (0 if not glow else 40)
    tmp = Image.new("RGBA", (10, 10))
    dd = ImageDraw.Draw(tmp)
    ws, hs = [], []
    for ln in lines:
        b = dd.textbbox((0, 0), ln, font=f, stroke_width=stroke_w)
        ws.append(b[2] - b[0])
        hs.append(b[3] - b[1])
    lh = int(size * spacing)
    tw = max(ws) + pad * 2
    th = lh * len(lines) + pad * 2
    img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        y = pad + i * lh
        if align == "center":
            x = tw // 2
            anchor = "ma"
        else:
            x = pad
            anchor = "la"
        # faux-bold: overdraw the stroke a few times with tiny offsets
        for ox, oy in [(0, 0), (faux_bold, 0), (0, faux_bold), (faux_bold, faux_bold)]:
            d.text((x + ox, y + oy), ln, font=f, fill=fill, anchor=anchor,
                   stroke_width=stroke_w, stroke_fill=stroke)
    if glow:
        g = Image.new("RGBA", img.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(g)
        for i, ln in enumerate(lines):
            y = pad + i * lh
            x = tw // 2 if align == "center" else pad
            gd.text((x, y), ln, font=f, fill=glow + (255,),
                    anchor=("ma" if align == "center" else "la"),
                    stroke_width=stroke_w + 12, stroke_fill=glow + (255,))
        g = g.filter(ImageFilter.GaussianBlur(22))
        out = Image.alpha_composite(g, img)
        return out
    return img


def paste_text(a, layer, cx, cy, scale=1.0, rot=0.0, alpha=1.0, additive=False):
    if alpha <= 0.01:
        return a
    lw, lh = layer.size
    if abs(scale - 1.0) > 0.005:
        layer = layer.resize((max(1, int(lw * scale)), max(1, int(lh * scale))), Image.LANCZOS)
    if abs(rot) > 0.05:
        layer = layer.rotate(rot, resample=Image.BICUBIC, expand=True)
    lw, lh = layer.size
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.paste(layer, (int(cx * W - lw / 2), int(cy * H - lh / 2)), layer)
    return blend_overlay(a, canvas, additive=additive, gain=alpha)


def pop(t, dur=0.22, over=0.34):
    """scale/alpha pop-in curve"""
    if t < 0:
        return 0.0, 0.0
    if t < dur:
        k = t / dur
        return 1.0 + over * (1 - ease_out(k)), min(1.0, k * 2.2)
    return 1.0, 1.0


# --------------------------------------------------------------------------
# assets
# --------------------------------------------------------------------------
print("loading stills ...")
IMG_FLIGHT = load_base("01_flight.png")     # entrance, flame whip, villain below
IMG_BOMB = load_base("02_bomb.png")         # firing yellow liquid at bombs
IMG_BOOM = load_base("03_explosion.png")    # explosion, villain blown away
IMG_FACE = load_base("04_thumbsup.png")     # thumbs-up close-up
IMG_LEAVE = load_base("05_leave.png")       # rocketing away, night sky

EM_WARM = Embers(70, 21, up=True, spread=1.0)
EM_SLOW = Embers(46, 42, up=True, spread=0.55)
EM_TRAIL = Embers(60, 63, up=False, spread=0.9, warm=True)
SCRIM = bottom_scrim(0.66, 0.58)


def end_scrim():
    """Soft dark band behind the closing birthday card."""
    yy = np.linspace(0, 1, H)[:, None]
    k = np.exp(-((yy - 0.505) ** 2) / (2 * 0.105 ** 2)) * 0.80
    a = np.zeros((H, W, 4), np.float32)
    a[:, :, 3] = k * 255
    return Image.fromarray(a.astype(np.uint8), "RGBA")


END_SCRIM = end_scrim()

# dialogue / SFX layers (built once)
TXT = {
    "sfx1": text_layer(["ゴォォッ！！"], 128, (255, 244, 210, 255), (24, 16, 60, 255), 12,
                       glow=(255, 150, 40)),
    "sfx2": text_layer(["ジュゴォッ！！"], 132, (255, 236, 140, 255), (40, 18, 10, 255), 12,
                       glow=(255, 120, 20)),
    "sfx3": text_layer(["ドゴォォォン！！"], 150, (255, 250, 225, 255), (60, 16, 8, 255), 14,
                       glow=(255, 110, 30)),
    "sfx4": text_layer(["シュゴォォ…"], 104, (225, 240, 255, 255), (18, 26, 70, 255), 11,
                       glow=(90, 170, 255)),
    "l1": text_layer(["俺はピーボンバー！！"], 92, (255, 255, 255, 255), (20, 24, 64, 255), 11,
                     glow=(60, 120, 255)),
    "l2": text_layer(["よう氷！", "ハッピーバースデー！！"], 92, (255, 246, 150, 255),
                     (46, 22, 8, 255), 11, glow=(255, 160, 30)),
    "l3": text_layer(["これからも", "よろしくな！"], 92, (255, 255, 255, 255), (20, 24, 64, 255), 11,
                     glow=(60, 140, 255)),
    "l4": text_layer(["やべえ！"], 104, (255, 255, 255, 255), (30, 20, 60, 255), 12,
                     glow=(120, 180, 255)),
    "l5": text_layer(["もれそう！"], 116, (255, 240, 120, 255), (52, 20, 10, 255), 13,
                     glow=(255, 140, 40)),
    "end": text_layer(["HAPPY BIRTHDAY", "氷！！"], 96, (255, 250, 220, 255), (30, 22, 70, 255), 10,
                      glow=(255, 170, 60)),
    "endsub": text_layer(["ヒーロー ピーボンバー 参上"], 44, (215, 228, 255, 255), (12, 16, 46, 255), 6),
}


# --------------------------------------------------------------------------
# per-frame render
# --------------------------------------------------------------------------
def shake(f, start, amp, decay=7.0, seed=0):
    """decaying camera shake -> (dx, dy) in pan units"""
    t = (f - start) / FPS
    if t < 0:
        return 0.0, 0.0
    k = amp * math.exp(-decay * t)
    r = random.Random(int(f) * 977 + seed)
    return (r.uniform(-1, 1) * k, r.uniform(-1, 1) * k)


def render(f):
    t = f / FPS
    txt_ops = []          # deferred: drawn after grade
    ov_add = []           # additive overlays
    ov_norm = []          # normal overlays
    fl = 0.0
    flc = (255, 255, 255)
    chroma = 0.0
    rblur = 0.0
    rfocus = (0.5, 0.45)
    impact = None

    # =====================================================================
    # S1  0-35  (0.00-1.50)  ENTRANCE - flame whip, villain spotted below
    # =====================================================================
    if f < 36:
        p = f / 35.0
        e = ease_out(p)
        z = lerp(1.30, 1.05, e)
        dx, dy = lerp(0.22, 0.0, e), lerp(-0.34, 0.02, e)
        sx, sy = shake(f, 0, 0.05, 9.0, 1)
        img = frame_from(IMG_FLIGHT, z, dx + sx, dy + sy)
        rblur = 0.055 * (1 - ease_out(min(1.0, p * 2.4)))
        rfocus = (0.46, 0.38)
        ov_add.append((speed_lines(max(0.0, 1.0 - p * 1.9), (0.46, 0.36), 3,
                                   (255, 236, 190), inner=0.20), 0.9))
        ov_add.append((EM_WARM.draw(t, 0.55), 0.8))
        fl = max(0.0, 0.85 - f * 0.34)
        flc = (255, 240, 210)
        if 2 <= f <= 20:
            s, a = pop((f - 2) / FPS, 0.16, 0.45)
            txt_ops.append(("sfx1", 0.30, 0.20, s * 0.92, -13, a * min(1.0, (20 - f) / 4.0), True))
        chroma = 5.0 * max(0.0, 1 - p * 3)

    # =====================================================================
    # S2  36-71 (1.50-3.00)  IGNITING THE BOMBS WITH THE YELLOW LIQUID
    # =====================================================================
    elif f < 72:
        i = f - 36
        p = i / 35.0
        z = lerp(1.03, 1.24, ease_in_out(p))
        dx = lerp(0.10, -0.24, ease_in_out(p))
        dy = lerp(0.20, -0.06, ease_in_out(p))
        sx, sy = shake(f, 36, 0.030, 5.0, 2)
        # ignition kicks at i=14 and i=24
        for st in (14, 24):
            s2x, s2y = shake(f, 36 + st, 0.055, 11.0, 3)
            sx += s2x
            sy += s2y
        img = frame_from(IMG_BOMB, z, dx + sx, dy + sy)
        for st, amt in ((14, 0.42), (24, 0.30)):
            if 0 <= i - st < 4:
                fl = max(fl, amt * (1 - (i - st) / 4.0))
                flc = (255, 226, 130)
        ov_add.append((EM_WARM.draw(t, 0.85), 1.0))
        ov_add.append((speed_lines(0.32 * (0.4 + 0.6 * math.sin(p * 3.14)), (0.22, 0.55), 8,
                                   (255, 214, 120), inner=0.30, count=120), 0.55))
        if 14 <= i <= 22:
            ov_add.append((shockwave((i - 14) / 8.0, 0.18, 0.55, (255, 214, 120)), 0.85))
        if 8 <= i <= 30:
            s, a = pop((i - 8) / FPS, 0.15, 0.42)
            txt_ops.append(("sfx2", 0.68, 0.735, s * 0.90, 9, a * min(1.0, (30 - i) / 5.0), True))
        chroma = 3.0 * (1 - p)
        rblur = 0.02 * p

    # =====================================================================
    # S3  72-107 (3.00-4.50)  THE EXPLOSION - villain goes down
    # =====================================================================
    elif f < 108:
        i = f - 72
        p = i / 35.0
        z = lerp(1.42, 1.10, ease_out(min(1.0, p * 1.5)))
        dx, dy = lerp(-0.10, 0.04, ease_out(p)), lerp(0.16, -0.10, ease_out(p))
        sx, sy = shake(f, 72, 0.115, 5.5, 4)
        img = frame_from(IMG_BOOM, z, dx + sx, dy + sy)
        rblur = 0.0 if i < 3 else 0.16 * math.exp(-4.2 * (i / FPS))
        rfocus = (0.52, 0.30)
        if i < 3:
            impact = "hot" if i < 2 else "cool"
        fl = max(fl, (0.34 if i < 3 else 0.62) * math.exp(-7.0 * (i / FPS)))
        flc = (255, 244, 214)
        ov_add.append((shockwave(min(1.0, i / 13.0), 0.52, 0.30), 1.0))
        ov_add.append((speed_lines(max(0.0, 1.15 - p * 1.5), (0.52, 0.30), 12,
                                   (255, 230, 175), inner=0.16, count=220), 1.0))
        ov_add.append((EM_WARM.draw(t, 1.0), 1.1))
        if 4 <= i <= 30:
            s, a = pop((i - 4) / FPS, 0.14, 0.55)
            txt_ops.append(("sfx3", 0.50, 0.185, s * 0.98, -7, a * min(1.0, (30 - i) / 5.0), True))
        chroma = 9.0 * math.exp(-5.0 * (i / FPS))

    # =====================================================================
    # S4  108-197 (4.50-8.25)  THE BIRTHDAY SPEECH  (3 sub-cuts)
    # =====================================================================
    elif f < 198:
        i = f - 108
        ov_norm.append((SCRIM, 1.0))
        # --- 4a: medium, "俺はピーボンバー！！"
        if i < 30:
            p = i / 29.0
            z = lerp(1.00, 1.07, p)
            dx, dy = 0.0, lerp(0.06, -0.02, p)
            sx, sy = shake(f, 108, 0.045, 10.0, 5)
            img = frame_from(IMG_FACE, z, dx + sx, dy + sy)
            fl = max(0.0, 0.34 - i * 0.15)
            ov_add.append((EM_SLOW.draw(t, 0.5), 0.8))
            if i >= 2:
                s, a = pop((i - 2) / FPS, 0.17, 0.38)
                txt_ops.append(("l1", 0.5, 0.845, s * 1.0, -1.5, a, False))
            if i < 6:
                ov_add.append((speed_lines(0.5 * (1 - i / 6.0), (0.5, 0.42), 21,
                                           (255, 255, 255), inner=0.26, count=140), 0.7))
        # --- 4b: tight on the face, "よう氷！ハッピーバースデー！！"
        elif i < 62:
            j = i - 30
            p = j / 31.0
            z = lerp(1.30, 1.38, ease_in_out(p))
            dx, dy = lerp(0.06, -0.04, p), lerp(-0.46, -0.40, p)
            sx, sy = shake(f, 138, 0.05, 9.0, 6)
            img = frame_from(IMG_FACE, z, dx + sx, dy + sy)
            fl = max(0.0, 0.38 - j * 0.17)
            ov_add.append((confetti(j / FPS, 71, 110), 1.0))
            ov_add.append((sparkle_stars(t, 33, 24), 0.9))
            ov_add.append((EM_SLOW.draw(t, 0.6), 0.9))
            if j >= 2:
                s, a = pop((j - 2) / FPS, 0.18, 0.42)
                wob = math.sin(j * 0.9) * 1.6
                txt_ops.append(("l2", 0.5, 0.815, s * 1.0, wob, a, False))
        # --- 4c: pull back, "これからもよろしくな！"
        else:
            j = i - 62
            p = j / 27.0
            z = lerp(1.16, 1.06, ease_out(p))
            dx, dy = 0.0, lerp(-0.14, -0.02, ease_out(p))
            sx, sy = shake(f, 170, 0.04, 10.0, 7)
            img = frame_from(IMG_FACE, z, dx + sx, dy + sy)
            fl = max(0.0, 0.30 - j * 0.14)
            ov_add.append((sparkle_stars(t, 44, 16, (0.05, 0.35, 0.6, 0.8)), 0.8))
            ov_add.append((EM_SLOW.draw(t, 0.5), 0.8))
            if j >= 2:
                s, a = pop((j - 2) / FPS, 0.17, 0.36)
                txt_ops.append(("l3", 0.5, 0.815, s * 1.0, 1.5, a, False))

    # =====================================================================
    # S5  198-233 (8.25-9.75)  THE SQUIRM - "やべえ！もれそう！"
    # =====================================================================
    elif f < 234:
        i = f - 198
        p = i / 35.0
        ov_norm.append((SCRIM, 1.0))
        wob = math.sin(i * 2.35) * 0.055 + math.sin(i * 4.9) * 0.03
        z = 1.24 + math.sin(i * 3.1) * 0.022
        dx = 0.05 + wob
        dy = -0.30 + math.sin(i * 3.9 + 1.2) * 0.05
        rot = math.sin(i * 3.05) * 2.3
        img = frame_from(IMG_FACE, z, dx, dy, rot=rot)
        if i < 4:
            fl = max(fl, 0.40 * (1 - i / 4.0))
            flc = (210, 235, 255)
        ov_add.append((jitter_lines(t, 5, 18, min(1.0, 0.25 + p)), 0.85))
        ov_norm.append((sweat_drops(i / FPS, 3, 6), 0.95))
        if 2 <= i <= 18:
            s, a = pop((i - 2) / FPS, 0.13, 0.5)
            jx = math.sin(i * 5.1) * 0.012
            txt_ops.append(("l4", 0.34 + jx, 0.775, s * 1.0, -8 + math.sin(i * 4) * 2, a, False))
        if i >= 14:
            s, a = pop((i - 14) / FPS, 0.12, 0.6)
            jx = math.sin(i * 6.3) * 0.016
            txt_ops.append(("l5", 0.62 + jx, 0.885, s * 1.0, 7 + math.sin(i * 5) * 2.5, a, False))
        chroma = 2.5 + 2.0 * abs(math.sin(i * 3.0))

    # =====================================================================
    # S6  234-269 (9.75-11.25)  BLASTING OFF INTO THE NIGHT
    # =====================================================================
    else:
        i = f - 234
        p = i / 35.0
        e = ease_out(p)
        z = lerp(1.30, 1.00, e)
        dx, dy = lerp(-0.10, 0.0, e), lerp(0.42, -0.05, e)
        sx, sy = shake(f, 234, 0.06, 8.0, 8)
        img = frame_from(IMG_LEAVE, z, dx + sx, dy + sy)
        rblur = 0.075 * (1 - ease_out(min(1.0, p * 1.6)))
        rfocus = (0.42, 0.62)
        fl = max(0.0, 0.48 - i * 0.20)
        flc = (255, 236, 200)
        ov_add.append((speed_lines(max(0.15, 0.95 - p * 0.8), (0.40, 0.66), 9,
                                   (255, 226, 170), inner=0.18, count=200), 0.9))
        ov_add.append((EM_TRAIL.draw(t, 0.9), 1.0))
        ov_add.append((sparkle_stars(t, 91, 22, (0.05, 0.02, 0.95, 0.5)), 0.75))
        if 2 <= i <= 22:
            s, a = pop((i - 2) / FPS, 0.16, 0.4)
            txt_ops.append(("sfx4", 0.70, 0.30, s * 0.85, 11, a * min(1.0, (22 - i) / 6.0), True))
        # closing card fades up while the picture dims
        if i >= 18:
            k = ease_in_out(min(1.0, (i - 18) / 15.0))
            s, a = pop((i - 18) / FPS, 0.30, 0.20)
            ov_norm.append((END_SCRIM, k * 0.85))
            txt_ops.append(("end", 0.5, 0.46, s * 1.0, 0, k, False))
            txt_ops.append(("endsub", 0.5, 0.565, 1.0, 0, k * 0.95, False))

    # ---------------- composite ----------------
    if rblur > 0.002:
        img = radial_blur(img, rfocus, rblur, 6)
    a = to_np(img)
    if impact:
        a = impact_frame(img, impact)
    a = grade(a)
    a = a * VIG
    if chroma:
        a = chroma_split(a, chroma)
    for ov, g in ov_add:
        a = blend_overlay(a, ov, additive=True, gain=g)
    for ov, g in ov_norm:
        a = blend_overlay(a, ov, additive=False, gain=g)
    if fl > 0.002:
        a = flash(a, fl, flc)

    for key, cx, cy, sc, rot, al, additive in txt_ops:
        a = paste_text(a, TXT[key], cx, cy, sc, rot, al, additive)

    # global fade in / out
    if f < 3:
        a *= (f + 1) / 4.0
    tail = TOTAL - 1 - f
    if tail < 7:
        a *= max(0.0, tail / 7.0) ** 0.9

    return to_img(a)


def _job(f):
    render(f).save(os.path.join(OUT, "f%04d.jpg" % f), quality=94, subsampling=1)
    return f


if __name__ == "__main__":
    import multiprocessing as mp
    n = max(1, min(8, (os.cpu_count() or 2)))
    print("rendering %d frames on %d workers ..." % (TOTAL, n))
    with mp.Pool(n) as pool:
        for k, f in enumerate(pool.imap_unordered(_job, range(TOTAL), chunksize=4)):
            if k % 45 == 0:
                print("  %3d / %d" % (k, TOTAL), flush=True)
    print("done ->", OUT)
