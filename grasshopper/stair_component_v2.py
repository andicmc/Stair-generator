"""STAIR GENERATOR v2 - Grasshopper Python 3 Script component (Rhino 8).

Thin component: all design logic is in core/stairs (pure Python, tested); Rhino geometry
is made by adapters/stairs_rhino. Paste this script into a Python 3 Script component and
add the inputs / outputs listed below (right-click the component > zoom in > "+").

INPUTS (all optional; names must match; units = mm regardless of the document units)
  base_pt        Point   base point: centre of the bottom of the first riser (default origin)
  rotation       Number  direction of the first flight, degrees from +X (counter-clockwise)
  stair_type     Text    straight | L | U | U2 | spiral
  turn           Text    left | right
  floor_to_floor Number  mm
  width          Number  clear width between stringers, mm
  riser_count    Integer 0 = auto
  tread_run      Number  0 = auto
  flight_risers  Integer (list) risers per flight; overrides riser_count
  landing_depth  Number  0 = width
  landing_depths Number (list) per landing
  well_gap       Number  U: gap between flights; U2: minimum gap
  winders        Boolean
  winder_count   Integer winders per 90 degree turn
  nosing, tread_thk, riser_thk, landing_thk   Number
  open_risers    Boolean
  stringer_type  Text    closed | cut | centre | none
  stringer_depth, stringer_thk                Number
  top_connection    Text  floor | top_tread
  bottom_connection Text  floor | starter_tread
  spiral_radius, spiral_column_radius, turn_angle   Number
  slab_thk       Number  floor above; ceiling = floor_to_floor - slab_thk
  opening        Curve   closed plan curve of the floor opening above (turns on the headroom check)
  rules          Text    JSON overrides for config/code_limits.json, e.g. {"rise_max_mm": 190}

OUTPUTS
  treads, risers, landings, stringers, supports   Breps (supports = spiral column)
  guard_lines     left/right guard path polylines (preview)
  guard_path      JSON string: the guard_path contract (docs/guard_path.md), document frame
  info            key/value text lines
  warnings        code-check warnings (strings)
  warning_index   failing step index per warning (-1 = whole stair)
  bom             quantity lines
  report          one text block for a panel
"""
# Folder holding 'core' and 'adapters'. Empty = find it next to this .gh (see adapters/locate.py).
LIBRARY_PATH = ""
RELOAD_LIBRARY = True   # re-import the library every solution (while editing it)

import importlib
import json
import os
import sys

from Grasshopper.Kernel import GH_RuntimeMessageLevel
import Rhino


def _gh_file():
    try:
        doc = ghenv.Component.OnPingDocument()
        return doc.FilePath if doc is not None and doc.IsFilePathDefined else None
    except Exception:
        return None


def _error(msg):
    ghenv.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Error, msg)
    ghenv.Component.Message = "error"


def _locate_module():
    """Bootstrap: find adapters/locate.py without the library on sys.path yet."""
    rdoc = Rhino.RhinoDoc.ActiveDoc
    files = [_gh_file(), getattr(rdoc, "Path", None) if rdoc is not None else None]
    candidates = []
    if LIBRARY_PATH.strip():
        p = LIBRARY_PATH.strip()
        if not os.path.isabs(p) and files[0]:
            p = os.path.join(os.path.dirname(files[0]), p)
        candidates.append(p)
    if os.environ.get("STAIRGEN_PATH"):
        candidates.append(os.environ["STAIRGEN_PATH"])
    for f in files:
        if not f:
            continue
        d = os.path.dirname(os.path.abspath(f))
        for _ in range(3):
            candidates.append(d)
            try:
                for n in os.listdir(d):
                    sub = os.path.join(d, n)
                    if "stair" in n.lower() and os.path.isdir(sub):
                        candidates.append(sub)
                        for m in os.listdir(sub):
                            if "stair" in m.lower() and os.path.isdir(os.path.join(sub, m)):
                                candidates.append(os.path.join(sub, m))
            except OSError:
                pass
            d = os.path.dirname(d)
    for c in candidates:
        if os.path.isfile(os.path.join(c, "adapters", "locate.py")) and \
                os.path.isfile(os.path.join(c, "core", "__init__.py")):
            return os.path.normpath(c), candidates
    return None, candidates


def _import_library():
    folder, looked = _locate_module()
    if folder is None:
        return None, ("Stair library not found (folder with 'core' and 'adapters').\nPut it next "
                      "to this .gh file, set LIBRARY_PATH in the script or the STAIRGEN_PATH "
                      "environment variable.\nLooked in:\n  " + "\n  ".join(looked))
    importlib.invalidate_caches()
    sys.path[:] = [p for p in sys.path if not (p != folder and
                                               os.path.isfile(os.path.join(p, "core", "stairs", "layout.py")))]
    if folder not in sys.path:
        sys.path.insert(0, folder)
    if RELOAD_LIBRARY:
        for name in list(sys.modules):
            if name.split(".")[0] in ("core", "adapters"):
                del sys.modules[name]
    try:
        import core.stairs as stairs
        import adapters.stairs_rhino as adapter
    except Exception as e:
        return None, "Could not import the stair library from {}:\n{}: {}".format(
            folder, type(e).__name__, e)
    return (stairs, adapter), None


def _num(name, default=None, zero_is_none=False):
    v = globals().get(name)
    if v is None or v == "":
        return default
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError("{} = '{}' is not a number".format(name, v))
    if zero_is_none and v <= 0:
        return default
    return v


def _text(name, default):
    v = globals().get(name)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip().strip('"')


def _bool(name, default=False):
    v = globals().get(name)
    if v is None or v == "":
        return default
    if isinstance(v, str):
        return v.strip().lower() in ("true", "yes", "1", "on")
    return bool(v)


def _int_list(name):
    v = globals().get(name)
    if v is None or v == "" or (isinstance(v, (list, tuple)) and not v):
        return None
    if not isinstance(v, (list, tuple)):
        v = [v]
    out = [int(float(x)) for x in v]
    return out if any(out) else None


def _float_list(name):
    v = globals().get(name)
    if v is None or v == "" or (isinstance(v, (list, tuple)) and not v):
        return None
    if not isinstance(v, (list, tuple)):
        v = [v]
    out = [float(x) for x in v]
    return out if any(out) else None


def run():
    global treads, risers, landings, stringers, supports, guard_lines, guard_path
    global info, warnings, warning_index, bom, report
    rdoc = Rhino.RhinoDoc.ActiveDoc
    if rdoc is None:
        raise ValueError("No Rhino document is open (the stair uses its units and tolerance).")
    lib, err = _import_library()
    if lib is None:
        raise ValueError(err)
    stairs, adapter = lib
    to_mm, tol_doc, unit_name = adapter.document_units(rdoc)
    unit_scale = 1.0 / to_mm           # mm -> document units

    rules = {}
    rules_text = _text("rules", "")
    if rules_text:
        try:
            rules = json.loads(rules_text)
        except ValueError as e:
            raise ValueError("rules is not valid JSON: {}".format(e))

    base = globals().get("base_pt")
    rot = _num("rotation", 0.0)
    opening_curve = globals().get("opening")
    opening = adapter.curve_to_polygon_mm(opening_curve, to_mm, base, rot, tol_doc) \
        if opening_curve is not None else None

    params = stairs.StairParams(
        stair_type=_text("stair_type", "straight"), turn=_text("turn", "left").lower(),
        floor_to_floor=_num("floor_to_floor", 2800.0), width=_num("width", 900.0),
        riser_count=_num("riser_count", None, zero_is_none=True),
        tread_run=_num("tread_run", None, zero_is_none=True),
        flight_risers=_int_list("flight_risers"),
        landing_depth=_num("landing_depth", None, zero_is_none=True),
        landing_depths=_float_list("landing_depths"),
        well_gap=_num("well_gap", 0.0), winders=_bool("winders"),
        winder_count=int(_num("winder_count", 3)),
        nosing=_num("nosing", 25.0), tread_thk=_num("tread_thk", 38.0),
        riser_thk=_num("riser_thk", 19.0), open_risers=_bool("open_risers"),
        landing_thk=_num("landing_thk", 250.0),
        stringer_type=_text("stringer_type", "closed").lower(),
        stringer_depth=_num("stringer_depth", 286.0), stringer_thk=_num("stringer_thk", 38.0),
        top_connection=_text("top_connection", "floor").lower(),
        bottom_connection=_text("bottom_connection", "floor").lower(),
        spiral_radius=_num("spiral_radius", 1000.0),
        spiral_column_radius=_num("spiral_column_radius", 60.0),
        turn_angle=_num("turn_angle", 360.0), slab_thk=_num("slab_thk", 250.0),
        opening=opening, rules=rules)
    if params.riser_count is not None:
        params.riser_count = int(params.riser_count)

    result = stairs.build_stair(params)
    geo = adapter.to_rhino(result, base, rot, unit_scale, tol_doc)

    treads, risers, landings = geo["treads"], geo["risers"], geo["landings"]
    stringers, supports = geo["stringers"], geo["supports"]
    guard_lines, guard_path = geo["guard_lines"], geo["guard_path_json"]
    warnings, warning_index = result["warnings"], result["warning_index"]
    inf = result["info"]
    info = ["{} = {}".format(k, _fmt(v)) for k, v in sorted(inf.items())]
    bom = ["{}: {} x  {}".format(b["part"], b["count"], ", ".join(
        "{} {}".format(k, v) for k, v in b.items() if k not in ("part", "count"))) for b in result["bom"]]
    lines = ["STAIR {} ({} turn)".format(inf["stair_type"], inf["turn"]),
             "{} risers x {:.1f} mm, run {:.0f} mm, {:.1f} deg".format(
                 inf["n_risers"], inf["rise"], inf["run"], inf["angle_deg"]),
             "flights (risers): {}".format(inf["flights"]),
             "treads {}, winders {}, landings {}".format(inf["n_treads"], inf["n_winders"],
                                                          inf["n_landings"])]
    if inf.get("landing_depths"):
        lines.append("landing depths: {}".format([round(d) for d in inf["landing_depths"]]))
    if inf.get("well_gap") is not None:
        lines.append("well gap: {:.0f} mm".format(inf["well_gap"]))
    if inf.get("headroom_checked"):
        lines.append("headroom min: {:.0f} mm at step {}".format(inf["headroom_min"],
                                                                 inf["headroom_at_step"]))
    else:
        lines.append("headroom: not checked (set 'opening' for the floor above)")
    lines.append("plan size: {:.0f} x {:.0f} mm".format(*inf["plan_size"]))
    lines.append("document: {} (tolerance {:g}); values above in mm".format(unit_name, tol_doc))
    if warnings:
        lines += ["", "WARNINGS:"] + ["  " + w for w in warnings]
    else:
        lines += ["", "no code warnings (limits: config/code_limits.json, verify against OBC)"]
    if result["remarks"]:
        lines += ["", "remarks:"] + ["  " + r for r in result["remarks"]]
    lines += ["", "BOM:"] + ["  " + b for b in bom]
    lines.append("")
    lines.append("DESIGN AID ONLY - NOT A CODE COMPLIANCE CERTIFICATION")
    report = "\n".join(lines)
    for w in warnings:
        ghenv.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, w)
    ghenv.Component.Message = "{} risers, {} warn".format(inf["n_risers"], len(warnings))


def _fmt(v):
    if isinstance(v, float):
        return "{:.2f}".format(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    return str(v)


try:
    run()
except ValueError as e:
    _error(str(e))
except Exception as e:
    import traceback
    traceback.print_exc()
    _error("Stair generator failed: {}: {} (see 'out')".format(type(e).__name__, e))
