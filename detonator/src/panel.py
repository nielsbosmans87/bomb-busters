"""Detonator panel: vector geometry, grayscale engraving raster and cut file.

Run with the project venv:  .venv/Scripts/python detonator/src/panel.py
Outputs go to detonator/out/. Tone convention: 255 = untouched MDF (light),
0 = darkest burn. LightBurn dithers the PNG (Jarvis/Stucki).
"""
import base64
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

import params as P

OUT = Path(__file__).resolve().parents[1] / "out"
PX_MM = P.DPI / 25.4


# --- geometry helpers ------------------------------------------------------

def ellipse(cx, cy, w, h, rot=0.0):
    g = affinity.scale(Point(0, 0).buffer(1, 64), w / 2, h / 2)
    return affinity.translate(affinity.rotate(g, rot, origin=(0, 0)), cx, cy)


def annulus_sector(r0, r1, a0, a1, n=96):
    angs = np.radians(np.linspace(a0, a1, n))
    outer = [(r1 * math.cos(a), r1 * math.sin(a)) for a in angs]
    inner = [(r0 * math.cos(a), r0 * math.sin(a)) for a in angs[::-1]]
    return Polygon(outer + inner)


def ring(r0, r1):
    return Point(0, 0).buffer(r1, 256).difference(Point(0, 0).buffer(r0, 256))


def stroke(geom, width):
    """Band of the given width centered on the geometry's boundary."""
    return geom.boundary.buffer(width / 2, 16)


def catmull_rom(pts, n=12):
    pts = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = (np.array(p, float) for p in pts[i - 1:i + 3])
        for t in np.linspace(0, 1, n, endpoint=False):
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t
                              + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(np.array(pts[-2], float))
    return LineString(out)


def stick(x0, y0, angle, length, d=14.4):
    """Dynamite stick from end point (x0, y0) along angle (deg)."""
    a = math.radians(angle)
    cx, cy = x0 + length / 2 * math.cos(a), y0 + length / 2 * math.sin(a)
    body = box(-length / 2, -d / 2, length / 2, d / 2).buffer(-2.2).buffer(2.2)
    body = affinity.translate(affinity.rotate(body, angle, origin=(0, 0)), cx, cy)
    caps = []
    for sgn in (-1, 1):
        ex = cx + sgn * (length / 2 - 0.2 * d) * math.cos(a)
        ey = cy + sgn * (length / 2 - 0.2 * d) * math.sin(a)
        caps.append(ellipse(ex, ey, 0.3 * d, 0.86 * d, angle))
    return dict(body=body, caps=caps, c=(cx, cy), a=a, d=d)


# --- the design -------------------------------------------------------------

TILT = 5  # every stick runs parallel; one bundle passes behind the dial
STICKS = [stick(-73, -24.5, TILT, 146), stick(-81, -10, TILT, 152),
          stick(-85, 4.5, TILT, 162), stick(-78, 19, TILT, 148)]

WIRES = [  # centerlines; each must stay inside the sticks + dial silhouette
    [(-60, 23), (-64, 12), (-61, 1), (-65, -11), (-61, -22), (-60, -27)],     # left tie
    [(60, 34), (64, 24), (61, 13), (65, 2), (61, -8), (62, -15)],             # right tie
    [(-48, 8), (-60, 6), (-69, 9), (-75, 5), (-73, -1), (-68, 1), (-70, 5)],  # left curl
    [(-46, -18), (-58, -15), (-67, -19), (-74, -13)],
    [(47, 14), (58, 17), (65, 15), (70, 18), (69, 22), (65, 21), (66, 17)],   # right curl
    [(48, -6), (58, -5), (64, -1), (68, -5)],
]
WIRE_CORE, WIRE_EDGE = 1.8, 0.6

TABS = [150, 62, -40]  # bezel clamp brackets, degrees


def tab(angle):
    t = box(-7, R_TAB0, 7, R_TAB1).buffer(-1.5).buffer(1.5)
    return affinity.rotate(t, angle - 90, origin=(0, 0))


R_TAB0, R_TAB1 = P.R_BEZEL_OUT - 4, P.R_BEZEL_OUT + 3.8


def bunny(cx, cy):
    head = ellipse(cx, cy - 0.7, 4.3, 3.7)
    ears = [ellipse(cx + s * 1.1, cy + 1.6, 1.5, 3.4, -s * 12) for s in (-1, 1)]
    return unary_union([head] + ears)


BUNNY_LAYOUT = {
    5: [(-5.6, 3), (0, 3), (5.6, 3), (-2.8, -3.4), (2.8, -3.4)],
    4: [(-2.8, 3), (2.8, 3), (-2.8, -3.4), (2.8, -3.4)],
    3: [(0, 3), (-2.8, -3.4), (2.8, -3.4)],
    2: [(-2.8, 0), (2.8, 0)],
}


def bone(p, q):
    shaft = LineString([p, q]).buffer(1.0, 16)
    d = np.subtract(q, p) / np.hypot(*np.subtract(q, p))
    n = np.array([-d[1], d[0]]) * 0.95
    knobs = [Point(np.add(e, s * n) - 0.3 * d * k).buffer(1.25, 32)
             for e, k in ((p, -1), (q, 1)) for s in (-1, 1)]
    return unary_union([shaft] + knobs)


def skull_icon(cx, cy):
    t = lambda g: affinity.translate(g, cx, cy)
    bones = unary_union([bone((-7.5, -2), (7.5, -9)), bone((-7.5, -9), (7.5, -2))])
    head = unary_union([Point(0, 1.4).buffer(4.4, 64),
                        box(-2.4, -4.2, 2.4, -0.5).buffer(0.8)])
    eyes = unary_union([ellipse(-1.7, 1.0, 2.3, 2.5), ellipse(1.7, 1.0, 2.3, 2.5)])
    nose = Polygon([(-0.6, -1.4), (0.6, -1.4), (0, -0.4)])
    return dict(bones=t(bones), head=t(head), holes=t(unary_union([eyes, nose])))


def warning_icons(r=31.0):
    ax, ay = r * math.cos(math.radians(-114)), r * math.sin(math.radians(-114))
    arc = catmull_rom([(ax + 5.5, ay - 3.2), (ax + 1, ay - 3.6), (ax - 3.2, ay - 1.2), (ax - 4.6, ay + 2.6)])
    head = Polygon([(ax - 7.4, ay + 1.8), (ax - 2.2, ay + 3.6), (ax - 5.8, ay + 6.8)])
    arrow = unary_union([arc.buffer(0.95, 16), head])
    tx, ty = r * math.cos(math.radians(-67)), r * math.sin(math.radians(-67))
    s = 13.0
    tri = Polygon([(tx - s / 2, ty - s * 0.36), (tx + s / 2, ty - s * 0.36), (tx, ty + s * 0.5)])
    tri_line = stroke(tri.buffer(-0.6, join_style=2).buffer(0.6), 1.5)
    bang = unary_union([LineString([(tx, ty + 2.4), (tx, ty - 1.4)]).buffer(0.75),
                        Point(tx, ty - 3.2).buffer(0.85)])
    return unary_union([arrow, tri_line, bang])


def pointer_shape():
    """Arrow pointer in its own frame: hub at origin, tip on +x."""
    w = P.BLADE_ROOT_W / 2
    blade = Polygon([(0, w), (P.BLADE_TIP_R, 0), (0, -w)]).buffer(-0.4).buffer(0.4)
    return unary_union([blade, Point(0, 0).buffer(P.CAP_D / 2, 128)])


def outline():
    parts = [Point(0, 0).buffer(P.R_BEZEL_OUT, 512)]
    parts += [tab(a) for a in TABS]
    parts += [s["body"] for s in STICKS]
    g = unary_union(parts).buffer(2.0, 32).buffer(-2.0, 32)  # round off slivers
    if isinstance(g, MultiPolygon):
        g = max(g.geoms, key=lambda p: p.area)
    g = Polygon(g.exterior)
    # wires are drawn on top only; they must not stick out past the silhouette
    for i, w in enumerate(WIRES):
        out = catmull_rom(w).buffer(WIRE_CORE / 2 + WIRE_EDGE, 16).difference(g.buffer(-0.3)).area
        if out > 0.01:
            raise ValueError(f"wire {i} sticks out of the outline by {out:.2f} mm2")
    return g.buffer(P.KERF_COMP, 32) if P.KERF_COMP else g


# --- raster engine -------------------------------------------------------------

class Canvas:
    def __init__(self, bounds, margin=2.0):
        x0, y0, x1, y1 = bounds
        self.x0, self.y1 = x0 - margin, y1 + margin
        self.w_mm, self.h_mm = (x1 - x0) + 2 * margin, (y1 - y0) + 2 * margin
        # final pixel grid is integral; supersampled grid is an exact multiple
        self.W, self.H = round(self.w_mm * PX_MM), round(self.h_mm * PX_MM)
        self.w_mm, self.h_mm = self.W / PX_MM, self.H / PX_MM
        self.s = PX_MM * P.SUPERSAMPLE
        self.img = np.full((self.H * P.SUPERSAMPLE, self.W * P.SUPERSAMPLE), 255.0, np.float32)

    def _mask(self, geom):
        if geom.is_empty:
            return None, None
        bx0, by0, bx1, by1 = geom.bounds
        c0 = max(int((bx0 - self.x0) * self.s) - 1, 0)
        r0 = max(int((self.y1 - by1) * self.s) - 1, 0)
        c1 = min(int((bx1 - self.x0) * self.s) + 2, self.img.shape[1])
        r1 = min(int((self.y1 - by0) * self.s) + 2, self.img.shape[0])
        if c1 <= c0 or r1 <= r0:
            return None, None
        tf = lambda cs: [((x - self.x0) * self.s - c0, (self.y1 - y) * self.s - r0) for x, y in cs]
        polys = geom.geoms if hasattr(geom, "geoms") else [geom]
        mask = np.zeros((r1 - r0, c1 - c0), bool)
        for poly in polys:
            if poly.geom_type != "Polygon":
                continue
            # one image per polygon so its holes cannot erase a sibling polygon
            m = Image.new("1", (c1 - c0, r1 - r0), 0)
            d = ImageDraw.Draw(m)
            d.polygon(tf(poly.exterior.coords), fill=1)
            for hole in poly.interiors:
                d.polygon(tf(hole.coords), fill=0)
            mask |= np.array(m, bool)
        return (slice(r0, r1), slice(c0, c1)), mask

    def paint(self, geom, tone):
        """tone: constant, or f(X, Y) -> array in mm coordinates."""
        sl, m = self._mask(geom)
        if sl is None:
            return
        region = self.img[sl]
        if callable(tone):
            rows = np.arange(sl[0].start, sl[0].stop) + 0.5
            cols = np.arange(sl[1].start, sl[1].stop) + 0.5
            X, Y = np.meshgrid(self.x0 + cols / self.s, self.y1 - rows / self.s)
            region[m] = np.clip(tone(X, Y), 0, 255)[m]
        else:
            region[m] = tone

    def final(self):
        img = Image.fromarray(self.img.clip(0, 255).astype(np.uint8))
        return img.resize((self.W, self.H), Image.BOX)


def stick_tone(s, base=150):
    """Red paper cylinder: mid tone, darker edges, soft highlight blotches."""
    cx, cy = s["c"]
    a, r = s["a"], s["d"] / 2

    def f(X, Y):
        v = ((X - cx) * -math.sin(a) + (Y - cy) * math.cos(a)) / r
        u = (X - cx) * math.cos(a) + (Y - cy) * math.sin(a)
        v = np.clip(v, -1, 1)
        blotch = 0.6 + 0.4 * np.cos(u * 0.35 + cx)
        shade = base - 70 * v ** 4 + 60 * blotch * np.exp(-((v - 0.38) / 0.2) ** 2)
        return shade
    return f


def metal_tone(X, Y):
    th = np.arctan2(Y, X)
    r = np.hypot(X, Y)
    base = 170 + 50 * np.cos(th - math.radians(135))
    return base + 35 * np.exp(-((r - (P.R_BEZEL_OUT - 2.6)) / 0.7) ** 2)


def sector_tone(base):
    def f(X, Y):
        u = (np.hypot(X, Y) - P.R_CENTER) / (P.R_SECTOR_OUT - P.R_CENTER)
        return base + 14 * (0.5 - u)
    return f


def draw_panel(cv, cut):
    BLACK = 18
    cv.paint(cut, 232)  # light background tint where nothing else is drawn

    for s in STICKS:
        cv.paint(s["body"], stick_tone(s))
        for cap in s["caps"]:
            # crimped paper end: lighter than the body so the stick reads solid
            cv.paint(cap.intersection(s["body"]), 196)
            cv.paint(stroke(cap, 0.45).intersection(s["body"]), BLACK)
        cv.paint(stroke(s["body"], 0.8), BLACK)

    for w in WIRES:
        line = catmull_rom(w)
        cv.paint(line.buffer(WIRE_CORE / 2 + WIRE_EDGE, 16), BLACK)
        cv.paint(line.buffer(WIRE_CORE / 2, 16), 252)

    for a in TABS:
        t = tab(a)
        cv.paint(t, metal_tone)
        band = affinity.rotate(box(-7, R_TAB1 - 3.2, 7, R_TAB1 - 2.2), a - 90, origin=(0, 0))
        cv.paint(band.intersection(t), 110)
        cv.paint(stroke(t, 0.8), BLACK)

    bezel = ring(P.R_BEZEL_IN, P.R_BEZEL_OUT)
    cv.paint(bezel, metal_tone)
    cv.paint(ring(P.R_BEZEL_OUT - 0.9, P.R_BEZEL_OUT + 0.3), BLACK)
    cv.paint(ring(P.R_SECTOR_OUT, P.R_BEZEL_IN), 214)
    cv.paint(ring(P.R_BEZEL_IN - 0.3, P.R_BEZEL_IN + 0.5), BLACK)

    for name, a0, a1, tone, icon in P.SECTORS:
        cv.paint(annulus_sector(P.R_CENTER, P.R_SECTOR_OUT, a0, a1), sector_tone(tone))
    for _, a0, _, _, _ in P.SECTORS:
        a = math.radians(a0)
        seg = LineString([(P.R_CENTER * math.cos(a), P.R_CENTER * math.sin(a)),
                          (P.R_SECTOR_OUT * math.cos(a), P.R_SECTOR_OUT * math.sin(a))])
        cv.paint(seg.buffer(P.DIVIDER_W / 2, cap_style=2), 250)
    cv.paint(ring(P.R_SECTOR_OUT - 0.2, P.R_SECTOR_OUT + 0.2), 120)

    cv.paint(Point(0, 0).buffer(P.R_CENTER, 256), 247)
    cv.paint(ring(P.R_CENTER - 0.25, P.R_CENTER + 0.1), 150)
    cv.paint(ring(P.R_CENTER_LINE - 0.25, P.R_CENTER_LINE + 0.25), 180)

    for name, a0, a1, tone, icon in P.SECTORS:
        if not icon:
            continue
        mid = math.radians((a0 + a1) / 2)
        cx, cy = 31.5 * math.cos(mid), 31.5 * math.sin(mid)
        kind, n = icon
        if kind == "bunnies":
            g = unary_union([bunny(cx + dx, cy + dy) for dx, dy in BUNNY_LAYOUT[n]])
            cv.paint(g.buffer(0.5), BLACK)
            cv.paint(g, 244)
        elif kind == "skull":
            sk = skull_icon(cx, cy + 1.5)
            cv.paint(unary_union([sk["bones"], sk["head"]]).buffer(0.9), BLACK)
            cv.paint(sk["bones"], 248)
            cv.paint(sk["head"].buffer(0.35).difference(sk["head"]), BLACK)
            cv.paint(sk["head"], 248)
            cv.paint(sk["holes"], BLACK)
        elif kind == "warning":
            cv.paint(warning_icons(), 238)

    cv.paint(Point(0, 0).buffer(P.HOLE_D / 2, 128), 255)  # cut away anyway
    # nothing outside the cut line
    outside = box(cv.x0 - 1, cv.y1 - cv.h_mm - 1, cv.x0 + cv.w_mm + 1, cv.y1 + 1).difference(cut)
    cv.paint(outside, 255)


# --- exports ---------------------------------------------------------------------

def svg_path(poly_coords, cv):
    pts = [(x - cv.x0, cv.y1 - y) for x, y in poly_coords]
    return "M " + " L ".join(f"{x:.3f},{y:.3f}" for x, y in pts) + " Z"


def write_job_svg(cut, cv, png_path, path):
    """One file for the cutter: embedded grayscale engraving + red cut lines."""
    hole = Point(0, 0).buffer(P.HOLE_D / 2, 256)
    w, h = cv.w_mm, cv.h_mm
    data = base64.b64encode(png_path.read_bytes()).decode("ascii")
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{w:.3f}mm" height="{h:.3f}mm" viewBox="0 0 {w:.3f} {h:.3f}">
  <!-- Engrave: grayscale image ({P.DPI} dpi, 1:1). Cut: red, inner hole first, then outline. -->
  <image x="0" y="0" width="{w:.3f}" height="{h:.3f}" preserveAspectRatio="none"
         xlink:href="data:image/png;base64,{data}" href="data:image/png;base64,{data}"/>
  <path d="{svg_path(hole.exterior.coords, cv)}" fill="none" stroke="#ff0000" stroke-width="0.1"/>
  <path d="{svg_path(cut.exterior.coords, cv)}" fill="none" stroke="#ff0000" stroke-width="0.1"/>
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def simulate_burn(gray, scale):
    """Approximate look of a dithered burn on MDF (for previews only)."""
    g = np.asarray(gray.resize((round(gray.width * scale), round(gray.height * scale)), Image.LANCZOS),
                   np.float32) / 255
    b = (1 - g) ** 0.85
    mdf = np.array([214, 178, 134], np.float32)
    burnt = np.array([52, 30, 18], np.float32)
    rgb = mdf * (1 - b[..., None]) + burnt * b[..., None]
    rng = np.random.default_rng(1)
    rgb += rng.normal(0, 4, rgb.shape[:2])[..., None]
    return rgb.clip(0, 255).astype(np.uint8)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cut = outline()
    cv = Canvas(cut.bounds)
    draw_panel(cv, cut)
    gray = cv.final()
    gray.save(OUT / "panel_engrave.png", dpi=(P.DPI, P.DPI))
    write_job_svg(cut, cv, OUT / "panel_engrave.png", OUT / "detonator_panel.svg")

    geo = dict(outline=list(cut.exterior.coords), hole_d=P.HOLE_D,
               pointer=list(pointer_shape().exterior.coords),
               extent=dict(x0=cv.x0, y1=cv.y1, w=cv.w_mm, h=cv.h_mm))
    (OUT / "panel_geometry.json").write_text(json.dumps(geo), encoding="utf-8")

    x0, y0, x1, y1 = cut.bounds
    print(f"panel {x1 - x0:.1f} x {y1 - y0:.1f} mm, raster {gray.width} x {gray.height} px @ {P.DPI} dpi")
    return cut, cv, gray


if __name__ == "__main__":
    main()
