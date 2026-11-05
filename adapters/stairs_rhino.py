"""Turn core.stairs data into RhinoCommon geometry. Rhino 8, Python 3. No design logic here.

    from adapters.stairs_rhino import to_rhino
    geo = to_rhino(result, base_point, rotation_deg, unit_scale, tolerance)
    geo["treads"]  -> list of Brep, ... geo["guard_lines"] -> list of PolylineCurve
"""
import json
import math

import Rhino
import Rhino.Geometry as rg

SOLID_KEYS = ("treads", "risers", "landings", "stringers", "supports")


def _pt(q, xf):
    p = rg.Point3d(q[0], q[1], q[2] if len(q) > 2 else 0.0)
    p.Transform(xf)
    return p


def _vec(v, xf):
    w = rg.Vector3d(v[0], v[1], v[2] if len(v) > 2 else 0.0)
    w.Transform(xf)
    return w


def rotation(rotation_deg):
    return rg.Transform.Rotation(math.radians(float(rotation_deg or 0.0)), rg.Vector3d.ZAxis,
                                 rg.Point3d.Origin)


def placement(base_point, rotation_deg, unit_scale):
    """Transform from the core frame (mm, base at origin, +X) to the document."""
    xf = rotation(rotation_deg) * rg.Transform.Scale(rg.Point3d.Origin, float(unit_scale))
    if base_point is not None:
        bp = rg.Point3d(base_point)
        xf = rg.Transform.Translation(bp.X, bp.Y, bp.Z) * xf
    return xf


def polyline(points, xf, closed=True):
    pts = [_pt(q, xf) for q in points]
    if closed and pts and pts[0].DistanceTo(pts[-1]) > 1e-9:
        pts.append(pts[0])
    return rg.PolylineCurve(pts)


def solid(item, xf, rot, unit_scale, tolerance):
    """Polygon + thickness + extrude vector -> capped Brep (or the planar face for 0 thickness)."""
    curve = polyline(item["polygon"], xf, closed=True)
    thickness = float(item["thickness"]) * float(unit_scale)
    if thickness <= 1e-9:
        faces = rg.Brep.CreatePlanarBreps(curve, tolerance)
        return faces[0] if faces else None
    direction = _vec(item["extrude"], rot)
    direction.Unitize()
    srf = rg.Surface.CreateExtrusion(curve, direction * thickness)
    if srf is None:
        return None
    brep = srf.ToBrep()
    capped = brep.CapPlanarHoles(tolerance)
    return capped if capped is not None else brep


def to_rhino(result, base_point=None, rotation_deg=0.0, unit_scale=1.0, tolerance=0.01):
    xf = placement(base_point, rotation_deg, unit_scale)
    rot = rotation(rotation_deg)
    out = {}
    for key in SOLID_KEYS:
        out[key] = [b for b in (solid(item, xf, rot, unit_scale, tolerance) for item in result[key])
                    if b is not None]
    gp = result["guard_path"]
    out["guard_lines"] = [polyline(gp["sides"][s]["polyline"], xf, closed=False)
                          for s in ("left", "right")]
    out["nosing_points"] = [_pt(s["nosing"], xf) for s in gp["steps"]]
    out["guard_path_json"] = json.dumps(transform_guard_path(gp, xf, rot, unit_scale))
    return out


def transform_guard_path(gp, xf, rot, unit_scale):
    """guard_path with every point moved into the document frame."""
    def tp(q):
        p = _pt(q, xf)
        return [p.X, p.Y, p.Z]

    def tv(v):
        w = _vec((v[0], v[1], 0.0), rot)
        return [w.X, w.Y]

    out = {"version": gp["version"], "units": gp["units"], "document_scale": unit_scale,
           "stair_type": gp["stair_type"], "turn": gp["turn"],
           "width": gp["width"] * unit_scale, "rise": (gp["rise"] or 0.0) * unit_scale,
           "sides": {}, "steps": []}
    for side, data in gp["sides"].items():
        out["sides"][side] = {"polyline": [tp(q) for q in data["polyline"]],
                              "segments": data["segments"], "breaks": data["breaks"],
                              "length": data["length"] * unit_scale}
    for s in gp["steps"]:
        out["steps"].append({
            "index": s["index"], "kind": s["kind"], "flight": s["flight"],
            "nosing": tp(s["nosing"]), "nosing_left": tp(s["nosing_left"]),
            "nosing_right": tp(s["nosing_right"]), "tread_centre": tp(s["tread_centre"]),
            "z": tp(s["nosing"])[2], "direction": tv(s["direction"]),
            "run": s["run"] * unit_scale, "rise": s["rise"] * unit_scale})
    return out


def document_units(doc):
    """(model unit -> mm factor, absolute tolerance in model units, unit name)."""
    to_mm = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Millimeters)
    return to_mm, doc.ModelAbsoluteTolerance, str(doc.ModelUnitSystem).split(".")[-1]


def curve_to_polygon_mm(curve, to_mm, base_point=None, rotation_deg=0.0, tolerance=0.01):
    """A closed Rhino curve (e.g. the floor opening) -> plan polygon in the core frame, mm."""
    if curve is None:
        return None
    if hasattr(curve, "ToNurbsCurve") and not isinstance(curve, rg.Curve):
        curve = curve.ToNurbsCurve()
    ok, inverse = placement(base_point, rotation_deg, 1.0 / to_mm).TryGetInverse()
    if not ok:
        return None
    pl = curve.ToPolyline(tolerance, math.radians(1.0), 0.0, 0.0)   # PolylineCurve
    if pl is None:
        return None
    pts = []
    for i in range(pl.PointCount):
        q = rg.Point3d(pl.Point(i))
        q.Transform(inverse)
        pts.append((q.X, q.Y))
    if len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6:
        pts.pop()
    return pts
