"""Build a guard / railing as plain data from a stair guard_path or from curves."""
import math

from ..limits import load_limits
from .params import GuardParams
from .path import side_paths_from_stair, side_paths_from_curves, direction_at
from . import rails
from .posts import build_posts
from .infill import build_infill
from .checks import run_checks
from .bom import build_bom


def _rail_profile(shape, w, h, custom=None):
    if shape == "round":
        return {"shape": "round", "d": h}
    if shape == "custom":
        return {"shape": "custom", "points": [tuple(q) for q in custom]}
    return {"shape": "rect", "w": w, "h": h}


def build_guard(params, limits=None):
    p = params if isinstance(params, GuardParams) else GuardParams(**params)
    p.validate()
    limits = limits or load_limits("guards", overrides=p.rules)
    h_key = "guard_height_residential_mm" if p.context == "residential" else "guard_height_other_mm"
    h_f = float(p.height_flight) if p.height_flight else float(limits.value(h_key))
    h_l = float(p.height_landing) if p.height_landing else float(limits.value(h_key))
    hr = float(p.handrail_height) if p.handrail_height else \
        (limits.value("handrail_height_min_mm") + limits.value("handrail_height_max_mm")) / 2.0
    inset = float(p.inset) if p.inset is not None else p.post_size / 2.0

    if p.mode == "stair":
        paths = side_paths_from_stair(p.guard_path, p.sides)
    else:
        paths = side_paths_from_curves(p.curves, p.curves_closed, p.curve_outward)
    paths = [q for q in paths if q["t"][-1] > p.post_size]
    if not paths:
        raise ValueError("no usable path for the guard: the path needs a plan length larger "
                         "than the post size (a stair with no treads has no guard)")

    sides_out = []
    for path in paths:
        path["_ref"] = rails.profile(path, 0.0, 0.0, p.transition)
        top_pieces = rails.profile(path, h_f - p.top_rail_h / 2.0, h_l - p.top_rail_h / 2.0,
                                   p.transition)
        bottom_pieces = rails.profile(path, p.bottom_gap + p.bottom_rail_h / 2.0,
                                      p.bottom_gap + p.bottom_rail_h / 2.0, p.transition) \
            if p.bottom_rail else None
        posts = build_posts(path, p, top_pieces, p.top_rail_h, inset)
        steps_in = [st for st in path["steps"] if st["kind"] in ("step", "winder")]
        infill = build_infill(path, p, posts, top_pieces, bottom_pieces, inset, steps_in)
        top_poly, top_kinds = rails.to_3d(path, top_pieces, inset)
        side = {
            "side": path["side"], "posts": posts, "infill": infill,
            "top_rail": {"side": path["side"], "polyline": top_poly, "kinds": top_kinds,
                         "profile": _rail_profile(p.top_rail_shape, p.top_rail_w, p.top_rail_h,
                                                  p.top_rail_custom_profile)},
            "bottom_rail": None, "handrail": None, "brackets": [],
            "flights": _flights_meta(path), "has_level": any(s["kind"] in ("landing", "curve")
                                                            for s in path["segments"]),
            "length": path["t"][-1],
        }
        if bottom_pieces:
            poly, kinds = rails.to_3d(path, bottom_pieces, inset)
            side["bottom_rail"] = {"side": path["side"], "polyline": poly, "kinds": kinds,
                                   "profile": _rail_profile(p.bottom_rail_shape, p.bottom_rail_w,
                                                            p.bottom_rail_h)}
        if p.handrail and _handrail_on(p, path["side"]):
            side["handrail"], side["brackets"] = _handrail(path, p, hr)
        sides_out.append(side)

    info = {
        "mode": p.mode, "sides": [s["side"] for s in sides_out],
        "height_flight": h_f, "height_landing": h_l, "handrail_height": hr, "inset": inset,
        "post_count": sum(len(s["posts"]) for s in sides_out),
        "posts_per_side": {s["side"]: len(s["posts"]) for s in sides_out},
        "max_post_spacing": max([_max_spacing(s["posts"]) for s in sides_out] + [0.0]),
        "top_rail_length": sum(rails.length_3d(s["top_rail"]["polyline"]) for s in sides_out),
        "bottom_rail_length": sum(rails.length_3d(s["bottom_rail"]["polyline"])
                                  for s in sides_out if s["bottom_rail"]),
        "handrail_length": sum(rails.length_3d(s["handrail"]["polyline"])
                               for s in sides_out if s["handrail"]),
        "baluster_count": sum(len(s["infill"]["balusters"]) for s in sides_out),
        "panel_count": sum(len(s["infill"]["panels"]) for s in sides_out),
        "glass_area_m2": sum(q["area_m2"] for s in sides_out for q in s["infill"]["panels"]),
        "max_infill_clear": max([s["infill"]["max_clear"] for s in sides_out] + [0.0]),
        "bay_count": sum(s["infill"]["bay_count"] for s in sides_out),
        "transition": p.transition, "infill": p.infill, "units": "mm",
    }
    warnings, idx = run_checks(p, limits, sides_out, info)
    return {
        "posts": [q for s in sides_out for q in s["posts"]],
        "top_rail": [s["top_rail"] for s in sides_out],
        "bottom_rail": [s["bottom_rail"] for s in sides_out if s["bottom_rail"]],
        "handrail": [s["handrail"] for s in sides_out if s["handrail"]],
        "brackets": [b for s in sides_out for b in s["brackets"]],
        "infill": {key: [q for s in sides_out for q in s["infill"][key]]
                   for key in ("balusters", "bars", "cables", "panels", "frames", "clamps")},
        "sides": sides_out, "info": info, "warnings": warnings, "warning_index": idx,
        "bom": build_bom(p, sides_out),
    }


def _handrail_on(p, side):
    if p.handrail_sides == "same":
        return True
    if p.handrail_sides == "both":
        return True
    return side == p.handrail_sides


def _handrail(path, p, hr):
    h = p.handrail_h if p.handrail_shape == "rect" else p.handrail_size
    pieces = rails.profile(path, hr - h / 2.0, hr - h / 2.0, p.transition)
    poly, kinds = rails.to_3d(path, pieces, p.handrail_offset)
    t = path["t"]
    ret = p.handrail_return_length if p.handrail_return_length is not None else p.handrail_offset
    if not path["closed"]:
        if p.handrail_ext_bottom > 0:
            d = direction_at(path["points"], t, t[0])
            start = poly[0]
            ext = (start[0] - d[0] * p.handrail_ext_bottom, start[1] - d[1] * p.handrail_ext_bottom, start[2])
            poly, kinds = [ext] + poly, ["level"] + kinds
            if p.handrail_returns and ret > 0:
                n = rails._normal_at(path, t[0])
                poly = [(ext[0] + n[0] * ret, ext[1] + n[1] * ret, ext[2])] + poly
                kinds = ["return"] + kinds
        if p.handrail_ext_top > 0:
            d = direction_at(path["points"], t, t[-1])
            end = poly[-1]
            ext = (end[0] + d[0] * p.handrail_ext_top, end[1] + d[1] * p.handrail_ext_top, end[2])
            poly, kinds = poly + [ext], kinds + ["level"]
            if p.handrail_returns and ret > 0:
                n = rails._normal_at(path, t[-1])
                poly = poly + [(ext[0] + n[0] * ret, ext[1] + n[1] * ret, ext[2])]
                kinds = kinds + ["return"]
    brackets = []
    total = rails.length_3d(poly)
    n_br = max(2, int(math.ceil(total / p.bracket_spacing)) + 1)
    for j in range(n_br):
        q = _point_along(poly, total * j / (n_br - 1))
        s = min(max(_station_guess(path, q), t[0]), t[-1])
        n = rails._normal_at(path, s)
        brackets.append({"point": q, "direction": (n[0], n[1], 0.0), "offset": p.handrail_offset})
    profile = _rail_profile(p.handrail_shape, p.handrail_size, h)
    return {"side": path["side"], "polyline": poly, "kinds": kinds, "profile": profile,
            "height": hr, "offset": p.handrail_offset}, brackets


def _station_guess(path, q):
    from .path import station_of
    return station_of(path["points"], path["t"], q)


def _point_along(poly, dist):
    acc = 0.0
    for a, b in zip(poly, poly[1:]):
        seg = math.sqrt(sum((b[i] - a[i]) ** 2 for i in range(3)))
        if acc + seg >= dist - 1e-9 and seg > 0:
            u = (dist - acc) / seg
            return tuple(a[i] + u * (b[i] - a[i]) for i in range(3))
        acc += seg
    return poly[-1]


def _flights_meta(path):
    out = []
    t = path["t"]
    for seg in path["segments"]:
        if seg["kind"] not in ("flight", "winders") or t[seg["end"]] - t[seg["start"]] < 1e-6:
            continue
        steps = [st for st in path["steps"] if st["kind"] in ("step", "winder") and
                 t[seg["start"]] - 1e-6 <= st["t"] <= t[seg["end"]] + 1e-6 and st["run"] > 0]
        rise = next((st["rise"] for st in steps if st.get("rise", 0) > 0), 0.0)
        run = steps[0]["run"] if steps else 0.0
        slope = rails._flight_slope(path, seg)
        out.append({"flight": seg.get("flight", 0), "slope": slope, "rise": rise, "run": run,
                    "first_step": steps[0]["index"] if steps else -1})
    return out


def _max_spacing(posts):
    s = sorted(q["station"] for q in posts)
    return max([b - a for a, b in zip(s, s[1:])] + [0.0])
