"""Halftone illustrations (newspaper-dot look) for carousel photo cards.

Usage:
  python3 halftone.py photo <in.jpg> <out.png>      # halftone a real photo (press kit / CC / user-supplied)
  python3 halftone.py draw <name> <out.png>         # draw a built-in illustration: earbuds | headphones | waves | chip | phone | robot
"""
import sys, math
from PIL import Image, ImageDraw, ImageFilter, ImageOps

PAPER = (240, 236, 228)
INK = (24, 22, 20)


def halftone(gray: Image.Image, cell: int = 11, scale: float = 1.0) -> Image.Image:
    """gray: L-mode image, 0 = black. Returns RGB halftone on paper colour."""
    w, h = gray.size
    out = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(out)
    small = gray.resize((max(1, w // cell), max(1, h // cell)), Image.BILINEAR)
    px = small.load()
    for j in range(small.size[1]):
        for i in range(small.size[0]):
            v = px[i, j] / 255.0
            dark = 1 - v
            if dark < 0.04:
                continue
            if dark > 0.93:
                d.rectangle([i * cell, j * cell, (i + 1) * cell, (j + 1) * cell], fill=INK)
                continue
            r = math.sqrt(dark) * cell * 0.72 * scale
            cx, cy = i * cell + cell / 2, j * cell + cell / 2
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=INK)
    return out


def photo(src, dst, w=820, h=520):
    im = Image.open(src).convert("L")
    im = ImageOps.fit(im, (w, h), Image.LANCZOS)
    im = ImageOps.autocontrast(im, cutoff=2)
    halftone(im, cell=9).save(dst)


def radial_blob(d, box, inner, outer, steps=40):
    x0, y0, x1, y1 = box
    for k in range(steps):
        t = k / steps
        c = int(outer + (inner - outer) * t)
        dx = (x1 - x0) * t * 0.35
        dy = (y1 - y0) * t * 0.35
        d.ellipse([x0 + dx * 0.6, y0 + dy * 0.5, x1 - dx * 1.4, y1 - dy * 1.5], fill=c)


def draw(name, dst, w=820, h=520):
    g = Image.new("L", (w, h), 245)
    d = ImageDraw.Draw(g)
    # soft background vignette
    for k in range(30):
        c = 245 - k * 2
        d.rectangle([0, h - 150 + k * 5, w, h], fill=c)
    if name == "earbuds":
        # open charging case seen from front, lid up
        d.rounded_rectangle([230, 290, 590, 470], 80, fill=55)
        d.rounded_rectangle([245, 300, 575, 340], 18, fill=110)
        d.rounded_rectangle([250, 120, 570, 300], 80, fill=95)
        d.rounded_rectangle([270, 140, 550, 280], 60, fill=150)
        d.ellipse([395, 395, 425, 425], fill=200)
        # two buds sitting in the case
        for cx in (340, 480):
            d.ellipse([cx - 52, 200, cx + 52, 300], fill=35)
            d.ellipse([cx - 30, 222, cx + 10, 262], fill=120)
            d.rounded_rectangle([cx - 16, 280, cx + 16, 340], 16, fill=35)
    elif name == "headphones":
        d.arc([180, 60, 640, 520], 190, 350, fill=30, width=38)
        for cx in (215, 605):
            radial_blob(d, (cx - 85, 250, cx + 85, 470), 200, 35)
        d.line([215, 470, 260, 520], fill=30, width=10)
    elif name == "waves":
        for k, amp in enumerate([150, 110, 70]):
            pts = [(x, h / 2 + amp * math.sin(x / (55 + k * 20)) * math.sin(x / 260)) for x in range(0, w, 4)]
            d.line(pts, fill=20 + k * 50, width=26 - k * 6)
    elif name == "chip":
        radial_blob(d, (260, 110, 560, 410), 160, 30)
        d.rectangle([300, 150, 520, 370], fill=30)
        d.rectangle([340, 190, 480, 330], fill=150)
        for k in range(7):
            o = 165 + k * 30
            for seg in ([o, 110, o + 12, 150], [o, 370, o + 12, 410], [220, o, 300, o + 12], [520, o, 600, o + 12]):
                d.rectangle(seg, fill=50)
    elif name == "phone":
        d.rounded_rectangle([300, 40, 520, 500], 40, fill=25)
        radial_blob(d, (320, 70, 500, 470), 230, 120)
    elif name == "robot":
        radial_blob(d, (290, 80, 530, 300), 220, 50)
        for cx in (360, 460):
            d.ellipse([cx - 22, 170, cx + 22, 214], fill=20)
        radial_blob(d, (250, 300, 570, 520), 200, 40)
    g = g.filter(ImageFilter.GaussianBlur(3))
    halftone(g, cell=11).save(dst)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "photo":
        photo(sys.argv[2], sys.argv[3])
    else:
        draw(sys.argv[2], sys.argv[3])
