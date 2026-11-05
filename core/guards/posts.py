"""Post stations along a side path and the posts themselves."""
import math

from .path import kinks, point_at, direction_at
from . import rails


def surface_z(path, s):
    """Walking-surface height under plan station s (tread top on flights)."""
    pts, t, segs = path["points"], path["t"], path["segments"]
    if not path["steps"]:
        return point_at(pts, t, s)[2]
    if s > t[-1] - 1e-6:
        return pts[-1][2]                                   # the upper floor
    for seg in segs:                                        # landings and newels first
        if seg["kind"] == "landing" and t[seg["start"]] - 1e-6 <= s <= t[seg["end"]] + 1e-6:
            return pts[seg["start"]][2]
        if seg["kind"] == "winders" and t[seg["end"]] - t[seg["start"]] < 1e-6 and \
                abs(s - t[seg["start"]]) < 1e-6:
            return pts[seg["start"]][2]
    for seg in segs:
        if seg["kind"] in ("flight", "winders") and t[seg["start"]] - 1e-6 <= s < t[seg["end"]] - 1e-6:
            on = sorted([st for st in path["steps"] if st["kind"] in ("step", "winder") and
                         t[seg["start"]] - 1e-6 <= st["t"] <= t[seg["end"]] + 1e-6],
                        key=lambda st: st["t"])
            z = None
            for st in on:
                if st["t"] - 1e-6 <= s:
                    z = st["z"]
            if z is None:                                   # before the first nosing: the floor
                z = (on[0]["z"] - path.get("rise", 0.0)) if on else pts[seg["start"]][2]
            return z
    return pts[0][2] - path.get("rise", 0.0)


def stations(path, p):
    """Sorted list of (station, reason) for the posts of one side."""
    t = path["t"]
    rules = set(p.post_rules) | {"ends", "corners"}
    out = []
    steps = sorted([st for st in path["steps"] if st["kind"] in ("step", "winder")],
                   key=lambda st: st["t"])
    tread_station = {}
    for j, st in enumerate(steps):
        if p.post_on_tread == "centre":
            # half way to the next nosing on this side (or to the end of the flight)
            nxt = steps[j + 1]["t"] if j + 1 < len(steps) and steps[j + 1]["flight"] == st["flight"] \
                else _segment_end(path, st["t"])
            tread_station[st["index"]] = st["t"] + (nxt - st["t"]) / 2.0
        else:
            tread_station[st["index"]] = st["t"] + p.post_tread_offset
    if not path["closed"]:
        if steps and tread_station:
            first = steps[0]
            out.append((tread_station[first["index"]], "end"))
        else:
            out.append((t[0], "end"))
        out.append((t[-1] + (p.post_depth if p.post_shape == "rect" else p.post_size) / 2.0, "end"))
    for i in kinks(path):
        out.append((t[i], "corner"))
    if "every_step" in rules or "every_n_steps" in rules:
        n = p.post_every_n if "every_n_steps" in rules and "every_step" not in rules else 1
        for j, st in enumerate(steps):
            if j % n == 0:
                out.append((tread_station[st["index"]], "step"))
    out = _dedupe(out, p.post_size)
    if "max_spacing" in rules:
        extra = []
        base = [s for s, _ in out]
        if path["closed"] and base:
            base.append(base[0] + t[-1])
        for a, b in zip(base, base[1:]):
            gap = b - a
            if gap > p.post_max_spacing + 1e-6:
                n = int(math.ceil(gap / p.post_max_spacing))
                extra += [((a + gap * k / n) % (t[-1] if path["closed"] else 1e18), "spacing")
                          for k in range(1, n)]
        if path["closed"] and len(base) <= 1:
            n = max(1, int(math.ceil(t[-1] / p.post_max_spacing)))
            extra += [(t[-1] * k / n, "spacing") for k in range(n)]
        out = _dedupe(out + extra, p.post_size)
    if path["closed"] and not out:
        out = [(0.0, "end")]
    return out


def _segment_end(path, s):
    t = path["t"]
    for seg in path["segments"]:
        if seg["kind"] in ("flight", "winders") and t[seg["start"]] - 1e-6 <= s <= t[seg["end"]] + 1e-6:
            return t[seg["end"]]
    return t[-1]


def _dedupe(items, min_gap):
    items = sorted(items, key=lambda x: x[0])
    out = []
    for s, why in items:
        if out and s - out[-1][0] < min_gap - 1e-6:
            if why in ("end", "corner") and out[-1][1] not in ("end", "corner"):
                out[-1] = (s, why)
            continue
        out.append((s, why))
    return out


def build_posts(path, p, top_pieces, h_top_rail, inset):
    posts = []
    t_end = path["t"][-1]
    for n, (s, why) in enumerate(stations(path, p)):
        s_clamped = min(max(s, path["t"][0]), t_end)
        x, y = rails.plan_point(path, s_clamped, inset)
        d = direction_at(path["points"], path["t"], s_clamped)
        if s > t_end:                       # top end post stands on the floor beyond the edge
            x, y = x + d[0] * (s - t_end), y + d[1] * (s - t_end)
        normal = rails._normal_at(path, s_clamped)
        z_surf = surface_z(path, s) if s <= t_end else path["points"][-1][2]
        base_z = z_surf
        plan_shift = 0.0
        if p.post_mount == "fascia":
            base_z -= p.fascia_drop
            plan_shift = p.fascia_offset + p.post_size / 2.0 + inset
        elif p.post_mount == "embedded":
            base_z -= p.embed_depth
        x, y = x + normal[0] * plan_shift, y + normal[1] * plan_shift
        z_rail = rails.z_at(top_pieces, s_clamped)
        top_z = z_rail - h_top_rail / 2.0 - p.top_rail_gap
        posts.append({"index": n, "station": s, "reason": why, "base": (x, y, base_z),
                      "top": (x, y, top_z), "height": top_z - base_z,
                      "direction": d, "rotation_deg": math.degrees(math.atan2(d[1], d[0])) + p.post_rotation,
                      "profile": post_profile(p), "mount": p.post_mount, "surface_z": z_surf})
    return posts


def post_profile(p):
    if p.post_shape == "custom":
        return {"shape": "custom", "points": [tuple(q) for q in p.post_custom_profile]}
    if p.post_shape == "round":
        return {"shape": "round", "d": p.post_size}
    if p.post_shape == "rect":
        return {"shape": "rect", "w": p.post_size, "d": p.post_depth}
    return {"shape": "rect", "w": p.post_size, "d": p.post_size}
