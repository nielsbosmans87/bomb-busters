"""Build detonator.FCStd and export print files. Runs inside FreeCAD (GUI).

Send it through the FreeCAD MCP / RPC `execute_code`, or paste it in the
FreeCAD Python console. Run detonator/src/panel.py first: it writes the panel
outline and pointer shape this script reads.
"""
import importlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\niels\Documents\GitHub\bomb-busters\detonator")
for d in (ROOT / "cad", ROOT / "src"):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

import FreeCAD
import Mesh
import MeshPart
import Part

import arrow_cad
import params as P

importlib.reload(P)
importlib.reload(arrow_cad)

V = FreeCAD.Vector
OUT = ROOT / "out"
DOC = "Detonator"


def add(doc, name, shape, color=None, visible=True):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    if FreeCAD.GuiUp:
        obj.ViewObject.Visibility = visible
        if color:
            obj.ViewObject.ShapeColor = color
    return obj


def params_sheet(doc):
    sheet = doc.addObject("Spreadsheet::Sheet", "Params")
    row = 1
    for k in sorted(vars(P)):
        v = getattr(P, k)
        if k.isupper() and isinstance(v, (int, float)):
            sheet.set(f"A{row}", k)
            sheet.set(f"B{row}", str(v))
            sheet.setAlias(f"B{row}", k)
            row += 1


def panel_shape(geo):
    pts = [V(x, y, 0) for x, y in geo["outline"]]
    face = Part.Face(Part.makePolygon(pts))
    slab = face.extrude(V(0, 0, -P.MDF_T))
    hole = Part.makeCylinder(geo["hole_d"] / 2, P.MDF_T + 2, V(0, 0, -P.MDF_T - 1))
    return slab.cut(hole)


def write_mesh(shape, path):
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.01,
                                  AngularDeflection=math.radians(8), Relative=False)
    mesh.write(str(path))


def print_oriented(front, back):
    """Front face-down (cap top on the bed), back flange-down."""
    L = arrow_cad.levels(P)
    f = front.copy()
    f.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    f.translate(V(0, 0, L["cap_top"]))
    b = back.copy()
    b.translate(V(0, 0, -L["flange_bot"]))
    return f, b


def build():
    if DOC in FreeCAD.listDocuments():
        FreeCAD.closeDocument(DOC)
    doc = FreeCAD.newDocument(DOC)
    params_sheet(doc)
    geo = json.loads((OUT / "panel_geometry.json").read_text(encoding="utf-8"))

    front = arrow_cad.arrow_front(P, geo["pointer"])
    back = arrow_cad.arrow_back(P)
    panel = panel_shape(geo)

    posed = front.copy()
    posed.rotate(V(0, 0, 0), V(0, 0, 1), P.POINTER_ANGLE)
    add(doc, "Panel", panel, (0.84, 0.70, 0.52))
    add(doc, "ArrowFront", posed, (0.10, 0.10, 0.11))
    add(doc, "ArrowBack", back, (0.92, 0.50, 0.12))

    test = arrow_cad.thread_test(P)
    test.translate(V(120, -20, -10))
    add(doc, "ThreadTest", test, (0.3, 0.6, 0.9), visible=False)

    checks = dict(
        front_valid=front.isValid(), back_valid=back.isValid(),
        overlap_front_back=round(front.common(back).Volume, 4),
        overlap_front_panel=round(posed.common(panel).Volume, 4),
        overlap_back_panel=round(back.common(panel).Volume, 4),
        flange_t=round(P.FLANGE_T, 3),
        radial_play_hole=round((P.HOLE_D - P.BOSS_D) / 2, 3),
        axial_play=P.AXIAL_PLAY,
        back_z=[round(v, 3) for v in (back.optimalBoundingBox().ZMin, back.optimalBoundingBox().ZMax)],
        front_z=[round(v, 3) for v in (front.optimalBoundingBox().ZMin, front.optimalBoundingBox().ZMax)],
    )

    pf, pb = print_oriented(front, back)
    write_mesh(pf, OUT / "arrow_front.stl")
    write_mesh(pb, OUT / "arrow_back.stl")
    write_mesh(arrow_cad.thread_test(P), OUT / "thread_test.stl")
    Part.makeCompound([pf, pb.translated(V(25, 0, 0))]).exportStep(str(OUT / "arrow.step"))

    doc.recompute()
    doc.saveAs(str(ROOT / "cad" / "detonator.FCStd"))
    print(json.dumps(checks))


build()
