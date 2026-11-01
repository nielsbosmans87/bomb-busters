"""Tone calibration coupon: engrave the panel's exact gray levels on scrap MDF.

Run with the project venv:  .venv/Scripts/python detonator/src/tone_test.py
Writes detonator/out/tone_test.svg (embedded engraving + red cut line).
"""
import base64

from PIL import Image, ImageDraw, ImageFont

import params as P
from panel import OUT, PX_MM

# the levels panel.py actually uses, light to dark (255 = untouched)
LEVELS = [255, 232] + [t for _, _, _, t, _ in P.SECTORS] + [18]
LEVELS = sorted(set(LEVELS), reverse=True)

PATCH, GAP, MARGIN, LABEL_H = 9.0, 1.0, 3.0, 5.0  # mm


def main():
    n = len(LEVELS)
    w_mm = 2 * MARGIN + n * PATCH + (n - 1) * GAP
    h_mm = 2 * MARGIN + PATCH + LABEL_H
    W, H = round(w_mm * PX_MM), round(h_mm * PX_MM)
    w_mm, h_mm = W / PX_MM, H / PX_MM
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", round(3.2 * PX_MM))
    except OSError:
        f = ImageFont.load_default()
    for i, tone in enumerate(LEVELS):
        x0 = (MARGIN + i * (PATCH + GAP)) * PX_MM
        y0 = MARGIN * PX_MM
        d.rectangle((x0, y0, x0 + PATCH * PX_MM, y0 + PATCH * PX_MM), fill=tone, outline=18, width=2)
        d.text((x0 + PATCH * PX_MM / 2, y0 + (PATCH + 0.6) * PX_MM), str(tone), fill=18, font=f, anchor="mt")
    png = OUT / "tone_test.png"
    img.save(png, dpi=(P.DPI, P.DPI))

    data = base64.b64encode(png.read_bytes()).decode("ascii")
    r = 1.5
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{w_mm:.3f}mm" height="{h_mm:.3f}mm" viewBox="0 0 {w_mm:.3f} {h_mm:.3f}">
  <!-- Same layer settings as detonator_panel.svg. Numbers = gray value in the panel image. -->
  <image x="0" y="0" width="{w_mm:.3f}" height="{h_mm:.3f}" preserveAspectRatio="none"
         xlink:href="data:image/png;base64,{data}" href="data:image/png;base64,{data}"/>
  <rect x="0.5" y="0.5" width="{w_mm - 1:.3f}" height="{h_mm - 1:.3f}" rx="{r}" fill="none" stroke="#ff0000" stroke-width="0.1"/>
</svg>
"""
    (OUT / "tone_test.svg").write_text(svg, encoding="utf-8")
    print(f"tone test {w_mm:.1f} x {h_mm:.1f} mm, levels {LEVELS}")


if __name__ == "__main__":
    main()
