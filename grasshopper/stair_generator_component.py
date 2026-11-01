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
A relative path is read from the folder of this .gh file.

Units: slider values and the report are always in millimetres. The stair library
works in millimetres; this component converts the points/curves you give it from the
model units of the open Rhino document to mm, and converts the geometry it outputs
and bakes back to model units. In a millimetre document nothing is converted.
0 on riser_count, tread_depth, flight1_risers or landing_depth means "auto".

Library location (the folder that holds the 'stairgen' and 'stairgen_rhino'
folders) is found in this order:
  1. STAIRGEN_PATH below, if not empty (absolute, or relative to this .gh file);
  2. the STAIRGEN_PATH environment variable;
  3. a search from the folder of this .gh file (and of the Rhino file): the folder
     itself, up to 2 parent folders, and sub-folders named like "*stair*" (2 levels).
So keeping the library next to the .gh file (e.g. in a "stair-generator" folder)
works on any computer and any drive letter without editing anything.

Bake: press the Bake button. Everything goes to `bake_layer` as one group.
Layers are typed as full paths, like Elefont: Parent::Child::Grandchild
(e.g. 03_ARCH::A-STAIR). Empty = the office default in DEFAULT_BAKE_LAYER.
`text_layer` is where the step numbers, arrows and UP label go:
  empty or "same" = the bake layer, "none" = no annotation, or a layer path.
Missing layers are created.

DESIGN AID ONLY - NOT A CODE COMPLIANCE CERTIFICATION.
"""

# Folder that contains the 'stairgen' and 'stairgen_rhino' folders. Leave empty to
# find it automatically (see the notes above). A relative path is read from the .gh folder.
STAIRGEN_PATH = ""
# True = rebuild the controls once (replaces the controls, resets their values). Set back to False.
REBUILD = False
# True = re-import the library on every solution so library edits show up at once
# (slower). Set to False when you are not editing the library.
RELOAD_LIBRARY = True

import importlib
import os
import sys

LIBRARY_PACKAGES = ("stairgen", "stairgen_rhino")
ENV_VAR = "STAIRGEN_PATH"


def _is_library(folder):
    """True if ``folder`` holds both library packages."""
    return bool(folder) and all(os.path.isfile(os.path.join(folder, pkg, "__init__.py"))
                                for pkg in LIBRARY_PACKAGES)


def _search_roots(gh_file, rhino_file):
    """Folders to search from: the .gh folder and the Rhino file folder, then parents."""
    roots = []
    for f in (gh_file, rhino_file):
        if not f:
            continue
        folder = os.path.dirname(os.path.abspath(f))
        for _ in range(3):  # the folder itself + 2 parents
            if folder not in roots:
                roots.append(folder)
            parent = os.path.dirname(folder)
            if parent == folder:
                break
            folder = parent
    return roots


def find_library(configured, gh_file, rhino_file, environ=None):
    """Return (folder or None, [places looked]) for the stairgen library."""
    environ = os.environ if environ is None else environ
    gh_dir = os.path.dirname(os.path.abspath(gh_file)) if gh_file else None
    looked = []

    def resolve(path, label):
        path = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))
        if not os.path.isabs(path):
            if gh_dir is None:
                looked.append("{}: '{}' is relative but the .gh file is not saved".format(label, path))
                return None
            path = os.path.join(gh_dir, path)
        path = os.path.normpath(path)
        looked.append("{}: {}".format(label, path))
        return path if _is_library(path) else None

    if configured and configured.strip():
        return resolve(configured, "STAIRGEN_PATH in script"), looked
    if environ.get(ENV_VAR, "").strip():
        return resolve(environ[ENV_VAR], ENV_VAR + " environment variable"), looked
    for root in _search_roots(gh_file, rhino_file):
        looked.append("search: " + root)
        candidates = [root]
        try:
            level1 = [os.path.join(root, n) for n in sorted(os.listdir(root))
                      if "stair" in n.lower() and os.path.isdir(os.path.join(root, n))]
        except OSError:
            level1 = []
        for sub in level1:
            candidates.append(sub)
            try:
                candidates += [os.path.join(sub, n) for n in sorted(os.listdir(sub))
                               if "stair" in n.lower() and os.path.isdir(os.path.join(sub, n))]
            except OSError:
                pass
        for c in candidates:
            if _is_library(c):
                return os.path.normpath(c), looked
    if not gh_file:
        looked.append("(the .gh file is not saved yet, so its folder could not be searched)")
    return None, looked


def _gh_file_path():
    try:
        doc = ghenv.Component.OnPingDocument()
        return doc.FilePath if doc is not None and doc.IsFilePathDefined else None
    except Exception:
        return None


def _rhino_doc():
    """The Rhino document Grasshopper is working on, or None when none is open."""
    try:
        import Rhino
        return Rhino.RhinoDoc.ActiveDoc
    except Exception:
        return None


def _error(msg):
    from Grasshopper.Kernel import GH_RuntimeMessageLevel
    ghenv.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, msg)
    ghenv.Component.Message = "error"


def _import_library():
    """Put the library on sys.path and import it. Returns (module or None, error text)."""
    rdoc = _rhino_doc()
    folder, looked = find_library(STAIRGEN_PATH, _gh_file_path(),
                                  getattr(rdoc, "Path", None) if rdoc is not None else None)
    if folder is None:
        return None, ("Stair library not found (folder with 'stairgen' and 'stairgen_rhino').\n"
                      "Put it next to this .gh file, or set STAIRGEN_PATH in the script or the "
                      "STAIRGEN_PATH environment variable.\nLooked in:\n  " + "\n  ".join(looked))
    importlib.invalidate_caches()  # see library files added while Rhino is open
    # drop other copies of the library (another computer's / drive's path) from sys.path
    sys.path[:] = [p for p in sys.path if not (p != folder and _is_library(p))]
    if folder not in sys.path:
        sys.path.insert(0, folder)
    loaded = sys.modules.get("stairgen_rhino")
    stale = loaded is not None and not os.path.abspath(
        getattr(loaded, "__file__", "") or "").startswith(os.path.abspath(folder))
    if RELOAD_LIBRARY or stale:
        for name in list(sys.modules):  # re-import so edits to the library show up
            if name.split(".")[0] in LIBRARY_PACKAGES:
                del sys.modules[name]
    try:
        from stairgen_rhino import gh as module
    except Exception as e:  # syntax error etc. in the library
        return None, "Could not import the stair library from {}:\n{}: {}".format(
            folder, type(e).__name__, e)
    return module, None

# --- bake layers: typed as full paths, like Elefont (Parent::Child) ---------------
# Office layer standard defaults; used when the layer input is empty.
DEFAULT_BAKE_LAYER = "03_ARCH::A-STAIR"
DEFAULT_TEXT_LAYER = "same"  # "same" = bake layer, "none" = no annotation, or a path
LAYER_SEPARATOR = "::"


# --- controls created by the setup -------------------------------------------------
# (input, "list", [(label, value), ...], default index)
# (input, "slider", (min, max, default))
# (input, "point" | "curve", hint)      empty parameter: right-click > Set one ...
# (input, "button", label)
# (input, "text", default text)       a panel you type in (layer paths)
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
    ("bake_layer", "text", DEFAULT_BAKE_LAYER),
    ("text_layer", "text", DEFAULT_TEXT_LAYER),
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
    "bake_layer": "Bake: layer path for the stair,\ne.g. 03_ARCH::A-STAIR (empty = default)",
    "text_layer": "Bake: layer path for numbers, arrows, UP\n(same = bake layer, none = no text)",
    "bake": "Press to bake the stair into Rhino",
}
VERSION = 10  # bump when CONTROLS change: refreshes drop-downs, labels and groups once
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
        kinds = (GH_NumberSlider, GH_ValueList, GH_ButtonObject, GH_Panel, Param_Point,
                 Param_Curve)
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
        elif kind == "text":
            obj = _text_panel(control[2])
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


def _text_panel(text):
    """A one-line panel to type a value in (used for layer paths)."""
    import System.Drawing as sd
    from Grasshopper.Kernel.Special import GH_Panel
    panel = GH_Panel()
    panel.CreateAttributes()
    panel.NickName = ""
    panel.UserText = text
    panel.Properties.Multiline = False
    panel.Attributes.Bounds = sd.RectangleF(0, 0, 260, 22)
    return panel


def list_choice_to_text(name, expression):
    """Value of an old layer drop-down item, as the text for the new layer panel."""
    value = (expression or "").strip().strip('"')
    if name == "text_layer" and value == "":
        return "none"  # the old "No annotation" item
    return value


def _refresh(doc):
    """Bring existing drop-downs up to date, then lay the controls out in their groups."""
    from Grasshopper.Kernel.Special import GH_ValueList, GH_ValueListItem
    comp = ghenv.Component
    controls = {c[0]: c for c in CONTROLS}

    for p in comp.Params.Input:
        c = controls.get(p.NickName)
        if c is not None and c[1] == "text":
            # an old drop-down (v9 layer lists) becomes a panel holding the chosen value
            for vl in [s for s in p.Sources if isinstance(s, GH_ValueList)]:
                chosen = [i.Expression for i in vl.SelectedItems]
                panel = _text_panel(list_choice_to_text(c[0], chosen[0]) if chosen else c[2])
                panel.Attributes.Pivot = vl.Attributes.Pivot
                doc.AddObject(panel, False)
                p.RemoveSource(vl)
                p.AddSource(panel)
                doc.RemoveObject(vl, False)
            continue
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


# --- input checks ------------------------------------------------------------------
_CONTROL_BY_NAME = {c[0]: c for c in CONTROLS}
CHOICE_INPUTS = ("stair_type", "turn", "location", "stringer_on")  # fixed lists of values


class InputError(Exception):
    """A bad input value; shown as a red component message, not a traceback."""


def normalise_choice(name, value):
    """Return the canonical value for a drop-down input (case-insensitive), or raise."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    allowed = [v for _, v in _CONTROL_BY_NAME[name][2]]
    text = str(value).strip().strip('"').strip()
    for a in allowed:
        if text.lower() == a.lower():
            return a
    raise InputError("{} = '{}' is not valid. Use one of: {}.".format(
        name, text, ", ".join(allowed)))


def _get(name):
    v = globals().get(name)
    if name in CHOICE_INPUTS:
        return normalise_choice(name, v)
    if name in AUTO_WHEN_ZERO and v is not None:
        try:
            if float(v) <= 0:
                return None
        except (TypeError, ValueError):
            raise InputError("{} = '{}' is not a number.".format(name, v))
    return v


# --- Rhino document: units and tolerance -------------------------------------------
def units_context(rdoc):
    """(model-units-to-mm factor, absolute tolerance in mm, angle tolerance deg, unit name)."""
    import Rhino
    factor = Rhino.RhinoMath.UnitScale(rdoc.ModelUnitSystem, Rhino.UnitSystem.Millimeters)
    return (factor, rdoc.ModelAbsoluteTolerance * factor, rdoc.ModelAngleToleranceDegrees,
            str(rdoc.ModelUnitSystem).split(".")[-1])


def scaled(value, factor):
    """Copy of point/curve/brep (or a list of them) scaled about the origin; other values as is."""
    if value is None or abs(factor - 1.0) < 1e-12:
        return value
    if isinstance(value, (str, bytes, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [scaled(v, factor) for v in value]
    import Rhino.Geometry as rg
    if isinstance(value, rg.Point3d):
        return rg.Point3d(value.X * factor, value.Y * factor, value.Z * factor)
    if hasattr(value, "Duplicate") and hasattr(value, "Transform"):
        dup = value.Duplicate()
        dup.Transform(rg.Transform.Scale(rg.Point3d.Origin, factor))
        return dup
    if hasattr(value, "__iter__"):  # .NET List / array of geometry
        return [scaled(v, factor) for v in value]
    return value


def _curve_in_mm(sg, value, factor):
    """Curve input converted to a curve in mm (unchanged in a mm document)."""
    if value is None or abs(factor - 1.0) < 1e-12:
        return value
    curve = sg._to_curve(value)
    if curve is None:
        raise InputError("Could not read the curve input ({}).".format(type(value).__name__))
    return scaled(curve, factor)


def layer_path(name, value, default):
    """Clean a typed layer path (Parent::Child), or raise. Empty = ``default``."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    text = "" if value is None else str(value).strip().strip('"').strip()
    if not text:
        return default
    parts = [part.strip() for part in text.split(LAYER_SEPARATOR)]
    if any(not part for part in parts):
        raise InputError("{} = '{}' is not a valid layer path. Use Parent::Child, "
                         "e.g. {}.".format(name, text, DEFAULT_BAKE_LAYER))
    try:
        from Rhino.DocObjects import Layer
        bad = [part for part in parts if not Layer.IsValidName(part)]
    except Exception:  # outside Rhino
        bad = [part for part in parts if any(ch in part for ch in '{}[]()"')]
    if bad:
        raise InputError("{}: '{}' is not a valid Rhino layer name.".format(name, bad[0]))
    return LAYER_SEPARATOR.join(parts)


def bake_layers(bake_value, text_value):
    """(bake layer path, annotation layer path or None for no annotation)."""
    layer = layer_path("bake_layer", bake_value, DEFAULT_BAKE_LAYER)
    raw = "" if text_value is None else str(text_value).strip().strip('"').strip()
    keyword = (raw or DEFAULT_TEXT_LAYER).lower()
    if keyword == "same":
        return layer, layer
    if keyword == "none":
        return layer, None
    return layer, layer_path("text_layer", raw or DEFAULT_TEXT_LAYER, layer)


def resolve_rules(rules, gh_file):
    """A relative rule-file path is read from the folder of the .gh file."""
    if not rules or not isinstance(rules, str):
        return rules
    path = os.path.expandvars(os.path.expanduser(rules.strip().strip('"')))
    if os.path.isabs(path):
        return path
    if not gh_file:
        raise InputError("rules = '{}' is a relative path: save the .gh file first, "
                         "or use a full path.".format(rules))
    return os.path.normpath(os.path.join(os.path.dirname(gh_file), path))


def _run():
    """Solve, set the outputs (as globals) and post messages."""
    global solids, treads, risers, stringers, landings, report, status, n_risers, riser_h
    global tread_d, flights, headroom, fits_boundary, numbers_pt, numbers_txt, arrows
    global up_pt, up_txt

    rdoc = _rhino_doc()
    if rdoc is None:
        raise InputError("No Rhino document is open. Open or create a Rhino file "
                         "(the stair uses its units and tolerance).")
    to_mm, tol_mm, angle_tol, unit_name = units_context(rdoc)
    to_model = 1.0 / to_mm

    sg, err = _import_library()
    if sg is None:
        raise InputError(err)
    # checked on every solution, so a mistyped layer shows before you press Bake
    layer, text = bake_layers(globals().get("bake_layer"), globals().get("text_layer"))

    options = ["{} = {}".format(k, globals()[k]) for k in OPTION_INPUTS
               if globals().get(k) is not None]
    if (_get("stringer_on") or "yes") == "no":
        options.append("stringer_thk = 0")
    rot = math.radians(float(globals().get("rotation") or 0.0))
    start_in = _get("start")
    r = sg.run_design(
        ghenv, rules=resolve_rules(_get("rules"), _gh_file_path()),
        stair_type=_get("stair_type"), floor_height=_get("floor_height"),
        start=scaled(start_in, to_mm), direction=(math.cos(rot), math.sin(rot)),
        width=_get("width"), landing_depth=_get("landing_depth"),
        spiral_radius=_get("spiral_radius"), turn_angle=_get("turn_angle"), turn=_get("turn"),
        riser_count=_get("riser_count"), tread_depth=_get("tread_depth"),
        flight1_risers=_get("flight1_risers"),
        opening=_curve_in_mm(sg, _get("opening"), to_mm), options=options,
        path=_curve_in_mm(sg, _get("path"), to_mm), location=_get("location"))
    stair = r["stair"]
    geo = sg.run_geometry(stair)
    ann = sg.run_annotation(stair, False)
    msgs = r["messages"] + geo["messages"] + ann["messages"]

    fits, bmsg = sg.boundary_check(stair, scaled(sg._to_curve(_get("boundary")), to_mm))
    if bmsg:
        msgs.append(("remark" if fits else "warning", bmsg))
        r["report"] += "\n\nBoundary: " + bmsg

    units_line = ("Rhino units: {} (tolerance {:g} mm, angle {:g} deg). Values in this "
                  "report are in mm.").format(unit_name, tol_mm, angle_tol)
    if abs(to_mm - 1.0) > 1e-12:
        units_line += " Geometry is converted to {}.".format(unit_name.lower())
    r["report"] = (r["report"] or "") + "\n\n" + units_line
    if tol_mm > 1.0:
        msgs.append(("warning", "The document tolerance is {:g} mm: coarser than 1 mm, so solids "
                                "and the boundary check may be inaccurate.".format(tol_mm)))

    # geometry back to model units (copies; the library's own objects stay in mm)
    out = {k: scaled(geo[k], to_model) for k in ("solids", "treads", "risers", "stringers",
                                                  "landings")}
    out.update({k: scaled(ann[k], to_model) for k in ("numbers_pt", "arrows", "up_pt")})

    if globals().get("bake"):
        if stair is None:
            msgs.append(("warning", "Nothing to bake: the stair could not be designed."))
        else:
            msgs.append(("remark", sg.bake(
                stair, out["solids"], layer, text, out["numbers_pt"], ann["numbers_txt"],
                out["arrows"], out["up_pt"], ann["up_txt"])))

    sg.post_messages(ghenv, msgs)
    ghenv.Component.Message = r["status"]

    solids, treads, risers = out["solids"], out["treads"], out["risers"]
    stringers, landings = out["stringers"], out["landings"]
    report, status = r["report"], r["status"]
    n_risers, riser_h, tread_d = r["n_risers"], r["riser_h"], r["tread_d"]  # mm
    flights, headroom, fits_boundary = r["flights"], r["headroom"], fits
    numbers_pt, numbers_txt, arrows = out["numbers_pt"], ann["numbers_txt"], out["arrows"]
    up_pt, up_txt = out["up_pt"], ann["up_txt"]


import math
import scriptcontext as _sc

_guid = ghenv.Component.InstanceGuid
_inputs = [p.NickName for p in ghenv.Component.Params.Input]
_key = "stairgen_built_{}_{}".format(_guid, len(EXPECTED_INPUTS))
_rebuild_key = "stairgen_rebuilt_{}".format(_guid)
if REBUILD:
    # once per switch to True (the old check never rebuilt after the first setup)
    _do_setup = not _sc.sticky.get(_rebuild_key)
    _sc.sticky[_rebuild_key] = True
else:
    _sc.sticky.pop(_rebuild_key, None)
    _do_setup = _inputs != EXPECTED_INPUTS and not _sc.sticky.get(_key)

if _do_setup:
    # set the component up once the current solution has finished
    _sc.sticky[_key] = True
    import Grasshopper as _gh
    _doc = ghenv.Component.OnPingDocument()
    _doc.ScheduleSolution(10, _gh.Kernel.GH_Document.GH_ScheduleDelegate(_setup))
    print("Setting up the Stair Generator component...")
elif not _sc.sticky.get("stairgen_refresh_{}_{}".format(_guid, VERSION)):
    _sc.sticky["stairgen_refresh_{}_{}".format(_guid, VERSION)] = True
    import Grasshopper as _gh
    ghenv.Component.OnPingDocument().ScheduleSolution(
        10, _gh.Kernel.GH_Document.GH_ScheduleDelegate(_refresh))
else:
    try:
        _run()
    except InputError as _e:
        _error(str(_e))
    except Exception as _e:  # library bug: short message on the component, details in 'out'
        import traceback
        traceback.print_exc()
        _error("Stair generator failed: {}: {}\n(see the 'out' output for details)".format(
            type(_e).__name__, _e))
