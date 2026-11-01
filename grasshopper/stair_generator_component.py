"""STAIR GENERATOR (all in one) - Grasshopper Python 3 script component (Rhino 8).

Paste this whole script into a new Python 3 Script component and run it. The
component sets itself up: it adds its inputs and outputs, places drop-downs,
sliders, point/curve parameters, a Bake button and a report panel, and wires
them all. After that, change the controls and the stair updates.

Two ways to place the stair (like Revit):
  1. By point: set `start` (right-click > Set one Point) and `rotation`.
  2. By path ("Run" tool): draw the walk line in Rhino and set it on `path`
     (right-click > Set one Curve). Line = straight, polyline with one 90° turn = L,
     two 90° turns = U, arc = spiral. `location` says which line you drew:
     the centre line, or the left/right edge looking up the stair. The tread depth
     and flight split are stretched so the stair fills the path.
     The path overrides start, rotation, stair_type and turn.

`boundary` (closed curve, optional) checks that every tread and landing is inside it.
`opening` (closed curve, optional) is the floor opening above, for the headroom check.
`rules` (optional) is the path of a rule file; empty = example file (PLACEHOLDERS).

Slider values are in model units (mm). 0 on riser_count, tread_depth,
flight1_risers or landing_depth means "auto".

Bake: press the Bake button. Everything goes to `bake_layer` (default
03_ARCH::A-STAIR) as one group. Pick a `text_layer` to put the step numbers, arrows
and UP label on another layer. Missing layers are created.

DESIGN AID ONLY - NOT A CODE COMPLIANCE CERTIFICATION.
"""

# Folder that contains the 'stairgen' and 'stairgen_rhino' folders.
STAIRGEN_PATH = r"F:\CMC\06_SOFTWARE\04_GRASSHOPPER\SCRIPT\stair-generator\stair-generator"
# True = rebuild the controls once (replaces the controls, resets their values). Set back to False.
REBUILD = False

import importlib
import sys

importlib.invalidate_caches()  # see library files added while Rhino is open
if STAIRGEN_PATH not in sys.path:
    sys.path.insert(0, STAIRGEN_PATH)
for _name in list(sys.modules):  # re-import so edits to the library show up
    if _name.split(".")[0] in ("stairgen", "stairgen_rhino"):
        del sys.modules[_name]

from stairgen_rhino import gh as _sg  # noqa: E402

# --- layer library (Parent::Child), edit to suit -----------------------------------
LAYERS = [
    "00_REF::REF-CAD", "00_REF::REF-IMAGE", "00_REF::REF-GRID",
    "01_SITE::C-TOPO", "01_SITE::C-PROP", "01_SITE::C-ROAD", "01_SITE::C-CONTEXT",
    "02_MASSING::M-MASS", "02_MASSING::M-FLOR-PLATE", "02_MASSING::M-OPTION-A", "02_MASSING::M-OPTION-B",
    "03_ARCH::A-WALL-EXT", "03_ARCH::A-WALL-INT", "03_ARCH::A-FLOR", "03_ARCH::A-ROOF", "03_ARCH::A-DOOR",
    "03_ARCH::A-GLAZ", "03_ARCH::A-STAIR", "03_ARCH::A-RAIL", "03_ARCH::A-CEIL",
    "04_STRUCT::S-FNDN", "04_STRUCT::S-COLS", "04_STRUCT::S-BEAM", "04_STRUCT::S-SLAB",
    "05_FACADE::F-PANEL", "05_FACADE::F-MULLION", "05_FACADE::F-FIN",
    "06_INTERIOR::I-FURN", "06_INTERIOR::I-FIXT",
    "07_LANDSCAPE::L-PLNT", "07_LANDSCAPE::L-HARD",
    "08_GH::GH-INPUT", "08_GH::GH-MASSING", "08_GH::GH-MASSING::GH-MASSING-FLOR",
    "08_GH::GH-FACADE", "08_GH::GH-FACADE::GH-FACADE-PANEL", "08_GH::GH-FACADE::GH-FACADE-MULLION",
    "08_GH::GH-FACADE::GH-FACADE-FIN", "08_GH::GH-STRUCT", "08_GH::GH-STRUCT::GH-STRUCT-COLS",
    "08_GH::GH-STRUCT::GH-STRUCT-BEAM", "08_GH::GH-ANALYSIS", "08_GH::GH-ARCHIVE",
    "09_DOC::D-MAKE2D", "09_DOC::D-DIM", "09_DOC::D-TEXT", "09_DOC::D-HATCH", "09_DOC::D-SECTION",
    "09_DOC::D-TITLE",
    "10_PRES::P-PEOPLE", "10_PRES::P-VEHICLE", "10_PRES::P-LIGHT", "10_PRES::P-CAMERA",
    "99_WIP::WIP", "99_WIP::TRASH",
]


def _layer_items(default):
    items = [(name.split("::")[-1] + "  (" + name.split("::")[0] + ")", name) for name in LAYERS]
    return items, LAYERS.index(default)


# --- controls created by the setup -------------------------------------------------
# (input, "list", [(label, value), ...], default index)
# (input, "slider", (min, max, default))
# (input, "point" | "curve", hint)      empty parameter: right-click > Set one ...
# (input, "button", label)
_BAKE_ITEMS, _BAKE_DEFAULT = _layer_items("03_ARCH::A-STAIR")
CONTROLS = [
    ("stair_type", "list", [("Straight", "straight"), ("L-shaped", "L"),
                            ("U-shaped", "U"), ("Spiral", "spiral")], 0),
    ("turn", "list", [("Turn left", "left"), ("Turn right", "right")], 0),
    ("start", "point", "start point (right-click > Set one Point)"),
    ("rotation", "slider", (0, 360, 0)),        # degrees, 0 = +X, counter-clockwise
    ("path", "curve", "path (right-click > Set one Curve)"),
    ("location", "list", [("Path = centre line", "center"), ("Path = left edge", "left"),
                          ("Path = right edge", "right")], 0),
    ("boundary", "curve", "boundary (right-click > Set one Curve)"),
    ("opening", "curve", "floor opening (right-click > Set one Curve)"),
    ("slab_thk", "slider", (0, 600, 250)),      # upper floor thickness, for headroom
    ("floor_height", "slider", (2000, 5000, 2800)),
    ("width", "slider", (600, 2000, 900)),
    ("riser_count", "slider", (0, 30, 0)),      # 0 = auto
    ("tread_depth", "slider", (0, 400, 0)),     # 0 = auto (not used for spiral or a path)
    ("flight1_risers", "slider", (0, 30, 0)),   # L/U, 0 = half
    ("landing_depth", "slider", (0, 2000, 0)),  # L/U, 0 = width
    ("well_gap", "slider", (0, 1000, 100)),     # U: gap between the flights
    ("spiral_radius", "slider", (600, 2500, 1000)),
    ("turn_angle", "slider", (90, 720, 360)),
    ("stringer_on", "list", [("With stringers", "yes"), ("No stringers", "no")], 0),
    ("stringer_thk", "slider", (0, 100, 40)),
    ("tread_thk", "slider", (0, 100, 40)),
    ("riser_thk", "slider", (0, 50, 20)),       # 0 = open risers
    ("nosing", "slider", (0, 50, 0)),
    ("bake_layer", "list", _BAKE_ITEMS, _BAKE_DEFAULT),
    ("text_layer", "list", [("Same as bake layer", "same"), ("No annotation", "")] + _BAKE_ITEMS, 0),
    ("bake", "button", "Bake stair"),
]
# shown as a label to the left of each control
DESCRIPTIONS = {
    "stair_type": "Stair type (ignored when a path is set)",
    "turn": "L / U / spiral: turn direction going up",
    "start": "Start point: bottom of the stair\n(spiral: centre of the column)",
    "rotation": "Direction of the first flight,\ndegrees from +X (counter-clockwise)",
    "path": "Draw the walk line in Rhino and set it here:\nline / L / U polyline / arc. Overrides\nstart, rotation, type and turn",
    "location": "Which line of the stair the path is",
    "boundary": "Closed curve the stair must stay inside\n(warning + fits_boundary output)",
    "opening": "Floor opening above (closed curve):\nturns on the headroom check",
    "slab_thk": "Upper floor slab thickness (mm):\nceiling = floor height - slab",
    "floor_height": "Floor-to-floor height (mm)",
    "width": "Clear width between stringers (mm)",
    "riser_count": "Number of risers (0 = auto)",
    "tread_depth": "Tread depth / run (0 = auto)",
    "flight1_risers": "L / U: risers before the landing (0 = half)",
    "landing_depth": "L / U: landing depth (0 = stair width)",
    "well_gap": "U: gap between the two flights (mm)\n(a U path sets it from the drawing)",
    "spiral_radius": "Spiral: outer radius (mm)",
    "turn_angle": "Spiral: degrees from first to last riser",
    "stringer_on": "Stringers on / off",
    "stringer_thk": "Stringer thickness (mm)",
    "tread_thk": "Tread thickness (mm)",
    "riser_thk": "Riser board thickness (0 = open risers)",
    "nosing": "Tread overhang past the riser (mm)",
    "bake_layer": "Bake: layer for the stair",
    "text_layer": "Bake: layer for numbers, arrows, UP label",
    "bake": "Press to bake the stair into Rhino",
}
VERSION = 9  # bump when CONTROLS change: refreshes drop-downs, labels and groups once
# the controls are laid out in these groups, top to bottom: (title, inputs, ARGB colour)
SECTIONS = [
    ("1. General", ["stair_type", "turn", "start", "rotation", "path", "location", "boundary",
                    "opening", "slab_thk", "floor_height", "width", "riser_count", "tread_depth",
                    "stringer_on", "stringer_thk", "tread_thk", "riser_thk", "nosing",
                    "bake_layer", "text_layer", "bake"], (60, 120, 160, 220)),
    ("2. L-shaped and U-shaped", ["flight1_risers", "landing_depth", "well_gap"], (60, 230, 160, 60)),
    ("3. Spiral", ["spiral_radius", "turn_angle"], (60, 150, 90, 220)),
]
FREE_INPUTS = ["rules"]  # no control; connect your own
OUTPUTS = ["solids", "treads", "risers", "stringers", "landings", "report", "status",
           "n_risers", "riser_h", "tread_d", "flights", "headroom", "fits_boundary",
           "numbers_pt", "numbers_txt", "arrows", "up_pt", "up_txt"]
OPTION_INPUTS = ("tread_thk", "riser_thk", "nosing", "stringer_thk", "well_gap", "slab_thk")
AUTO_WHEN_ZERO = ("riser_count", "tread_depth", "flight1_risers", "landing_depth")
EXPECTED_INPUTS = [c[0] for c in CONTROLS] + FREE_INPUTS


def _rename(param, name):
    param.Name = name
    param.NickName = name
    if hasattr(param, "VariableName"):
        try:
            param.VariableName = name
        except Exception:
            pass


def _setup(doc):
    """Add inputs/outputs to this component, then the controls, and wire them."""
    import System
    import System.Drawing as sd
    import Grasshopper as gh
    from Grasshopper.Kernel import GH_ParameterSide
    from Grasshopper.Kernel.Parameters import Param_Curve, Param_Point
    from Grasshopper.Kernel.Special import (GH_ButtonObject, GH_NumberSlider, GH_Panel,
                                            GH_ValueList, GH_ValueListItem, GH_ValueListMode)

    comp = ghenv.Component
    # keep what is wired to inputs/outputs that still exist (your controls and their layout);
    # REBUILD removes the controls and panels instead
    kept_in = {p.NickName: list(p.Sources) for p in comp.Params.Input}
    kept_out = {p.NickName: list(p.Recipients) for p in comp.Params.Output}
    if REBUILD:
        kinds = (GH_NumberSlider, GH_ValueList, GH_ButtonObject, Param_Point, Param_Curve)
        for o in [s for v in kept_in.values() for s in v if isinstance(s, kinds)]:
            doc.RemoveObject(o, False)
        for o in [r for v in kept_out.values() for r in v if isinstance(r, GH_Panel)]:
            doc.RemoveObject(o, False)
        kept_in, kept_out = {}, {}
    for p in list(comp.Params.Input):
        comp.Params.UnregisterInputParameter(p, True)
    for p in list(comp.Params.Output):
        if p.NickName != "out":
            comp.Params.UnregisterOutputParameter(p, True)

    for i, name in enumerate(EXPECTED_INPUTS):
        p = comp.CreateParameter(GH_ParameterSide.Input, i)
        _rename(p, name)
        p.Optional = True
        comp.Params.RegisterInputParam(p, i)
    first = comp.Params.Output.Count
    for j, name in enumerate(OUTPUTS):
        p = comp.CreateParameter(GH_ParameterSide.Output, first + j)
        _rename(p, name)
        comp.Params.RegisterOutputParam(p, first + j)
    comp.VariableParameterMaintenance()
    comp.Params.OnParametersChanged()
    comp.NickName = "Stair Generator"
    comp.Attributes.ExpireLayout()
    comp.Attributes.PerformLayout()

    for p in comp.Params.Input:
        for src in kept_in.get(p.NickName, []):
            p.AddSource(src)
    for p in comp.Params.Output:
        for rec in kept_out.get(p.NickName, []):
            rec.AddSource(p)

    # new controls in a column to the left of the component (or of your existing controls)
    box = comp.Attributes.Bounds
    kept_left = [s.Attributes.Bounds.Left for v in kept_in.values() for s in v]
    column = (min(kept_left) - 320) if kept_left else (box.Left - 420)
    row = 0
    for i, control in enumerate(CONTROLS):
        name, kind = control[0], control[1]
        target = comp.Params.Input[i]
        if kept_in.get(name):
            continue
        if kind == "list":
            obj = GH_ValueList()
            obj.CreateAttributes()
            obj.ListMode = GH_ValueListMode.DropDown
            obj.ListItems.Clear()
            for label, value in control[2]:
                obj.ListItems.Add(GH_ValueListItem(label, '"{}"'.format(value)))
            obj.SelectItem(control[3])
            obj.NickName = name
            width = 200
        elif kind == "slider":
            lo, hi, val = control[2]
            obj = GH_NumberSlider()
            obj.CreateAttributes()
            obj.Slider.Type = gh.GUI.Base.GH_SliderAccuracy.Integer
            obj.Slider.Minimum = System.Decimal(lo)
            obj.Slider.Maximum = System.Decimal(hi)
            obj.SetSliderValue(System.Decimal(val))
            obj.NickName = name
            width = 260
        elif kind == "button":
            obj = GH_ButtonObject()
            obj.CreateAttributes()
            obj.NickName = control[2]
            width = 120
        else:
            obj = Param_Point() if kind == "point" else Param_Curve()
            obj.CreateAttributes()
            obj.NickName = control[2]
            width = 60
        obj.Attributes.Pivot = sd.PointF(column + (260 - width), box.Top - 60 + row * 34)
        row += 1
        doc.AddObject(obj, False)
        obj.Attributes.ExpireLayout()
        target.AddSource(obj)

    # report panel to the right
    rep = comp.Params.Output[first + OUTPUTS.index("report")]
    if kept_out.get("report"):
        comp.ExpireSolution(False)
        return
    panel = GH_Panel()
    panel.CreateAttributes()
    panel.NickName = "Stair report"
    grip = rep.Attributes.OutputGrip
    panel.Attributes.Bounds = sd.RectangleF(grip.X + 80, grip.Y - 200, 520, 600)
    panel.Attributes.Pivot = sd.PointF(grip.X + 80, grip.Y - 200)
    doc.AddObject(panel, False)
    panel.AddSource(rep)

    comp.ExpireSolution(False)


def _tidy(doc, names):
    """Move the controls of ``names`` into a column left of the other controls."""
    import System.Drawing as sd
    comp = ghenv.Component
    moving = [(p.NickName, s) for p in comp.Params.Input if p.NickName in names for s in p.Sources]
    others = [s.Attributes.Bounds.Left for p in comp.Params.Input if p.NickName not in names
              for s in p.Sources]
    column = (min(others) if others else comp.Attributes.Bounds.Left) - 320
    top = comp.Attributes.Bounds.Top - 60
    for row, (_, s) in enumerate(moving):
        s.Attributes.Pivot = sd.PointF(column + 260 - s.Attributes.Bounds.Width, top + row * 34)
        s.Attributes.ExpireLayout()
    ghenv.Component.ExpireSolution(False)


LABEL_TAG = "stairgen-label"


def _refresh(doc):
    """Bring existing drop-downs up to date, then lay the controls out in their groups."""
    from Grasshopper.Kernel.Special import GH_ValueList, GH_ValueListItem
    comp = ghenv.Component
    controls = {c[0]: c for c in CONTROLS}

    for p in comp.Params.Input:
        c = controls.get(p.NickName)
        if c is None or c[1] != "list":
            continue
        for vl in [s for s in p.Sources if isinstance(s, GH_ValueList)]:
            old = [i.Expression for i in vl.ListItems]
            chosen = [i.Expression for i in vl.SelectedItems]
            new = ['"{}"'.format(v) for _, v in c[2]]
            if old == new:
                continue
            vl.ListItems.Clear()
            for label, value in c[2]:
                vl.ListItems.Add(GH_ValueListItem(label, '"{}"'.format(value)))
            # keep the choice only if the old list already offered the new default
            keep = chosen and chosen[0] in new and new[c[3]] in old
            vl.SelectItem(new.index(chosen[0]) if keep else c[3])
            vl.ExpireSolution(False)
    _arrange(doc)


def _place(obj, left, top):
    """Move ``obj`` so its box starts at (left, top); the pivot is not the corner for every type."""
    import System.Drawing as sd
    a = obj.Attributes
    a.ExpireLayout()
    a.PerformLayout()
    b, p = a.Bounds, a.Pivot
    a.Pivot = sd.PointF(p.X + left - b.Left, p.Y + top - b.Top)
    a.ExpireLayout()
    a.PerformLayout()


def _arrange(doc):
    """One column left of the component: a coloured group per SECTION, a label per control."""
    import System.Drawing as sd
    from Grasshopper.Kernel.Special import GH_Group, GH_Relay, GH_Scribble
    comp = ghenv.Component
    # a wire relay (double-click on a wire) between a control and the component is removed
    for p in comp.Params.Input:
        for relay in [s for s in p.Sources if isinstance(s, GH_Relay)]:
            upstream = list(relay.Sources)
            p.RemoveSource(relay)
            for u in upstream:
                p.AddSource(u)
            doc.RemoveObject(relay, False)
    sources = {p.NickName: list(p.Sources) for p in comp.Params.Input}
    ours = set(str(s.InstanceGuid) for v in sources.values() for s in v)

    # old labels, and groups that hold any of these controls, are replaced
    for o in list(doc.Objects):
        if isinstance(o, GH_Scribble) and o.NickName == LABEL_TAG:
            doc.RemoveObject(o, False)
        elif isinstance(o, GH_Group) and any(str(g) in ours for g in o.ObjectIDs):
            doc.RemoveObject(o, False)

    box = comp.Attributes.Bounds
    x_label = box.Left - 820
    x_ctrl = x_label + 340
    y = box.Top - 300
    for title, names, argb in SECTIONS:
        y += 40                                   # room for the group title
        members = []
        for name in names:
            text = DESCRIPTIONS.get(name, name)
            height = max(56, 18 * (text.count("\n") + 1) + 26)
            for src in sources.get(name, []):
                _place(src, x_ctrl, y)
                label = GH_Scribble()
                label.CreateAttributes()
                label.NickName = LABEL_TAG
                label.Text = text
                label.Font = sd.Font("Arial", 11)
                label.Attributes.Pivot = sd.PointF(x_label, y)
                doc.AddObject(label, False)
                members += [src, label]
                y += height
        group = GH_Group()
        group.CreateAttributes()
        group.NickName = title
        group.Colour = sd.Color.FromArgb(*argb)
        for m in members:
            group.AddObject(m.InstanceGuid)
        doc.AddObject(group, False)
        y += 50
    comp.ExpireSolution(False)


def _get(name):
    v = globals().get(name)
    if name in AUTO_WHEN_ZERO and v is not None and float(v) <= 0:
        return None
    return v


import math
import scriptcontext as _sc

_inputs = [p.NickName for p in ghenv.Component.Params.Input]
_key = "stairgen_built_{}_{}".format(ghenv.Component.InstanceGuid, len(EXPECTED_INPUTS))
if (_inputs != EXPECTED_INPUTS or REBUILD) and not _sc.sticky.get(_key):
    # set the component up once the current solution has finished
    _sc.sticky[_key] = True
    import Grasshopper as _gh
    _doc = ghenv.Component.OnPingDocument()
    _doc.ScheduleSolution(10, _gh.Kernel.GH_Document.GH_ScheduleDelegate(_setup))
    print("Setting up the Stair Generator component...")
elif not _sc.sticky.get("stairgen_refresh_{}_{}".format(ghenv.Component.InstanceGuid, VERSION)):
    _sc.sticky["stairgen_refresh_{}_{}".format(ghenv.Component.InstanceGuid, VERSION)] = True
    import Grasshopper as _gh
    ghenv.Component.OnPingDocument().ScheduleSolution(
        10, _gh.Kernel.GH_Document.GH_ScheduleDelegate(_refresh))
else:
    _options = ["{} = {}".format(k, globals()[k]) for k in OPTION_INPUTS
                if globals().get(k) is not None]
    if str(globals().get("stringer_on") or "yes").lower() == "no":
        _options.append("stringer_thk = 0")
    _rot = math.radians(float(globals().get("rotation") or 0.0))
    _r = _sg.run_design(
        ghenv, rules=_get("rules"), stair_type=_get("stair_type"),
        floor_height=_get("floor_height"), start=_get("start"),
        direction=(math.cos(_rot), math.sin(_rot)), width=_get("width"),
        landing_depth=_get("landing_depth"), spiral_radius=_get("spiral_radius"),
        turn_angle=_get("turn_angle"), turn=_get("turn"), riser_count=_get("riser_count"),
        tread_depth=_get("tread_depth"), flight1_risers=_get("flight1_risers"),
        opening=_get("opening"), options=_options, path=_get("path"), location=_get("location"))
    _stair = _r["stair"]
    _geo = _sg.run_geometry(_stair)
    _ann = _sg.run_annotation(_stair, False)
    _msgs = _r["messages"] + _geo["messages"] + _ann["messages"]

    fits_boundary, _bmsg = _sg.boundary_check(_stair, _sg._to_curve(_get("boundary")))
    if _bmsg:
        _msgs.append(("remark" if fits_boundary else "warning", _bmsg))
        _r["report"] += "\n\nBoundary: " + _bmsg

    if globals().get("bake") and _stair is not None:
        _layer = _get("bake_layer") or "03_ARCH::A-STAIR"
        _text = _get("text_layer")
        _text = _layer if _text in (None, "same") else (_text or None)
        _msgs.append(("remark", _sg.bake(
            _stair, _geo["solids"], _layer, _text, _ann["numbers_pt"], _ann["numbers_txt"],
            _ann["arrows"], _ann["up_pt"], _ann["up_txt"])))

    _sg.post_messages(ghenv, _msgs)
    ghenv.Component.Message = _r["status"]

    solids = _geo["solids"]
    treads = _geo["treads"]
    risers = _geo["risers"]
    stringers = _geo["stringers"]
    landings = _geo["landings"]
    report = _r["report"]
    status = _r["status"]
    n_risers = _r["n_risers"]
    riser_h = _r["riser_h"]
    tread_d = _r["tread_d"]
    flights = _r["flights"]
    headroom = _r["headroom"]
    numbers_pt = _ann["numbers_pt"]
    numbers_txt = _ann["numbers_txt"]
    arrows = _ann["arrows"]
    up_pt = _ann["up_pt"]
    up_txt = _ann["up_txt"]
