"""Turn core.guards data into RhinoCommon geometry. Rhino 8, Python 3. No design logic.

    from adapters.guards_rhino import to_rhino, curves_to_polylines
    geo = to_rhino(result, unit_scale, tolerance)
    geo["posts"], geo["top_rail"], geo["bottom_rail"], geo["handrail"], geo["brackets"],
    geo["balusters"], geo["bars"], geo["cables"], geo["panels"], geo["frames"], geo["clamps"]

Everything the core returns is already in the document frame when the stair guard_path
came from the stair component (its JSON is in document units); ``unit_scale`` then is the
mm -> document factor for the sizes (post size, rail profile ...), and 1.0 for positions.
"""
import math

import Rhino
import Rhino.Geometry as rg


def _p(q, s=1.0):
    return rg.Point3d(q[0] * s, q[1] * s, q[2] * s)


def _v(q, s=1.0):
    return rg.Vector3d(q[0] * s, q[1] * s, (q[2] if len(q) > 2 else 0.0) * s)


def profile_curve(profile, plane, scale):
    """Closed profile curve in ``plane`` (plane origin = profile centre). Sizes in mm * scale."""
    shape = profile.get("shape", "rect")
    if shape == "round":
        return rg.Circle(plane, profile["d"] * scale / 2.0).ToNurbsCurve()
    if shape == "custom":
        pts = [plane.PointAt(x * scale, y * scale) for x, y in profile["points"]]
        pts.append(pts[0])
        return rg.PolylineCurve(pts)
    w = profile.get("w", profile.get("size", 50.0)) * scale
    h = profile.get("h", profile.get("d", profile.get("size", 50.0))) * scale
    rect = rg.Rectangle3d(plane, rg.Interval(-w / 2.0, w / 2.0), rg.Interval(-h / 2.0, h / 2.0))
    return rect.ToNurbsCurve()


def extrude_between(profile, a, b, scale, tolerance, up=None):
    """Prism with ``profile`` from point a to point b (profile plane normal to a->b)."""
    pa, pb = _p(a), _p(b)
    axis = pb - pa
    length = axis.Length
    if length < tolerance:
        return None
    axis.Unitize()
    if up is None:
        up = rg.Vector3d.ZAxis if abs(axis.Z) < 0.9 else rg.Vector3d.XAxis
    xdir = rg.Vector3d.CrossProduct(up, axis)
    if xdir.Length < 1e-9:
        xdir = rg.Vector3d.XAxis
    xdir.Unitize()
    ydir = rg.Vector3d.CrossProduct(axis, xdir)
    plane = rg.Plane(pa, xdir, ydir)
    curve = profile_curve(profile, plane, scale)
    srf = rg.Surface.CreateExtrusion(curve, axis * length)
    if srf is None:
        return None
    brep = srf.ToBrep()
    capped = brep.CapPlanarHoles(tolerance)
    return capped if capped is not None else brep


def post_brep(post, scale, tolerance):
    base, top = post["base"], post["top"]
    if top[2] - base[2] < tolerance:
        return None
    d = post.get("direction", (1.0, 0.0))
    ang = math.radians(post.get("rotation_deg", 0.0))
    # profile x along the guard (post direction + rotation), y across, extruded up
    xdir = rg.Vector3d(math.cos(ang), math.sin(ang), 0.0) if "rotation_deg" in post else _v((d[0], d[1], 0.0))
    ydir = rg.Vector3d.CrossProduct(rg.Vector3d.ZAxis, xdir)
    plane = rg.Plane(_p(base), xdir, ydir)
    prof = dict(post["profile"])
    if prof.get("shape") == "rect":
        prof = {"shape": "rect", "w": prof.get("d", prof["w"]), "h": prof["w"]}  # d along, w across
    curve = profile_curve(prof, plane, scale)
    srf = rg.Surface.CreateExtrusion(curve, rg.Vector3d(0, 0, top[2] - base[2]))
    if srf is None:
        return None
    brep = srf.ToBrep()
    capped = brep.CapPlanarHoles(tolerance)
    return capped if capped is not None else brep


def rail_breps(rail, scale, tolerance):
    """One prism per straight segment of the rail polyline (kinks are not mitred)."""
    out = []
    poly = rail["polyline"]
    for a, b in zip(poly, poly[1:]):
        brep = extrude_between(rail["profile"], a, b, scale, tolerance)
        if brep is not None:
            out.append(brep)
    return out


def rail_curve(rail):
    return rg.PolylineCurve([_p(q) for q in rail["polyline"]])


def panel_brep(panel, scale, tolerance):
    pts = [_p(q) for q in panel["polygon"]]
    pts.append(pts[0])
    curve = rg.PolylineCurve(pts)
    thk = panel["thickness"] * scale
    # panel normal: horizontal, perpendicular to the panel's bottom edge
    e = pts[1] - pts[0]
    n = rg.Vector3d(-e.Y, e.X, 0.0)
    if n.Length < 1e-9:
        return None
    n.Unitize()
    srf = rg.Surface.CreateExtrusion(curve, n * thk)
    if srf is None:
        return None
    brep = srf.ToBrep()
    brep.Translate(n * (-thk / 2.0))
    capped = brep.CapPlanarHoles(tolerance)
    return capped if capped is not None else brep


def to_rhino(result, unit_scale=1.0, tolerance=0.01):
    s = unit_scale
    out = {"posts": [], "top_rail": [], "bottom_rail": [], "handrail": [], "brackets": [],
           "balusters": [], "bars": [], "cables": [], "panels": [], "frames": [], "clamps": [],
           "rail_lines": []}
    for post in result["posts"]:
        b = post_brep(post, s, tolerance)
        if b is not None:
            out["posts"].append(b)
    for key in ("top_rail", "bottom_rail", "handrail"):
        for rail in result[key]:
            out[key] += rail_breps(rail, s, tolerance)
            out["rail_lines"].append(rail_curve(rail))
    for br in result["brackets"]:
        out["brackets"].append(rg.Line(_p(br["point"]), _v(br["direction"]) * br["offset"] * s))
    for b in result["infill"]["balusters"]:
        prof = {"shape": "round" if b["profile"]["shape"] == "round" else "rect",
                "d": b["profile"]["size"], "w": b["profile"]["size"], "h": b["profile"]["size"]}
        brep = extrude_between(prof, b["bottom"], b["top"], s, tolerance, up=rg.Vector3d.XAxis)
        if brep is not None:
            out["balusters"].append(brep)
    for key in ("bars", "cables"):
        for bar in result["infill"][key]:
            prof = {"shape": bar["profile"]["shape"], "d": bar["profile"]["size"],
                    "w": bar["profile"]["size"], "h": bar["profile"]["size"]}
            poly = bar["polyline"]
            for a, b in zip(poly, poly[1:]):
                brep = extrude_between(prof, a, b, s, tolerance)
                if brep is not None:
                    out[key].append(brep)
    for panel in result["infill"]["panels"]:
        brep = panel_brep(panel, s, tolerance)
        if brep is not None:
            out["panels"].append(brep)
    for frame in result["infill"]["frames"]:
        prof = {"shape": "rect", "w": frame["size"], "h": frame["size"]}
        poly = frame["polyline"]
        for a, b in zip(poly, poly[1:]):
            brep = extrude_between(prof, a, b, s, tolerance)
            if brep is not None:
                out["frames"].append(brep)
    out["clamps"] = [_p(q) for q in result["infill"]["clamps"]]
    return out


def curves_to_polylines(curves, tolerance, base_geometry=None):
    """Rhino curves -> ([polyline points], [closed flags]) for curve mode.

    ``base_geometry`` (Brep or Mesh) samples the walking surface height under each point."""
    polys, closed = [], []
    for c in curves or []:
        if c is None:
            continue
        if not isinstance(c, rg.Curve) and hasattr(c, "ToNurbsCurve"):
            c = c.ToNurbsCurve()
        pl = c.ToPolyline(tolerance, math.radians(2.0), 0.0, 0.0)
        if pl is None:
            continue
        pts = [rg.Point3d(pl.Point(i)) for i in range(pl.PointCount)]
        if base_geometry is not None:
            pts = [_project(q, base_geometry) for q in pts]
        polys.append([(q.X, q.Y, q.Z) for q in pts])
        closed.append(bool(c.IsClosed))
    return polys, closed


def _project(q, geo):
    """Point on ``geo`` straight below / above q (closest point as a fallback)."""
    try:
        if isinstance(geo, rg.Mesh):
            ray = rg.Ray3d(rg.Point3d(q.X, q.Y, q.Z + 1e6), -rg.Vector3d.ZAxis)
            t = rg.Intersect.Intersection.MeshRay(geo, ray)
            if t >= 0:
                return ray.PointAt(t)
            return geo.ClosestPoint(q)
        hits = rg.Intersect.Intersection.ProjectPointsToBreps([geo], [q], -rg.Vector3d.ZAxis, 0.01)
        if hits:
            return max(hits, key=lambda h: h.Z)
        return geo.ClosestPoint(q)
    except Exception:
        return q


def document_units(doc):
    to_mm = Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem, Rhino.UnitSystem.Millimeters)
    return to_mm, doc.ModelAbsoluteTolerance, str(doc.ModelUnitSystem).split(".")[-1]
