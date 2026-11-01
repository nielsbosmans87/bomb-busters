"""Render arrow preview screenshots from FreeCAD (GUI). Run after build.py."""
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\niels\Documents\GitHub\bomb-busters\detonator")
for d in (ROOT / "cad", ROOT / "src"):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

import FreeCAD
import FreeCADGui as Gui
import Part
from PySide import QtGui

import arrow_cad
import params as P

importlib.reload(P)
importlib.reload(arrow_cad)

V = FreeCAD.Vector
SHOTS = ROOT / "out" / "shots"
DOC = "DetonatorPreview"
TAN, BLACK, ORANGE = (0.84, 0.70, 0.52), (0.16, 0.16, 0.17), (0.92, 0.50, 0.12)


def show(doc, name, shape, color, transparency=0):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    obj.ViewObject.ShapeColor = color
    obj.ViewObject.Transparency = transparency
    obj.ViewObject.LineColor = (0.05, 0.05, 0.05)
    return obj


def shot(doc, objs, view, name, w=1400, h=1000, zoom=None):
    for o in doc.Objects:
        o.ViewObject.Visibility = o in objs
    v = Gui.getDocument(doc.Name).ActiveView
    v.setCameraType("Orthographic")
    doc.recompute()
    path = str(SHOTS / f"{name}.png")
    for _ in range(4):  # the view occasionally renders blank right after adding objects
        Gui.updateGui()  # new objects must reach the scene graph before fitAll
        getattr(v, view)()
        v.fitAll()
        Gui.updateGui()
        for _ in range(zoom or 0):
            v.zoomIn()
        Gui.updateGui()
        v.saveImage(path, w, h, "White")
        if not is_blank(path):
            return
    raise RuntimeError(f"{name}: screenshot stayed blank")


def is_blank(path):
    img = QtGui.QImage(path)
    first = img.pixel(0, 0)
    return all(img.pixel(x, y) == first
               for x in range(0, img.width(), 25) for y in range(0, img.height(), 25))


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    if DOC in FreeCAD.listDocuments():
        FreeCAD.closeDocument(DOC)
    doc = FreeCAD.newDocument(DOC)
    Gui.getDocument(DOC).ActiveView.setAxisCross(False)
    geo = json.loads((ROOT / "out" / "panel_geometry.json").read_text(encoding="utf-8"))

    front = arrow_cad.arrow_front(P, geo["pointer"])
    back = arrow_cad.arrow_back(P)
    coupon = Part.makeCylinder(24, P.MDF_T, V(0, 0, -P.MDF_T)).cut(
        Part.makeCylinder(P.HOLE_D / 2, P.MDF_T + 2, V(0, 0, -P.MDF_T - 1)))

    exploded = [front.translated(V(0, 0, 22)), coupon, back.translated(V(0, 0, -22))]
    colors = (BLACK, TAN, ORANGE)
    top = [show(doc, f"ExTop{i}", s, c) for i, (s, c) in enumerate(zip(exploded, colors))]
    shot(doc, top, "viewIsometric", "exploded_top")
    # underside: flip the shapes instead of fighting the camera
    flipped = [s.copy() for s in exploded]
    for s in flipped:
        s.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    under = [show(doc, f"ExBot{i}", s, c) for i, (s, c) in enumerate(zip(flipped, colors))]
    shot(doc, under, "viewIsometric", "exploded_bottom")

    half = Part.makeBox(200, 100, 200, V(-100, 0, -100))
    sec = [show(doc, "SecFront", front.common(half), BLACK),
           show(doc, "SecPlate", coupon.common(half), TAN),
           show(doc, "SecBack", back.common(half), ORANGE)]
    shot(doc, sec, "viewFront", "section", 1600, 900, zoom=3)

    if "Detonator" in FreeCAD.listDocuments():  # full assembly from build.py
        main_doc = FreeCAD.getDocument("Detonator")
        Gui.getDocument("Detonator").ActiveView.setAxisCross(False)
        objs = [main_doc.getObject(n) for n in ("Panel", "ArrowFront", "ArrowBack")]
        shot(main_doc, objs, "viewIsometric", "assembly_iso", 1600, 1100)
        main_doc.getObject("ThreadTest").ViewObject.Visibility = False

    print("ok", sorted(p.name for p in SHOTS.iterdir()))


main()
