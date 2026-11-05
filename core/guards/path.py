"""Turn the input (stair guard_path or curves) into side paths with a plan station t.

A side path:
    points   [(x, y, z)]   reference line: nosing line on flights, surface edge on landings,
                           the curve itself in curve mode
    t        [float]       cumulative plan (x, y) length at each point
    segments [{kind, start, end, slope, z}]   kind: flight | landing | winders | curve
    outward  [(nx, ny)]    unit plan normal pointing away from the stair (falling side)
    steps    [{t, z, kind, index, run}]   walking surfaces along this side (posts on treads)
    closed   bool
"""
import math

from ..geom import sub, dot, rot90, unit, length, dedupe


def plan_stations(points):
    t = [0.0]
    for a, b in zip(points, points[1:]):
        t.append(t[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return t


def outward_normals(points, side, closed=False):
    """Plan normals pointing away from the stair: left side -> +left of travel.

    A closed path repeats its first point at the end; both copies get the mitre normal."""
    sign = 1.0 if side == "left" else -1.0
    dirs = []
    n = len(points)
    for i in range(n):
        if closed and n > 2:
            a = points[i - 1] if i > 0 else points[n - 2]
            b = points[i + 1] if i < n - 1 else points[1]
        else:
            a = points[max(i - 1, 0)]
            b = points[min(i + 1, n - 1)]
        d = (b[0] - a[0], b[1] - a[1])
        if length(d) < 1e-9:
            d = dirs[-1] if dirs else (1.0, 0.0)
        dirs.append(unit(d))
    return [(rot90(d)[0] * sign, rot90(d)[1] * sign) for d in dirs]


def station_of(points, t, q, min_t=0.0):
    """Plan station of the closest point on the polyline to q (x, y), at or after min_t.

    ``min_t`` keeps the search monotonic along the path, which matters where a path
    overlaps itself in plan (a U stair with no well gap, a spiral's inner side)."""
    best = (None, 0.0)
    for i in range(len(points) - 1):
        if t[i + 1] < min_t - 1e-6:
            continue
        a, b = points[i], points[i + 1]
        e = (b[0] - a[0], b[1] - a[1])
        ll = e[0] ** 2 + e[1] ** 2
        if ll < 1e-12:
            continue
        u = ((q[0] - a[0]) * e[0] + (q[1] - a[1]) * e[1]) / ll
        u = max(0.0, min(1.0, u))
        s_here = t[i] + u * (t[i + 1] - t[i])
        if s_here < min_t - 1e-6:
            u = (min_t - t[i]) / (t[i + 1] - t[i]) if t[i + 1] > t[i] else 1.0
            u = max(0.0, min(1.0, u))
            s_here = t[i] + u * (t[i + 1] - t[i])
        px, py = a[0] + u * e[0], a[1] + u * e[1]
        d = math.hypot(px - q[0], py - q[1])
        if best[0] is None or d < best[0] - 1e-9:
            best = (d, s_here)
    return best[1]


def point_at(points, t, s):
    """3D point on the polyline at plan station s (clamped)."""
    if s <= t[0]:
        return points[0]
    for i in range(len(t) - 1):
        if t[i] <= s <= t[i + 1]:
            span = t[i + 1] - t[i]
            u = 0.0 if span < 1e-12 else (s - t[i]) / span
            a, b = points[i], points[i + 1]
            return (a[0] + u * (b[0] - a[0]), a[1] + u * (b[1] - a[1]), a[2] + u * (b[2] - a[2]))
    return points[-1]


def direction_at(points, t, s):
    for i in range(len(t) - 1):
        if t[i] <= s <= t[i + 1] and t[i + 1] - t[i] > 1e-9:
            return unit((points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]))
    for i in range(len(t) - 2, -1, -1):
        if t[i + 1] - t[i] > 1e-9:
            return unit((points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1]))
    return (1.0, 0.0)


def _segment_slope(points, t, seg):
    """Rise per plan mm of a flight segment, measured along this side's nosing points.

    The last point of a flight is the landing / floor edge and the first point of a flight
    that leaves a landing is the exit edge, so both are left out when there are enough
    nosings. On a straight flight this is exactly rise / run; on a spiral it differs
    between the inner and the outer side."""
    i0, i1 = seg["start"], seg["end"]
    j1 = i1 - 1 if i1 - i0 >= 2 else i1
    j0 = i0 + 1 if j1 - i0 >= 2 else i0
    dt = t[j1] - t[j0]
    if dt < 1e-9:
        j0, dt = i0, t[j1] - t[i0]
    if dt < 1e-9:
        return 0.0
    return (points[j1][2] - points[j0][2]) / dt


def side_paths_from_stair(gp, sides):
    out = []
    wanted = ("left", "right") if sides == "both" else (sides,)
    for side in wanted:
        data = gp["sides"][side]
        pts = [tuple(q) for q in data["polyline"]]
        t = plan_stations(pts)
        segs = []
        for s in data["segments"]:
            seg = {"kind": s["kind"], "start": s["start"], "end": s["end"], "flight": s["flight"]}
            if s["kind"] in ("flight", "winders"):
                seg["slope"] = _segment_slope(pts, t, seg)
            else:
                seg["z"] = pts[s["start"]][2]
            segs.append(seg)
        # vertical newel pair on the inner side of winders: zero plan length, keep as 'winders'
        steps = []
        key = "nosing_left" if side == "left" else "nosing_right"
        last_t = 0.0
        for st in gp["steps"]:
            q = st[key]
            s_t = station_of(pts, t, q, last_t)
            last_t = s_t
            steps.append({"t": s_t, "z": st["z"] if "z" in st else q[2], "kind": st["kind"],
                          "index": st["index"], "flight": st.get("flight", 0),
                          "run": st.get("run", 0.0), "rise": st.get("rise", 0.0),
                          "direction": tuple(st["direction"])})
        out.append({"side": side, "points": pts, "t": t, "segments": segs, "closed": False,
                    "outward": outward_normals(pts, side), "steps": steps,
                    "rise": gp.get("rise") or 0.0})
    return out


def side_paths_from_curves(curves, closed_flags, outward):
    out = []
    for k, curve in enumerate(curves):
        pts = dedupe([tuple(q) + ((0.0,) if len(q) == 2 else ()) for q in curve])
        if len(pts) < 2:
            continue
        closed = bool(closed_flags[k]) if closed_flags and k < len(closed_flags) else False
        if closed and length(sub(pts[0][:2], pts[-1][:2])) > 1e-6:
            pts.append(pts[0])
        t = plan_stations(pts)
        side = "left" if outward == "left" else "right"
        out.append({"side": "curve{}".format(k), "points": pts, "t": t,
                    "segments": [{"kind": "curve", "start": 0, "end": len(pts) - 1}],
                    "closed": closed, "outward": outward_normals(pts, side, closed),
                    "steps": [], "rise": 0.0})
    return out


def kinks(path, min_angle_deg=15.0):
    """Indices of points where the plan direction changes by more than min_angle_deg.

    Zero-length plan edges (vertical jumps) are looked through. In stair mode the bends
    of a flight / winder / spiral nosing polyline are not corners: only points that touch a
    landing segment count (landing corners and the newel / junction points).
    """
    pts = path["points"]
    n = len(pts)
    stair = any(s["kind"] in ("flight", "winders") for s in path["segments"])
    on_landing = set()
    for s in path["segments"]:
        if s["kind"] == "landing":
            on_landing.update(range(s["start"], s["end"] + 1))
        elif s["kind"] == "winders" and path["t"][s["end"]] - path["t"][s["start"]] < 1e-6:
            on_landing.update(range(s["start"], s["end"] + 1))      # the newel

    def plan_dir(i, step):
        j = i
        while 0 <= j + step < n:
            a, b = pts[j], pts[j + step]
            d = (b[0] - a[0], b[1] - a[1]) if step > 0 else (a[0] - b[0], a[1] - b[1])
            if length(d) > 1e-9:
                return unit(d)
            j += step
        if path["closed"]:
            return plan_dir(1 if step > 0 else n - 2, step) if j != i else None
        return None

    out = []
    rng = range(0, n - 1) if path["closed"] else range(1, n - 1)
    for i in rng:
        if stair and i not in on_landing:
            continue
        d1 = plan_dir(i, -1) if (i > 0 or path["closed"]) else None
        d2 = plan_dir(i, +1)
        if d1 is None or d2 is None:
            continue
        cosang = max(-1.0, min(1.0, dot(d1, d2)))
        if math.degrees(math.acos(cosang)) > min_angle_deg:
            if not out or abs(path["t"][i] - path["t"][out[-1]]) > 1e-6:
                out.append(i)
    return out
