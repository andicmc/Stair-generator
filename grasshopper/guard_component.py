"""GUARD / RAILING - Grasshopper Python 3 Script component (Rhino 8).

Thin component: design logic in core/guards (pure Python, tested); Rhino geometry by
adapters/guards_rhino. Paste into a Python 3 Script component and add the inputs/outputs
below (names must match). All sizes in mm whatever the document units.

INPUTS (optional unless noted)
  guard_path     Text    JSON from the stair component's `guard_path` output (stair mode)
  side           Text    stair mode: left | right | both
  curves         Curve   (list) curve mode: any curves, 2D/3D, open or closed
  base           Brep/Mesh  curve mode: walking surface to sample heights from
  curve_outward  Text    curve mode: falling side = left | right (of the curve direction)
  context        Text    residential | other   (guard height from config)
  height_flight, height_landing   Number  guard height (to the top of the top rail), mm
  inset          Number  guard plane from the edge towards the stair (default post_size/2)
  transition     Text    smooth | sharp
  post_rules     Text    (list) every_step | every_n_steps | max_spacing (corners+ends always)
  post_every_n   Integer
  post_max_spacing Number
  post_on_tread  Text    centre | nosing
  post_tread_offset Number
  post_shape     Text    square | rect | round | custom
  post_size, post_depth, post_rotation   Number
  post_profile   Curve   custom closed profile curve (mm, centred on the origin, XY plane)
  post_mount     Text    top | fascia | embedded
  fascia_drop, fascia_offset, embed_depth  Number
  top_rail_shape Text    rect | round | custom ; top_rail_w, top_rail_h Number ; top_rail_profile Curve
  top_rail_gap   Number
  bottom_rail    Boolean ; bottom_gap, bottom_rail_w, bottom_rail_h Number ; bottom_rail_shape Text
  handrail       Boolean ; handrail_sides Text ; handrail_height Number ; handrail_shape Text
  handrail_size, handrail_h, handrail_offset, bracket_spacing Number
  handrail_ext_top, handrail_ext_bottom Number ; handrail_returns Boolean
  infill         Text    balusters | horizontal | cable | glass | mesh | none
  baluster_spacing, baluster_size Number ; balusters_per_tread Integer ; baluster_shape Text
  bar_count Integer ; bar_spacing, bar_size Number
  cable_diameter, cable_spacing Number
  glass_thk, glass_gap, glass_bottom_gap, clamp_spacing Number
  mesh_frame, mesh_panel_thk Number
  rules          Text    JSON overrides for config/code_limits.json (guards section)

OUTPUTS
  posts, top_rail, bottom_rail, handrail, balusters, bars, cables, panels, frames  Breps
  brackets  Lines (bracket from the handrail to the wall)
  clamps    Points
  rail_lines  rail centrelines (preview)
  info, warnings, warning_index, bom, report
"""
LIBRARY_PATH = ""
RELOAD_LIBRARY = True

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


def _locate():
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
        if os.path.isfile(os.path.join(c, "adapters", "guards_rhino.py")) and \
                os.path.isfile(os.path.join(c, "core", "__init__.py")):
            return os.path.normpath(c), candidates
    return None, candidates


def _import_library():
    folder, looked = _locate()
    if folder is None:
        return None, ("Stair library not found (folder with 'core' and 'adapters').\nPut it next "
                      "to this .gh file, set LIBRARY_PATH in the script or the STAIRGEN_PATH "
                      "environment variable.\nLooked in:\n  " + "\n  ".join(looked))
    importlib.invalidate_caches()
    sys.path[:] = [p for p in sys.path if not (p != folder and
                                               os.path.isfile(os.path.join(p, "core", "guards", "layout.py")))]
    if folder not in sys.path:
        sys.path.insert(0, folder)
    if RELOAD_LIBRARY:
        for name in list(sys.modules):
            if name.split(".")[0] in ("core", "adapters"):
                del sys.modules[name]
    try:
        import core.guards as guards
        import adapters.guards_rhino as adapter
    except Exception as e:
        return None, "Could not import the guard library from {}:\n{}: {}".format(
            folder, type(e).__name__, e)
    return (guards, adapter), None


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


def _list(name):
    v = globals().get(name)
    if v is None or v == "":
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def _profile_points(curve, tolerance):
    """Closed Rhino curve in the XY plane -> [(x, y)] in mm, centred on its centroid."""
    if curve is None:
        return None
    import Rhino.Geometry as rg
    c = curve if isinstance(curve, rg.Curve) else curve.ToNurbsCurve()
    pl = c.ToPolyline(tolerance, 0.03, 0.0, 0.0)
    pts = [(pl.Point(i).X, pl.Point(i).Y) for i in range(pl.PointCount)]
    if len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) < 1e-9 and abs(pts[0][1] - pts[-1][1]) < 1e-9:
        pts.pop()
    cx = sum(q[0] for q in pts) / len(pts)
    cy = sum(q[1] for q in pts) / len(pts)
    return [(x - cx, y - cy) for x, y in pts]


def run():
    global posts, top_rail, bottom_rail, handrail, balusters, bars, cables, panels, frames
    global brackets, clamps, rail_lines, info, warnings, warning_index, bom, report
    rdoc = Rhino.RhinoDoc.ActiveDoc
    if rdoc is None:
        raise ValueError("No Rhino document is open (the guard uses its units and tolerance).")
    lib, err = _import_library()
    if lib is None:
        raise ValueError(err)
    guards, adapter = lib
    to_mm, tol_doc, unit_name = adapter.document_units(rdoc)
    unit_scale = 1.0 / to_mm

    rules = {}
    rules_text = _text("rules", "")
    if rules_text:
        try:
            rules = json.loads(rules_text)
        except ValueError as e:
            raise ValueError("rules is not valid JSON: {}".format(e))

    gp_text = _text("guard_path", "")
    curve_list = [c for c in _list("curves") if c is not None]
    kw = {}
    if gp_text:
        try:
            gp = json.loads(gp_text)
        except ValueError as e:
            raise ValueError("guard_path is not valid JSON: {}".format(e))
        doc_scale = float(gp.get("document_scale", 1.0))   # mm -> document in that JSON
        # the core works in mm: scale the JSON's points back to mm
        gp = _scale_guard_path(gp, 1.0 / doc_scale)
        kw.update(mode="stair", guard_path=gp, sides=_text("side", "both").lower())
    elif curve_list:
        polys, closed = adapter.curves_to_polylines(curve_list, tol_doc, globals().get("base"))
        polys = [[(x * to_mm, y * to_mm, z * to_mm) for x, y, z in poly] for poly in polys]
        kw.update(mode="curve", curves=polys, curves_closed=closed,
                  curve_outward=_text("curve_outward", "right").lower())
    else:
        raise ValueError("Connect guard_path (from the stair component) or curves.")

    params = guards.GuardParams(
        context=_text("context", "residential").lower(),
        height_flight=_num("height_flight", None, True), height_landing=_num("height_landing", None, True),
        inset=_num("inset", None), transition=_text("transition", "smooth").lower(),
        post_rules=[str(r).strip().lower() for r in _list("post_rules")] or ["every_step", "corners", "ends"],
        post_every_n=int(_num("post_every_n", 2)), post_max_spacing=_num("post_max_spacing", 1200.0),
        post_on_tread=_text("post_on_tread", "centre").lower(),
        post_tread_offset=_num("post_tread_offset", 0.0),
        post_shape=_text("post_shape", "square").lower(), post_size=_num("post_size", 50.0),
        post_depth=_num("post_depth", 50.0), post_rotation=_num("post_rotation", 0.0),
        post_custom_profile=_profile_points(globals().get("post_profile"), tol_doc),
        post_mount=_text("post_mount", "top").lower(), fascia_drop=_num("fascia_drop", 200.0),
        fascia_offset=_num("fascia_offset", 40.0), embed_depth=_num("embed_depth", 100.0),
        top_rail_shape=_text("top_rail_shape", "rect").lower(), top_rail_w=_num("top_rail_w", 60.0),
        top_rail_h=_num("top_rail_h", 40.0),
        top_rail_custom_profile=_profile_points(globals().get("top_rail_profile"), tol_doc),
        top_rail_gap=_num("top_rail_gap", 0.0),
        bottom_rail=_bool("bottom_rail", False), bottom_gap=_num("bottom_gap", 90.0),
        bottom_rail_w=_num("bottom_rail_w", 40.0), bottom_rail_h=_num("bottom_rail_h", 30.0),
        bottom_rail_shape=_text("bottom_rail_shape", "rect").lower(),
        handrail=_bool("handrail", False), handrail_sides=_text("handrail_sides", "same").lower(),
        handrail_height=_num("handrail_height", None, True),
        handrail_shape=_text("handrail_shape", "round").lower(),
        handrail_size=_num("handrail_size", 42.0), handrail_h=_num("handrail_h", 42.0),
        handrail_offset=_num("handrail_offset", 75.0), bracket_spacing=_num("bracket_spacing", 1200.0),
        handrail_ext_top=_num("handrail_ext_top", 300.0),
        handrail_ext_bottom=_num("handrail_ext_bottom", 300.0),
        handrail_returns=_bool("handrail_returns", True),
        infill=_text("infill", "balusters").lower(),
        baluster_spacing=_num("baluster_spacing", 100.0), balusters_per_tread=int(_num("balusters_per_tread", 0)),
        baluster_shape=_text("baluster_shape", "square").lower(), baluster_size=_num("baluster_size", 20.0),
        bar_count=int(_num("bar_count", 0)), bar_spacing=_num("bar_spacing", 100.0),
        bar_size=_num("bar_size", 12.0), cable_diameter=_num("cable_diameter", 4.0),
        cable_spacing=_num("cable_spacing", 80.0), glass_thk=_num("glass_thk", 10.0),
        glass_gap=_num("glass_gap", 15.0), glass_bottom_gap=_num("glass_bottom_gap", 90.0),
        clamp_spacing=_num("clamp_spacing", 600.0), mesh_frame=_num("mesh_frame", 25.0),
        mesh_panel_thk=_num("mesh_panel_thk", 3.0), rules=rules, **kw)

    result = guards.build_guard(params)
    result = _scale_result(result, unit_scale)          # positions mm -> document units
    geo = adapter.to_rhino(result, unit_scale, tol_doc)

    posts, top_rail, bottom_rail, handrail = geo["posts"], geo["top_rail"], geo["bottom_rail"], geo["handrail"]
    balusters, bars, cables, panels, frames = geo["balusters"], geo["bars"], geo["cables"], geo["panels"], geo["frames"]
    brackets, clamps, rail_lines = geo["brackets"], geo["clamps"], geo["rail_lines"]
    warnings, warning_index = result["warnings"], result["warning_index"]
    inf = result["info"]
    info = ["{} = {}".format(k, _fmt(v)) for k, v in sorted(inf.items())]
    bom = ["{}: {} x  {}".format(b["part"], b["count"], ", ".join(
        "{} {}".format(k, v) for k, v in b.items() if k not in ("part", "count"))) for b in result["bom"]]
    lines = ["GUARD ({} mode, {} side(s))".format(inf["mode"], len(inf["sides"])),
             "height flights {:.0f} / landings {:.0f} mm, infill: {}, transition: {}".format(
                 inf["height_flight"], inf["height_landing"], inf["infill"], inf["transition"]),
             "posts: {} (max spacing {:.0f} mm)".format(inf["post_count"], inf["max_post_spacing"]),
             "top rail {:.2f} m, bottom rail {:.2f} m, handrail {:.2f} m".format(
                 inf["top_rail_length"] / 1000.0, inf["bottom_rail_length"] / 1000.0,
                 inf["handrail_length"] / 1000.0),
             "balusters {}, panels {} ({:.2f} m2), max infill clear {:.0f} mm".format(
                 inf["baluster_count"], inf["panel_count"], inf["glass_area_m2"], inf["max_infill_clear"]),
             "document: {} (tolerance {:g}); values above in mm".format(unit_name, tol_doc)]
    if warnings:
        lines += ["", "WARNINGS:"] + ["  " + w for w in warnings]
    else:
        lines += ["", "no code warnings (limits: config/code_limits.json, verify against OBC)"]
    lines += ["", "BOM:"] + ["  " + b for b in bom]
    lines += ["", "DESIGN AID ONLY - NOT A CODE COMPLIANCE CERTIFICATION"]
    report = "\n".join(lines)
    for w in warnings:
        ghenv.Component.AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, w)
    ghenv.Component.Message = "{} posts, {} warn".format(inf["post_count"], len(warnings))


def _scale_guard_path(gp, f):
    if abs(f - 1.0) < 1e-12:
        return gp
    out = dict(gp)
    out["width"] = gp["width"] * f
    out["rise"] = (gp.get("rise") or 0.0) * f
    out["sides"] = {}
    for side, data in gp["sides"].items():
        out["sides"][side] = dict(data)
        out["sides"][side]["polyline"] = [[q[0] * f, q[1] * f, q[2] * f] for q in data["polyline"]]
        out["sides"][side]["length"] = data.get("length", 0.0) * f
    out["steps"] = []
    for s in gp["steps"]:
        st = dict(s)
        for key in ("nosing", "nosing_left", "nosing_right", "tread_centre"):
            st[key] = [q * f for q in s[key]]
        st["z"] = s["z"] * f
        st["run"], st["rise"] = s["run"] * f, s["rise"] * f
        out["steps"].append(st)
    return out


def _scale_result(result, f):
    """Scale every position in the core result from mm to document units (sizes stay mm)."""
    if abs(f - 1.0) < 1e-12:
        return result

    def sp(q):
        return tuple(x * f for x in q)
    for post in result["posts"]:
        post["base"], post["top"] = sp(post["base"]), sp(post["top"])
    for key in ("top_rail", "bottom_rail", "handrail"):
        for rail in result[key]:
            rail["polyline"] = [sp(q) for q in rail["polyline"]]
    for br in result["brackets"]:
        br["point"] = sp(br["point"])
    inf = result["infill"]
    for b in inf["balusters"]:
        b["bottom"], b["top"] = sp(b["bottom"]), sp(b["top"])
    for key in ("bars", "cables", "frames"):
        for item in inf[key]:
            item["polyline"] = [sp(q) for q in item["polyline"]]
    for panel in inf["panels"]:
        panel["polygon"] = [sp(q) for q in panel["polygon"]]
    inf["clamps"] = [sp(q) for q in inf["clamps"]]
    return result


def _fmt(v):
    if isinstance(v, float):
        return "{:.2f}".format(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ", ".join("{}: {}".format(k, _fmt(x)) for k, x in v.items()) + "}"
    return str(v)


try:
    run()
except ValueError as e:
    _error(str(e))
except Exception as e:
    import traceback
    traceback.print_exc()
    _error("Guard failed: {}: {} (see 'out')".format(type(e).__name__, e))
