"""Compose the review PNGs from panel.py output and the FreeCAD screenshots.

Order: panel.py -> FreeCAD build.py -> FreeCAD preview_cad.py -> previews.py
"""
import json
import math

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

import params as P
from panel import OUT, simulate_burn

SHOTS = OUT / "shots"
SCALE = 0.5  # preview px per engraving px (engraving is 10 px/mm)
BG = (245, 245, 242)


def font(size, bold=False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    try:
        return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
    except OSError:
        return ImageFont.load_default()


def to_px(x, y, ext, s):
    return ((x - ext["x0"]) * 10 * s, (ext["y1"] - y) * 10 * s)


def trim(img, pad=20):
    bg = Image.new(img.mode, img.size, (255, 255, 255))
    x0, y0, x1, y1 = ImageChops.difference(img, bg).getbbox()
    return img.crop((max(x0 - pad, 0), max(y0 - pad, 0), min(x1 + pad, img.width), min(y1 + pad, img.height)))


def panel_views(geo, gray):
    ext = geo["extent"]
    s = SCALE
    # left: engraving file as LightBurn sees it + the red cut line
    left = gray.convert("RGB").resize((round(gray.width * s), round(gray.height * s)), Image.LANCZOS)
    d = ImageDraw.Draw(left)
    d.line([to_px(x, y, ext, s) for x, y in geo["outline"]], fill=(230, 20, 20), width=2)
    r = geo["hole_d"] / 2
    cx, cy = to_px(0, 0, ext, s)
    d.ellipse((cx - r * 10 * s, cy - r * 10 * s, cx + r * 10 * s, cy + r * 10 * s), outline=(230, 20, 20), width=2)

    # right: simulated burn, cut to shape, with the printed pointer on top
    burn = Image.fromarray(simulate_burn(gray, s))
    mask = Image.new("L", burn.size, 0)
    ImageDraw.Draw(mask).polygon([to_px(x, y, ext, s) for x, y in geo["outline"]], fill=255)
    ImageDraw.Draw(mask).ellipse((cx - r * 10 * s, cy - r * 10 * s, cx + r * 10 * s, cy + r * 10 * s), fill=0)
    right = Image.new("RGB", burn.size, BG)
    shadow = Image.new("RGB", burn.size, (190, 190, 185))
    right.paste(shadow, (6, 8), mask)
    right.paste(burn, (0, 0), mask)
    a = math.radians(P.POINTER_ANGLE)
    rot = [(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)) for x, y in geo["pointer"]]
    d = ImageDraw.Draw(right)
    d.polygon([(px + 4, py + 5) for px, py in (to_px(x, y, ext, s) for x, y in rot)], fill=(95, 80, 60))
    d.polygon([to_px(x, y, ext, s) for x, y in rot], fill=(30, 30, 33), outline=(80, 80, 85))
    return left, right


def framed(title, img, subtitle=None, w=None):
    w = w or img.width
    head = 70 if subtitle else 50
    out = Image.new("RGB", (w, img.height + head + 10), BG)
    d = ImageDraw.Draw(out)
    d.text((10, 8), title, font=font(26, True), fill=(30, 30, 30))
    if subtitle:
        d.text((10, 40), subtitle, font=font(18), fill=(90, 90, 90))
    out.paste(img, ((w - img.width) // 2, head))
    return out


def hstack(imgs, gap=30):
    h = max(i.height for i in imgs)
    out = Image.new("RGB", (sum(i.width for i in imgs) + gap * (len(imgs) - 1), h), BG)
    x = 0
    for i in imgs:
        out.paste(i, (x, 0))
        x += i.width + gap
    return out


def vstack(imgs, gap=20):
    w = max(i.width for i in imgs)
    out = Image.new("RGB", (w, sum(i.height for i in imgs) + gap * (len(imgs) - 1)), BG)
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


def notes_panel(lines, w, h):
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    y = 10
    for line in lines:
        bold = line.startswith("#")
        d.text((10, y), line.lstrip("# "), font=font(21 if bold else 19, bold), fill=(30, 30, 30))
        y += 34 if bold else 28
    return img


def main():
    geo = json.loads((OUT / "panel_geometry.json").read_text(encoding="utf-8"))
    gray = Image.open(OUT / "panel_engrave.png")
    left, right = panel_views(geo, gray)
    w_mm, h_mm = gray.width / 10, gray.height / 10
    panel = hstack([framed("Engraving file + cut line", left, f"detonator_panel.svg  {w_mm:.0f} x {h_mm:.0f} mm, engraving @ {P.DPI} dpi + red cut lines"),
                    framed("Simulated burn on MDF", right, "approximation of a dithered CO2 engrave, arrow printed in black")])
    vstack([panel]).save(OUT / "preview_panel.png")

    engage = P.CAP_H - P.CAP_SKIN + P.MDF_T  # shank top to boss bottom
    sec = trim(Image.open(SHOTS / "section.png").convert("RGB"))
    top = trim(Image.open(SHOTS / "exploded_top.png").convert("RGB"))
    bot = trim(Image.open(SHOTS / "exploded_bottom.png").convert("RGB"))
    r_min = P.THREAD_D / 2 - (P.THREAD_P / 2 - P.THREAD_CREST)
    notes = notes_panel([
        "# Thread (custom, printed vertically)",
        f"Ø{P.THREAD_D:g} mm, pitch {P.THREAD_P:g} mm, 90° included angle",
        f"crest/root flats {P.THREAD_CREST} mm, depth {P.THREAD_D / 2 - r_min:.2f} mm",
        f"radial clearance {P.THREAD_CLEAR} mm, engagement {engage:.1f} mm",
        "# Free rotation",
        f"screw clamps the boss, not the MDF: {P.AXIAL_PLAY} mm axial play",
        f"hole Ø{P.HOLE_D} / boss Ø{P.BOSS_D}: {(P.HOLE_D - P.BOSS_D) / 2:.1f} mm radial play",
        "# Back screw",
        f"flange Ø{P.FLANGE_D:g} x {P.FLANGE_T} mm  -> panel stands {P.FLANGE_T} mm proud",
        f"screwdriver slot {P.SLOT_W} x {P.SLOT_L:g} mm, {P.SLOT_DEPTH} mm deep",
        "# Pointer",
        f"hub Ø{P.CAP_D:g}, blade {P.BLADE_T:g} mm, tip {P.BLADE_TIP_R:g} mm from pivot",
    ], 620, max(sec.height + 70, 400))
    row1 = hstack([framed("Cross-section, assembled", sec, f"4 mm MDF (tan), pointer (black), back screw (orange)"), notes])
    row2 = hstack([framed("Exploded, from the front", top), framed("Exploded, from the back (slot)", bot)])
    vstack([row1, row2]).save(OUT / "preview_arrow.png")

    iso = trim(Image.open(SHOTS / "assembly_iso.png").convert("RGB"))
    iso.thumbnail((right.width, 10_000))
    vstack([hstack([framed("Front, as it will look", right), framed("3D assembly (FreeCAD)", iso)])]).save(OUT / "preview_assembly.png")
    print("written preview_panel.png, preview_arrow.png, preview_assembly.png")


if __name__ == "__main__":
    main()
