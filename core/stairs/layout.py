"""Build a stair as plain data: treads, risers, landings, stringers, guard path.

Frame: base point = centre of the bottom of the first riser at (0, 0, 0). First flight
along +X. Looking up the stair, left is +Y. Every turn is built as a LEFT turn and the
whole stair is mirrored (y -> -y) at the end for ``turn == "right"``.

Every solid is a polygon (list of (x, y, z)) plus ``thickness`` and a unit ``extrude``
vector: the adapter extrudes the polygon by thickness along that vector.
"""
import math

from ..geom import (add, mul, rot90, rotate, to3, xy, centroid, dedupe,
                    ray_hit_polyline, polygon_area, bbox)
from ..limits import load_limits
from .params import StairParams
from .solver import allocate_risers, default_run
from .checks import run_checks
from .guard import assemble_guard_path
from .bom import build_bom

DOWN = (0.0, 0.0, -1.0)
UP = (0.0, 0.0, 1.0)


class Frame(object):
    """Local frame: origin (2D), travel direction d (unit, 2D), left = rot90(d)."""

    def __init__(self, origin, direction):
        self.o = (float(origin[0]), float(origin[1]))
        self.d = direction
        self.l = rot90(direction)

    def pt(self, s, y, z):
        """(s along travel, y to the left, z) -> world (x, y, z)."""
        p = add(self.o, add(mul(self.d, s), mul(self.l, y)))
        return (p[0], p[1], float(z))

    def pt2(self, s, y):
        return xy(self.pt(s, y, 0.0))


class Build(object):
    """Accumulates the stair while the segments are walked."""

    def __init__(self, params, limits):
        self.p = params
        self.limits = limits
        self.treads, self.risers, self.landings = [], [], []
        self.stringers, self.supports = [], []
        self.steps = []                      # per-step data for the guard path
        self.guard = {"left": [], "right": []}  # list of (kind, flight, [points])
        self.flights_meta = []               # for the headroom check
        self.landings_meta = []
        self.winder_sets = []
        self.remarks = []
        self.step_index = 0
        self.flight_index = 0
        self.landing_index = 0

    # --- helpers ---------------------------------------------------------------------
    def _solid(self, kind, polygon, thickness, extrude, **extra):
        d = {"kind": kind, "polygon": polygon, "thickness": float(thickness),
             "extrude": extrude, "index": None, "flight": self.flight_index}
        d.update(extra)
        return d

    def _guard(self, side, kind, points, flight=None):
        self.guard[side].append((kind, self.flight_index if flight is None else flight,
                                 list(points)))


# --- flights -------------------------------------------------------------------------
def _flight(b, frame, z0, n_risers, rise, run, is_first, is_last):
    p = b.p
    w = p.width
    top_tread = is_last and p.top_connection == "top_tread"
    n_treads = n_risers - 1 + (1 if top_tread else 0)
    plan_length = n_treads * run if top_tread else (n_risers - 1) * run
    z_end = z0 + n_risers * rise
    fi = b.flight_index
    first_step = b.step_index

    # risers: face at s = i*run, board behind it (closed risers only)
    for i in range(n_risers):
        z_lo, z_hi, s = z0 + i * rise, z0 + (i + 1) * rise, i * run
        poly = [frame.pt(s, -w / 2, z_lo), frame.pt(s, w / 2, z_lo),
                frame.pt(s, w / 2, z_hi), frame.pt(s, -w / 2, z_hi)]
        b.risers.append(b._solid("riser", poly, 0.0 if p.open_risers else p.riser_thk,
                                 to3(frame.d, 0.0), index=first_step + i, open=p.open_risers,
                                 z_lo=z_lo, z_hi=z_hi))

    # treads
    for i in range(n_treads):
        z = z0 + (i + 1) * rise
        s0, s1 = i * run - p.nosing, (i + 1) * run
        ext = p.starter_extension if (is_first and i == 0 and
                                      p.bottom_connection == "starter_tread") else 0.0
        poly = [frame.pt(s0, -w / 2 - ext, z), frame.pt(s1, -w / 2 - ext, z),
                frame.pt(s1, w / 2 + ext, z), frame.pt(s0, w / 2 + ext, z)]
        kind = "top_tread" if (top_tread and i == n_treads - 1) else "tread"
        idx = first_step + i
        nosing_l, nosing_r = frame.pt(s0, w / 2, z), frame.pt(s0, -w / 2, z)
        b.treads.append(b._solid(kind, poly, p.tread_thk, DOWN, index=idx, run=run, rise=rise,
                                 nosing=(nosing_r, nosing_l), starter=ext > 0))
        b.steps.append({"index": idx, "kind": "step", "flight": fi,
                        "nosing": frame.pt(s0, 0.0, z), "nosing_left": nosing_l,
                        "nosing_right": nosing_r, "tread_centre": frame.pt((s0 + s1) / 2, 0.0, z),
                        "z": z, "direction": frame.d, "run": run, "rise": rise})

    # guard path along the nosing line, ending at the landing / floor edge. A flight that
    # leaves a landing starts its line at the landing's exit edge (not over the landing),
    # so the plan path never doubles back.
    for side, y in (("left", w / 2), ("right", -w / 2)):
        pts = [frame.pt((i * run - p.nosing) if (i or is_first) else 0.0, y,
                        z0 + (i + 1) * rise) for i in range(n_treads)]
        pts.append(frame.pt(plan_length, y, z_end))
        b._guard(side, "flight", pts)

    _stringers(b, frame, z0, n_risers, rise, run, plan_length)

    b.flights_meta.append({"index": fi, "origin": frame.o, "dir": frame.d, "z0": z0,
                           "rise": rise, "run": run, "plan_length": plan_length,
                           "n_risers": n_risers, "n_treads": n_treads,
                           "first_step": first_step, "width": w,
                           "soffit_depth": p.tread_thk + (p.stringer_depth
                                                          if p.stringer_type != "none" else 0.0)})
    b.step_index += n_treads
    b.flight_index += 1
    return Frame(frame.pt2(plan_length, 0.0), frame.d), z_end


def _stringers(b, frame, z0, n_risers, rise, run, plan_length):
    """Side profiles in the vertical plane along the flight; extruded sideways."""
    p = b.p
    if p.stringer_type == "none" or n_risers < 1:
        return
    w, t, depth = p.width, p.stringer_thk, p.stringer_depth
    slope = rise / run
    s_top = max(plan_length, 0.0)

    if p.stringer_type == "closed":
        # nosing line through (i*run - nosing, z0 + (i+1)*rise); top edge above it, bottom below
        def z_line(s):
            return z0 + rise + slope * (s + p.nosing)
        s_b = (z0 - (z_line(0.0) - depth)) / slope if slope > 0 else 0.0   # bottom meets floor
        s_b = min(s_b, s_top)
        m = p.stringer_top_margin
        profile = [(s_b, z0), (s_b, z_line(s_b) + m), (s_top, z_line(s_top) + m),
                   (s_top, z_line(s_top) - depth)]
        sides = [("left", w / 2, 1.0), ("right", -w / 2, -1.0)]   # outside the treads
    else:
        # cut (sawtooth) profile; treads sit on it. Throat line through (i*run, z0 + i*rise)
        rt = 0.0 if p.open_risers else p.riser_thk
        profile = []
        for i in range(n_risers):
            s = i * run
            profile.append((s + rt, z0 + i * rise - (p.tread_thk if i > 0 else 0.0)))
            profile.append((s + rt, z0 + (i + 1) * rise - p.tread_thk))
        profile.append((s_top, z0 + n_risers * rise - p.tread_thk))
        profile.append((s_top, z0 + (n_risers - 1) * rise - depth))
        s_b = min(depth / slope if slope > 0 else 0.0, s_top)
        profile.append((s_b, z0))
        profile.append((0.0, z0))
        if p.stringer_type == "centre":
            sides = [("centre", 0.0, 0.0)]
        else:
            sides = [("left", w / 2, -1.0), ("right", -w / 2, 1.0)]  # inside the width
    for side, y, inward in sides:
        y0 = y - (t / 2 if side == "centre" else 0.0)
        poly = [frame.pt(s, y0, z) for s, z in profile]
        b.stringers.append(b._solid("stringer", poly, t,
                                    to3(mul(frame.l, inward if inward else 1.0), 0.0),
                                    side=side, stringer_type=p.stringer_type,
                                    length=math.hypot(s_top - s_b, slope * (s_top - s_b))))


# --- landings ------------------------------------------------------------------------
def _landing(b, frame, z, angle, depth):
    """90 or 180 degree landing (left turn). Returns the exit frame."""
    p = b.p
    w = p.width
    D = depth
    li = b.landing_index
    if angle == 90:
        corners = [(0.0, -w / 2), (D, -w / 2), (D, w / 2), (0.0, w / 2)]
        exit_frame = Frame(frame.pt2(D - w / 2, w / 2), frame.l)
        left = [frame.pt(0.0, w / 2, z), frame.pt(D - w, w / 2, z)]
        right = [frame.pt(0.0, -w / 2, z), frame.pt(D, -w / 2, z), frame.pt(D, w / 2, z)]
        across = w
    else:
        g = p.well_gap
        corners = [(0.0, -w / 2), (D, -w / 2), (D, 1.5 * w + g), (0.0, 1.5 * w + g)]
        exit_frame = Frame(frame.pt2(0.0, w + g), mul(frame.d, -1.0))
        left = [frame.pt(0.0, w / 2, z), frame.pt(0.0, w / 2 + g, z)]
        right = [frame.pt(0.0, -w / 2, z), frame.pt(D, -w / 2, z), frame.pt(D, 1.5 * w + g, z),
                 frame.pt(0.0, 1.5 * w + g, z)]
        across = 2 * w + g
    poly = [frame.pt(s, y, z) for s, y in corners]
    idx = b.step_index
    b.landings.append(b._solid("landing", poly, p.landing_thk, DOWN, index=idx, landing=li,
                               z=z, depth=D, across=across, turn_angle=angle))
    b.steps.append({"index": idx, "kind": "landing", "flight": b.flight_index - 1,
                    "landing": li, "nosing": frame.pt(0.0, 0.0, z),
                    "nosing_left": frame.pt(0.0, w / 2, z), "nosing_right": frame.pt(0.0, -w / 2, z),
                    "tread_centre": centroid(poly), "z": z, "direction": frame.d,
                    "run": D, "rise": 0.0})
    b._guard("left", "landing", dedupe(left), flight=b.flight_index - 1)
    b._guard("right", "landing", dedupe(right), flight=b.flight_index - 1)
    b.landings_meta.append({"index": li, "polygon": poly, "z": z, "depth": D, "across": across,
                            "angle": angle, "soffit": z - p.landing_thk})
    b.landing_index += 1
    b.step_index += 1
    return exit_frame, z


def _winders(b, frame, z, angle, rise):
    """Winder set replacing a landing (left turn). Returns (exit frame, z of last winder)."""
    p = b.p
    w = p.width
    k = int(p.winder_count) * (2 if angle == 180 else 1)
    E = (0.0, w / 2)                                   # inner corner (newel)
    if angle == 90:
        boundary = [(0.0, -w / 2), (w, -w / 2), (w, w / 2)]
        exit_frame = Frame(frame.pt2(w / 2, w / 2), frame.l)
    else:
        boundary = [(0.0, -w / 2), (w, -w / 2), (w, 1.5 * w), (0.0, 1.5 * w)]
        exit_frame = Frame(frame.pt2(0.0, w), mul(frame.d, -1.0))
    # rays from E, in local (s, y) coordinates, sweeping from -y (entry line) by `angle`
    hits = []
    for i in range(k + 1):
        phi = -90.0 + angle * i / k
        ray = rotate((1.0, 0.0), phi)
        if i == 0:
            hits.append(((0.0, -w / 2), 0))
        elif i == k:
            hits.append((boundary[-1], len(boundary) - 2))
        else:
            hit = ray_hit_polyline(E, ray, boundary)
            if hit is None:
                raise ValueError("winder ray did not hit the landing boundary")
            hits.append((hit[0], hit[1]))
    walk_offset = b.limits.value("walkline_offset_mm")
    set_steps = []
    first_idx = b.step_index
    for i in range(k):
        zi = z + i * rise
        (P0, seg0), (P1, seg1) = hits[i], hits[i + 1]
        poly_local = [E, P0] + [boundary[j] for j in range(seg0 + 1, seg1 + 1)] + [P1]
        poly = [frame.pt(s, y, zi) for s, y in poly_local]
        idx = first_idx + i
        phi = -90.0 + angle * i / k
        ray = rotate((1.0, 0.0), phi)
        nosing_pt = frame.pt(E[0] + ray[0] * walk_offset, E[1] + ray[1] * walk_offset, zi)
        b.treads.append(b._solid("winder", poly, p.tread_thk, DOWN, index=idx, winder=i,
                                 angle=angle / k, rise=rise, run=walk_offset * math.radians(angle / k),
                                 nosing=(frame.pt(P0[0], P0[1], zi), frame.pt(E[0], E[1], zi))))
        if i > 0:   # riser along ray i, from the previous winder up to this one
            face = [frame.pt(E[0], E[1], zi - rise), frame.pt(P0[0], P0[1], zi - rise),
                    frame.pt(P0[0], P0[1], zi), frame.pt(E[0], E[1], zi)]
            b.risers.append(b._solid("riser", face, 0.0 if p.open_risers else p.riser_thk,
                                     to3(rotate(frame.d, phi + 90.0), 0.0), index=idx,
                                     open=p.open_risers, z_lo=zi - rise, z_hi=zi))
        b.steps.append({"index": idx, "kind": "winder", "flight": b.flight_index - 1,
                        "nosing": nosing_pt, "nosing_left": frame.pt(E[0], E[1], zi),
                        "nosing_right": frame.pt(P0[0], P0[1], zi), "tread_centre": centroid(poly),
                        "z": zi, "direction": rotate(frame.d, phi + 90.0),
                        "run": walk_offset * math.radians(angle / k), "rise": rise if i > 0 else 0.0})
        set_steps.append(idx)
    z_last = z + (k - 1) * rise
    # guard path: inner = newel (bottom and top), outer = winder nosing ends
    b._guard("left", "winders", [frame.pt(E[0], E[1], z), frame.pt(E[0], E[1], z_last)],
             flight=b.flight_index - 1)
    outer = [frame.pt(hits[i][0][0], hits[i][0][1], z + i * rise) for i in range(k)]
    outer.append(frame.pt(hits[k][0][0], hits[k][0][1], z_last))
    b._guard("right", "winders", outer, flight=b.flight_index - 1)
    b.winder_sets.append({"index": len(b.winder_sets), "angle": angle, "count": k,
                          "steps": set_steps, "walkline_run": walk_offset * math.radians(angle / k),
                          "z": z, "soffit": z - p.tread_thk, "first_step": first_idx,
                          "polygon_plan": [frame.pt(s, y, z) for s, y in [E] + boundary]})
    b.step_index += k
    return exit_frame, z_last


# --- spiral --------------------------------------------------------------------------
def _spiral(b, n_risers, rise):
    """Counter-clockwise spiral around the base point (column centre)."""
    p = b.p
    R, rc = p.spiral_radius, p.spiral_column_radius
    top_tread = p.top_connection == "top_tread"
    n_treads = n_risers - 1 + (1 if top_tread else 0)
    dtheta = p.turn_angle / (n_risers - 1) if n_risers > 1 else p.turn_angle
    nos_deg = math.degrees(p.nosing / R) if R > 0 else 0.0
    walk_offset = b.limits.value("walkline_offset_mm")
    walk_r = rc + walk_offset

    def P(r, a, z):
        return (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), z)

    def arc(r, a0, a1, z):
        m = max(2, int(math.ceil(abs(a1 - a0) / 10.0)))
        return [P(r, a0 + (a1 - a0) * j / m, z) for j in range(m + 1)]

    for i in range(n_risers):
        a = i * dtheta
        z_lo, z_hi = i * rise, (i + 1) * rise
        face = [P(rc, a, z_lo), P(R, a, z_lo), P(R, a, z_hi), P(rc, a, z_hi)]
        b.risers.append(b._solid("riser", face, 0.0 if p.open_risers else p.riser_thk,
                                 to3(rotate((1.0, 0.0), a + 90.0), 0.0), index=i,
                                 open=p.open_risers, z_lo=z_lo, z_hi=z_hi))
    for i in range(n_treads):
        a0, a1 = i * dtheta - nos_deg, (i + 1) * dtheta
        z = (i + 1) * rise
        poly = arc(rc, a0, a1, z) + arc(R, a1, a0, z)
        kind = "top_tread" if (top_tread and i == n_treads - 1) else "tread"
        nos_in, nos_out = P(rc, a0, z), P(R, a0, z)
        b.treads.append(b._solid(kind, poly, p.tread_thk, DOWN, index=i, rise=rise,
                                 run=walk_r * math.radians(dtheta), angle=dtheta,
                                 nosing=(nos_out, nos_in)))
        b.steps.append({"index": i, "kind": "step", "flight": 0, "nosing": P(walk_r, a0, z),
                        "nosing_left": nos_in, "nosing_right": nos_out,
                        "tread_centre": P((rc + R) / 2, (a0 + a1) / 2, z), "z": z,
                        "direction": rotate((1.0, 0.0), a0 + 90.0),
                        "run": walk_r * math.radians(dtheta), "rise": rise})
    H = n_risers * rise
    a_end = (n_risers - 1) * dtheta + (dtheta if top_tread else 0.0)
    inner = [P(rc, i * dtheta - nos_deg, (i + 1) * rise) for i in range(n_treads)] + [P(rc, a_end, H)]
    outer = [P(R, i * dtheta - nos_deg, (i + 1) * rise) for i in range(n_treads)] + [P(R, a_end, H)]
    b._guard("left", "flight", inner, flight=0)
    b._guard("right", "flight", outer, flight=0)
    column = arc(max(rc, 1.0), 0.0, 360.0, 0.0)[:-1]
    b.supports.append(b._solid("column", column, H + p.tread_thk, UP, index=0, radius=rc,
                               height=H + p.tread_thk))
    b.flights_meta.append({"index": 0, "spiral": True, "n_risers": n_risers, "n_treads": n_treads,
                           "rise": rise, "run": walk_r * math.radians(dtheta), "dtheta": dtheta,
                           "first_step": 0, "width": R - rc, "R": R, "rc": rc, "z0": 0.0,
                           "soffit_depth": p.tread_thk, "plan_length": None})
    b.step_index = n_treads
    b.flight_index = 1


# --- mirror for right turns ------------------------------------------------------------
def _mirror_point(pt):
    return (pt[0], -pt[1]) + tuple(pt[2:])


def _mirror_build(b):
    def mp(poly):
        return [_mirror_point(q) for q in poly]
    for lst in (b.treads, b.risers, b.landings, b.stringers, b.supports):
        for s in lst:
            s["polygon"] = mp(s["polygon"])
            s["extrude"] = _mirror_point(s["extrude"])
            if "nosing" in s:
                s["nosing"] = (_mirror_point(s["nosing"][1]), _mirror_point(s["nosing"][0]))
            if s.get("side") == "left":
                s["side"] = "right"
            elif s.get("side") == "right":
                s["side"] = "left"
    for st in b.steps:
        for key in ("nosing", "tread_centre"):
            st[key] = _mirror_point(st[key])
        st["nosing_left"], st["nosing_right"] = (_mirror_point(st["nosing_right"]),
                                                 _mirror_point(st["nosing_left"]))
        st["direction"] = _mirror_point(st["direction"])
    left = [(k, f, mp(pts)) for k, f, pts in b.guard["right"]]
    right = [(k, f, mp(pts)) for k, f, pts in b.guard["left"]]
    b.guard = {"left": left, "right": right}
    for fm in b.flights_meta:
        if "origin" in fm:
            fm["origin"] = _mirror_point(fm["origin"])
            fm["dir"] = _mirror_point(fm["dir"])
    for lm in b.landings_meta:
        lm["polygon"] = mp(lm["polygon"])
    for ws in b.winder_sets:
        ws["polygon_plan"] = mp(ws["polygon_plan"])


# --- main ----------------------------------------------------------------------------
def build_stair(params, limits=None):
    """Build the stair described by ``params``. Returns a dict (see the package docstring)."""
    p = params if isinstance(params, StairParams) else StairParams(**params)
    p.validate()
    limits = limits or load_limits("stairs", overrides=p.rules)
    rise_max = limits.value("rise_max_mm")
    n_total, rise, flights, winder_risers = allocate_risers(p, rise_max)
    run = float(p.tread_run) if p.tread_run else default_run(
        rise, limits.value("run_min_mm"), limits.value("run_max_mm"))
    b = Build(p, limits)

    if p.stair_type == "spiral":
        _spiral(b, n_total, rise)
    else:
        angles = p.turn_angles()
        depths = _landing_depths(p, angles, flights, run)
        frame, z = Frame((0.0, 0.0), (1.0, 0.0)), 0.0
        for i, n in enumerate(flights):
            frame, z = _flight(b, frame, z, n, rise, run, i == 0, i == len(flights) - 1)
            if i < len(angles):
                if p.winders and (angles[i] == 90 or p.well_gap == 0):
                    frame, z = _winders(b, frame, z, angles[i], rise)
                else:
                    if p.winders:
                        b.remarks.append("Winders on a half-turn need well_gap = 0; a landing "
                                         "was used for turn {}.".format(i + 1))
                    frame, z = _landing(b, frame, z, angles[i], depths[i])
    if p.turn == "right":
        _mirror_build(b)

    for lst in (b.treads, b.risers, b.landings, b.stringers, b.supports):
        for s in lst:
            s["area_m2"] = polygon_area(s["polygon"]) / 1e6

    guard_path = assemble_guard_path(b, p)
    info = _info(b, p, n_total, rise, run, flights, winder_risers)
    warnings, warning_index, headroom = run_checks(b, p, limits, info)
    info["headroom_min"] = headroom["min"]
    info["headroom_at_step"] = headroom["step"]
    info["headroom_checked"] = headroom["checked"]
    return {
        "treads": b.treads, "risers": b.risers, "landings": b.landings,
        "stringers": b.stringers, "supports": b.supports,
        "steps": b.steps, "guard_path": guard_path,
        "info": info, "warnings": warnings, "warning_index": warning_index,
        "remarks": b.remarks, "bom": build_bom(b, info),
    }


def _landing_depths(p, angles, flights, run):
    depths = []
    for i, angle in enumerate(angles):
        if p.landing_depths is not None and i < len(p.landing_depths):
            depths.append(float(p.landing_depths[i]))
        elif p.landing_depth is not None:
            depths.append(float(p.landing_depth))
        else:
            d = p.width
            if p.stair_type == "U2" and i == 1 and p.well_gap > 0:
                # landing 2 grows so the well between flights 1 and 3 is at least well_gap
                d = max(d, p.well_gap + p.width - (flights[1] - 1) * run)
            depths.append(d)
    return depths


def _info(b, p, n_total, rise, run, flights, winder_risers):
    pts = [q for s in b.treads + b.landings + b.risers for q in s["polygon"]]
    lo, hi = bbox(pts) if pts else ((0, 0, 0), (0, 0, 0))
    info = {
        "stair_type": p.stair_type, "turn": p.turn,
        "n_risers": n_total, "rise": rise, "run": run,
        "n_treads": len([t for t in b.treads if t["kind"] in ("tread", "top_tread")]),
        "n_winders": len([t for t in b.treads if t["kind"] == "winder"]),
        "n_landings": len(b.landings),
        "flights": flights, "winder_risers": winder_risers,
        "flight_rise": [n * rise for n in flights],
        "landing_depths": [l["depth"] for l in b.landings],
        "well_gap": _well_gap(b, p),
        "angle_deg": math.degrees(math.atan2(rise, run)),
        "total_going": sum(fm["plan_length"] or 0.0 for fm in b.flights_meta),
        "bbox_min": lo, "bbox_max": hi,
        "plan_size": (hi[0] - lo[0], hi[1] - lo[1]),
        "width": p.width, "units": "mm",
    }
    if p.stair_type == "spiral":
        fm = b.flights_meta[0]
        info["spiral"] = {"radius": fm["R"], "column_radius": fm["rc"],
                          "angle_per_tread": fm["dtheta"], "walkline_run": fm["run"],
                          "narrow_run": fm["rc"] * math.radians(fm["dtheta"])}
    if b.winder_sets:
        info["winder_sets"] = [{"angle": w["angle"], "count": w["count"],
                                "walkline_run": w["walkline_run"]} for w in b.winder_sets]
    return info


def _well_gap(b, p):
    """Clear gap between the first and the last flight (U, U2) measured in plan."""
    if p.stair_type not in ("U", "U2") or len(b.flights_meta) < 2:
        return None
    f1, f3 = b.flights_meta[0], b.flights_meta[-1]
    # both run along +/-X in the unmirrored frame; distance between their edges in y
    y1 = f1["origin"][1]
    y3 = f3["origin"][1]
    return abs(y3 - y1) - p.width
