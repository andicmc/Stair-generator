"""Rail height profiles along a side path: sloped on flights, level on landings.

A profile is a list of pieces {"kind": sloped | level | vertical, "pts": [(t, z), ...]}
in (plan station, height-of-rail-centreline). ``to_3d`` turns it into a polyline in the
guard plane. The same machinery serves the top rail, the bottom rail and the handrail.
"""
import math

from ..geom import dot
from .path import direction_at, point_at


def _flight_slope(path, seg):
    """Rise per plan mm along this side (see path._segment_slope)."""
    return seg.get("slope", 0.0)


def _collinear(path, i, j):
    """Direction of the edge ending at point i vs the edge starting at point j."""
    pts = path["points"]
    if i < 1 or j + 1 >= len(pts):
        return False
    a = (pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
    b = (pts[j + 1][0] - pts[j][0], pts[j + 1][1] - pts[j][1])
    la, lb = math.hypot(*a), math.hypot(*b)
    if la < 1e-9 or lb < 1e-9:
        return False
    return dot(a, b) / (la * lb) > 0.999


def profile(path, h_flight, h_level, transition="smooth"):
    """Centreline height profile for a rail ``h_flight`` above the nosing line and
    ``h_level`` above landings / floors / curves."""
    pts, t, segs = path["points"], path["t"], path["segments"]
    pieces = []
    level_start = {}            # landing index -> station where its level piece begins

    def last_z():
        return pieces[-1]["pts"][-1][1] if pieces else None

    def vertical(tt, z_from, z_to):
        if abs(z_to - z_from) > 1e-6:
            pieces.append({"kind": "vertical", "pts": [(tt, z_from), (tt, z_to)]})

    for k, seg in enumerate(segs):
        kind, i0, i1 = seg["kind"], seg["start"], seg["end"]
        plan_len = t[i1] - t[i0]
        nxt = segs[k + 1] if k + 1 < len(segs) else None

        if kind == "curve":
            pieces.append({"kind": "level", "pts": [(t[i], pts[i][2] + h_level)
                                                     for i in range(i0, i1 + 1)]})
            continue

        if kind == "winders" and plan_len <= 1e-6:      # inner newel: vertical connector
            z_lo = last_z() if pieces else pts[i0][2] + h_level
            vertical(t[i0], z_lo, pts[i1][2] + h_level)
            continue

        if kind in ("flight", "winders"):
            m = _flight_slope(path, seg)
            if m <= 0:
                j = i1 - 1 if i1 - 1 > i0 else i1
                m = (pts[j][2] - pts[i0][2]) / max(t[j] - t[i0], 1e-9)
            z0, t0, t_edge = pts[i0][2] + h_flight, t[i0], t[i1]

            def z_at(tt, z0=z0, t0=t0, m=m):
                return z0 + m * (tt - t0)

            # --- start: from the floor, or from the previous landing ---
            t_a = t0
            if pieces and pieces[-1]["kind"] == "level":
                prev = pieces[-1]
                z_prev = prev["pts"][-1][1]
                t_meet = t0 - (z0 - z_prev) / m if m > 1e-9 else t0
                if transition == "smooth" and _collinear(path, segs[k - 1]["end"], i0) \
                        and prev["pts"][-2][0] - 1e-6 <= t_meet <= t0 + 1e-6:
                    prev["pts"][-1] = (t_meet, z_prev)
                    t_a = t_meet
                else:
                    vertical(t0, z_prev, z_at(t0))
            elif pieces:
                vertical(t0, last_z(), z_at(t0))

            # --- end: into the next landing, or at the top floor ---
            if nxt is not None and nxt["kind"] in ("landing", "curve"):
                z_next = pts[nxt["start"]][2] + h_level
                t_meet = t0 + (z_next - z0) / m if m > 1e-9 else t_edge
                if transition == "smooth" and nxt["end"] > nxt["start"] \
                        and _collinear(path, i1, nxt["start"]) \
                        and t_meet <= t[nxt["start"] + 1] + 1e-6:
                    t_meet = max(t_meet, t_a)
                    pieces.append({"kind": "sloped", "pts": [(t_a, z_at(t_a)), (t_meet, z_at(t_meet))]})
                    level_start[k + 1] = t_meet
                elif t_a < t_meet < t_edge:
                    pieces.append({"kind": "sloped", "pts": [(t_a, z_at(t_a)), (t_meet, z_next)]})
                    pieces.append({"kind": "level", "pts": [(t_meet, z_next), (t_edge, z_next)]})
                    level_start[k + 1] = t_edge
                else:
                    pieces.append({"kind": "sloped", "pts": [(t_a, z_at(t_a)), (t_edge, z_at(t_edge))]})
                    vertical(t_edge, z_at(t_edge), z_next)
            elif nxt is None:
                z_floor = pts[i1][2] + h_level
                t_meet = t0 + (z_floor - z0) / m if m > 1e-9 else t_edge
                if t_a < t_meet < t_edge:
                    pieces.append({"kind": "sloped", "pts": [(t_a, z_at(t_a)), (t_meet, z_floor)]})
                    pieces.append({"kind": "level", "pts": [(t_meet, z_floor), (t_edge, z_floor)]})
                else:
                    pieces.append({"kind": "sloped", "pts": [(t_a, z_at(t_a)), (t_edge, z_at(t_edge))]})
                    if z_at(t_edge) < z_floor - 1e-6:      # landing height above the slope: step up
                        vertical(t_edge, z_at(t_edge), z_floor)
            else:
                # next segment is sloped too (winders / another flight): do not overshoot its
                # starting height; stop the slope there and run level to the edge
                z_next = pts[nxt["start"]][2] + h_flight
                t_meet = t0 + (z_next - z0) / m if m > 1e-9 else t_edge
                if t_a < t_meet < t_edge:
                    pieces.append({"kind": "sloped", "pts": [(t_a, z_at(t_a)), (t_meet, z_next)]})
                    pieces.append({"kind": "level", "pts": [(t_meet, z_next), (t_edge, z_next)]})
                else:
                    pieces.append({"kind": "sloped", "pts": [(t_a, z_at(t_a)), (t_edge, z_at(t_edge))]})
            continue

        # landing: level through its corners, from where the previous rail levelled out
        z = pts[i0][2] + h_level
        t_start = level_start.get(k, t[i0])
        level_pts = [(t_start, z)] + [(t[i], z) for i in range(i0 + 1, i1 + 1)
                                      if t[i] > t_start + 1e-6]
        if len(level_pts) == 1:
            level_pts.append((t[i1], z))
        if pieces and k not in level_start:
            vertical(level_pts[0][0], last_z(), z)
        if level_pts[0][0] >= t[i1] - 1e-6 and len(level_pts) == 2 and level_pts[0] == level_pts[1]:
            continue
        pieces.append({"kind": "level", "pts": level_pts})
    return _clean(pieces)


def _clean(pieces):
    out = []
    for p in pieces:
        pts = []
        for q in p["pts"]:
            if not pts or abs(pts[-1][0] - q[0]) > 1e-9 or abs(pts[-1][1] - q[1]) > 1e-9:
                pts.append(q)
        if len(pts) >= 2:
            out.append({"kind": p["kind"], "pts": pts})
    return out


def z_at(pieces, s):
    """Rail centreline height at plan station s (the lower value at a vertical jump)."""
    best = None
    for p in pieces:
        for (t0, z0), (t1, z1) in zip(p["pts"], p["pts"][1:]):
            if t0 - 1e-6 <= s <= t1 + 1e-6:
                if t1 - t0 < 1e-9:
                    z = min(z0, z1)
                else:
                    u = (s - t0) / (t1 - t0)
                    z = z0 + u * (z1 - z0)
                best = z if best is None else min(best, z)
    if best is None:
        flat = [q for p in pieces for q in p["pts"]]
        return flat[0][1] if s < flat[0][0] else flat[-1][1]
    return best


def z_at_high(pieces, s):
    """Rail centreline height at s, the higher value at a vertical jump."""
    best = None
    for p in pieces:
        for (t0, z0), (t1, z1) in zip(p["pts"], p["pts"][1:]):
            if t0 - 1e-6 <= s <= t1 + 1e-6:
                z = max(z0, z1) if t1 - t0 < 1e-9 else z0 + (s - t0) / (t1 - t0) * (z1 - z0)
                best = z if best is None else max(best, z)
    return z_at(pieces, s) if best is None else best


def breakpoints(pieces):
    return sorted(set(round(q[0], 6) for p in pieces for q in p["pts"]))


def plan_point(path, s, offset):
    """Plan point at station s moved ``offset`` towards the stair (negative = outwards)."""
    q = point_at(path["points"], path["t"], s)
    n = _normal_at(path, s)
    return (q[0] - n[0] * offset, q[1] - n[1] * offset)


def _normal_at(path, s):
    t = path["t"]
    for i in range(len(t) - 1):
        if t[i] - 1e-6 <= s <= t[i + 1] + 1e-6:
            if abs(s - t[i]) < 1e-6:
                return path["outward"][i]
            if abs(s - t[i + 1]) < 1e-6:
                return path["outward"][i + 1]
            d = direction_at(path["points"], t, s)
            sign = 1.0 if dot(path["outward"][i], (-d[1], d[0])) >= 0 else -1.0
            return (-d[1] * sign, d[0] * sign)
    return path["outward"][-1] if s > t[-1] else path["outward"][0]


def to_3d(path, pieces, offset):
    """One polyline (list of (x, y, z)) through all pieces, in the guard plane."""
    poly, kinds = [], []
    for p in pieces:
        for i, (s, z) in enumerate(p["pts"]):
            x, y = plan_point(path, s, offset)
            q = (x, y, z)
            if poly and abs(poly[-1][0] - q[0]) < 1e-6 and abs(poly[-1][1] - q[1]) < 1e-6 and \
                    abs(poly[-1][2] - q[2]) < 1e-6:
                continue
            if poly and i > 0:
                kinds.append(p["kind"])
            elif poly:
                kinds.append(p["kind"])
            poly.append(q)
    return poly, kinds


def length_3d(poly):
    return sum(math.sqrt(sum((b[i] - a[i]) ** 2 for i in range(3))) for a, b in zip(poly, poly[1:]))
