"""Part-workbench geometry for the two-part arrow. Runs inside FreeCAD.

Assembled frame: plate top surface at z = 0, plate bottom at z = -MDF_T,
pivot on the z axis, pointer tip along +x. The axial play is split evenly
above and below the plate.
"""
import math

import FreeCAD
import Part

V = FreeCAD.Vector
Z_REF = -30.0  # common helix phase origin so internal/external threads mesh


def thread_rod(r_min, r_maj, z0, z1, pitch, crest):
    """Externally threaded rod between z0 and z1 (truncated 90-degree thread)."""
    h = r_maj - r_min
    w_root = crest + 2 * h          # 45-degree flanks
    over = 0.1                      # sink the profile into the core
    turns = math.ceil((z1 - Z_REF) / pitch) + 2
    helix = Part.makeHelix(pitch, turns * pitch, r_min)
    prof = Part.makePolygon([
        V(r_min - over, 0, -w_root / 2 - over), V(r_maj, 0, -crest / 2),
        V(r_maj, 0, crest / 2), V(r_min - over, 0, w_root / 2 + over),
        V(r_min - over, 0, -w_root / 2 - over)])
    tooth = Part.Wire(helix).makePipeShell([prof], True, True)
    core = Part.makeCylinder(r_min, turns * pitch)
    rod = core.fuse(tooth)
    rod.translate(V(0, 0, Z_REF - pitch))
    return rod.common(Part.makeCylinder(r_maj + 1, z1 - z0, V(0, 0, z0)))


def male_profile(p):
    r_maj = p.THREAD_D / 2
    return r_maj - (p.THREAD_P / 2 - p.THREAD_CREST), r_maj


def levels(p):
    gap = p.AXIAL_PLAY / 2
    cap_bot = gap
    cap_top = cap_bot + p.CAP_H
    boss_bot = cap_bot - (p.MDF_T + p.AXIAL_PLAY)
    hole_top = cap_top - p.CAP_SKIN
    return dict(cap_bot=cap_bot, cap_top=cap_top, boss_bot=boss_bot, hole_top=hole_top,
                flange_bot=boss_bot - p.FLANGE_T)


def arrow_front(p, pointer_pts):
    L = levels(p)
    cap = Part.makeCylinder(p.CAP_D / 2, p.CAP_H, V(0, 0, L["cap_bot"]))
    blade_face = Part.Face(Part.makePolygon([V(x, y, 0) for x, y in pointer_pts]))
    blade = blade_face.extrude(V(0, 0, p.BLADE_T))
    blade.translate(V(0, 0, L["cap_top"] - p.BLADE_T))
    boss = Part.makeCylinder(p.BOSS_D / 2, L["cap_bot"] - L["boss_bot"], V(0, 0, L["boss_bot"]))
    body = cap.fuse([blade, boss]).removeSplitter()

    r_min, r_maj = male_profile(p)
    c = p.THREAD_CLEAR
    void = thread_rod(r_min + c, r_maj + c, L["boss_bot"] - 1, L["hole_top"], p.THREAD_P, p.THREAD_CREST)
    lead_in = Part.makeCone(r_maj + c + 0.5, r_min + c, r_maj - r_min + 0.5,
                            V(0, 0, L["boss_bot"] - 0.01))
    return body.cut(void.fuse(lead_in))


def arrow_back(p):
    L = levels(p)
    flange = Part.makeCylinder(p.FLANGE_D / 2, p.FLANGE_T, V(0, 0, L["flange_bot"]))
    r_min, r_maj = male_profile(p)
    shank_top = L["hole_top"] - p.AXIAL_PLAY  # never bottoms out in the blind hole
    rod = thread_rod(r_min, r_maj, L["boss_bot"] - 0.05, shank_top, p.THREAD_P, p.THREAD_CREST)
    # tip chamfer down past the thread root; steeper than 45 degrees so the cone
    # never runs parallel to a thread flank (that leaves sliver faces in the STL)
    ch = r_maj - r_min + 0.3
    ch_h = 1.6 * ch
    z_ch = shank_top - ch_h
    bullet = Part.makeCylinder(r_maj + 1, z_ch - L["flange_bot"], V(0, 0, L["flange_bot"])).fuse(
        Part.makeCone(r_maj + 0.01, r_maj - ch, ch_h, V(0, 0, z_ch)))
    body = flange.fuse(rod.common(bullet)).removeSplitter()
    slot = Part.makeBox(p.SLOT_L, p.SLOT_W, p.SLOT_DEPTH,
                        V(-p.SLOT_L / 2, -p.SLOT_W / 2, L["flange_bot"] - 0.01))
    return body.cut(slot)


def thread_test(p):
    """Bolt + nut pairs per clearance; the nut carries 1/2/3 notches."""
    r_min, r_maj = male_profile(p)
    parts = []
    for i, c in enumerate(p.TEST_CLEARANCES):
        x = i * 22.0
        bolt = Part.makeCylinder(7, 1.2, V(x, 0, 0)).fuse(
            thread_rod(r_min, r_maj, 1.19, 9, p.THREAD_P, p.THREAD_CREST).translated(V(x, 0, 0)))
        nut = Part.makePolygon([V(x + 7.5 * math.cos(math.radians(a)), 15 + 7.5 * math.sin(math.radians(a)), 0)
                                for a in range(0, 361, 60)])
        nut = Part.Face(nut).extrude(V(0, 0, 6))
        void = thread_rod(r_min + c, r_maj + c, -1, 7, p.THREAD_P, p.THREAD_CREST).translated(V(x, 15, 0))
        nut = nut.cut(void)
        for k in range(i + 1):
            nut = nut.cut(Part.makeBox(1.0, 2.0, 1.0, V(x - 2.5 + 2 * k, 15 + 5.5, 5.01)))
        parts += [bolt.removeSplitter(), nut]
    return Part.makeCompound(parts)
