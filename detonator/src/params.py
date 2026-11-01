"""Single source of truth for every dimension (mm). Origin = dial center, +y up.

The FreeCAD build script copies these into the document's Params spreadsheet,
so measured values (MDF thickness, kerf, thread fit) are tuned here.
"""

# --- material / machine -------------------------------------------------
MDF_T = 4.0            # measure your sheet with calipers and update
KERF_COMP = 0.0        # outward offset applied to the cut outline (mm)
DPI = 254              # 10 px/mm, engraving raster resolution
SUPERSAMPLE = 3        # anti-aliasing factor for the raster

# --- dial (from photo, scaled so the bezel is 109 mm) -----------------
R_BEZEL_OUT = 54.5
R_BEZEL_IN = 47.6
R_SECTOR_OUT = 43.4    # light rim runs from here to R_BEZEL_IN
R_CENTER = 19.25       # white center disc
R_CENTER_LINE = 17.6   # thin gray ring inside the center disc
DIVIDER_W = 1.6

# Sector boundaries in degrees (math convention, CCW from +x), listed
# clockwise starting at the green sector's lower edge.
SECTORS = [
    # (name, start_deg, end_deg, tone, icon)
    ("green", 222, 180, 222, ("bunnies", 5)),
    ("yellow", 180, 138, 198, ("bunnies", 4)),
    ("yellow_orange", 138, 96, 172, ("bunnies", 3)),
    ("orange", 96, 54, 146, ("bunnies", 2)),
    ("orange_red", 54, 12, 118, None),
    ("red", 12, -42, 84, ("skull", 1)),
    ("purple", -42, -138, 124, ("warning", 1)),
]

# --- pivot / arrow (3D printed) -----------------------------------------
HOLE_D = 12.4          # laser-cut pivot hole
BOSS_D = 12.0          # arrow boss through the hole
AXIAL_PLAY = 0.3       # boss is MDF_T + AXIAL_PLAY long
CAP_D = 15.0           # hub cap on top of the plate
CAP_H = 2.4
BLADE_T = 2.0
BLADE_TIP_R = 33.0     # center to tip
BLADE_ROOT_W = 12.0
POINTER_ANGLE = 205.0  # pose used for previews only

THREAD_D = 8.0         # male major diameter
THREAD_P = 2.0         # pitch
THREAD_CREST = 0.3     # flat at crest and root
THREAD_CLEAR = 0.25    # radial clearance of the internal thread
CAP_SKIN = 0.8         # material left above the blind threaded hole

FLANGE_D = 16.0
FLANGE_T = 0.5
SLOT_W = 1.2
SLOT_L = 6.0
SLOT_DEPTH = 2.5       # measured from the flange underside

TEST_CLEARANCES = (0.15, 0.25, 0.35)
