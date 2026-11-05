"""Infill between consecutive posts: balusters, horizontal bars, cable, glass, mesh."""
import math

from . import rails


def bays(posts, path):
    """(t_a, t_b) between consecutive posts, measured between the post faces."""
    out = []
    size = posts[0]["profile"].get("d") or posts[0]["profile"].get("w") if posts else 0.0
    half = (size or 0.0) / 2.0
    stations = [q["station"] for q in posts]
    if path["closed"] and len(stations) >= 2:
        stations = stations + [stations[0] + path["t"][-1]]
    for a, b in zip(stations, stations[1:]):
        a, b = a + half, b - half
        if b - a > 1e-6:
            out.append((a, b))
    return out


def _bottom_z(path, p, bottom_pieces, s):
    """Top of the bottom rail, or the surface / nosing line when there is no bottom rail."""
    if bottom_pieces:
        return rails.z_at(bottom_pieces, s) + p.bottom_rail_h / 2.0
    return rails.z_at(path["_ref"], s)


def _top_z(p, top_pieces, s):
    return rails.z_at(top_pieces, s) - p.top_rail_h / 2.0


def _count_by_spacing(length, size, spacing):
    """Fewest members of ``size`` in ``length`` so the clear gap is <= spacing."""
    if length <= spacing:
        return 0
    return int(math.ceil((length - spacing) / (size + spacing) - 1e-9))


def build_infill(path, p, posts, top_pieces, bottom_pieces, inset, steps_in):
    res = {"balusters": [], "bars": [], "cables": [], "panels": [], "frames": [], "clamps": [],
           "max_clear": 0.0, "bay_count": 0}
    if p.infill == "none" or len(posts) < 2:
        return res
    t_max = path["t"][-1]
    for (a, b) in bays(posts, path):
        res["bay_count"] += 1
        L = b - a
        if p.infill == "balusters":
            if p.balusters_per_tread > 0 and steps_in:
                n_treads = len([st for st in steps_in if a - 1e-6 <= st["t"] + st["run"] / 2 <= b + 1e-6])
                n = max(p.balusters_per_tread * max(n_treads, 1), 1)
            else:
                n = _count_by_spacing(L, p.baluster_size, p.baluster_spacing)
            clear = (L - n * p.baluster_size) / (n + 1)
            res["max_clear"] = max(res["max_clear"], clear)
            for j in range(n):
                s = a + clear * (j + 1) + p.baluster_size * (j + 0.5)
                sc = min(s, t_max)
                x, y = rails.plan_point(path, sc, inset)
                z0 = _bottom_z(path, p, bottom_pieces, sc)
                z1 = _top_z(p, top_pieces, sc)
                res["balusters"].append({"bottom": (x, y, z0), "top": (x, y, z1), "station": s,
                                         "profile": {"shape": p.baluster_shape, "size": p.baluster_size}})
        elif p.infill in ("horizontal", "cable"):
            size = p.bar_size if p.infill == "horizontal" else p.cable_diameter
            spacing = p.bar_spacing if p.infill == "horizontal" else p.cable_spacing
            sa, sb = min(a, t_max), min(b, t_max)
            H = min(_top_z(p, top_pieces, sa) - _bottom_z(path, p, bottom_pieces, sa),
                    _top_z(p, top_pieces, sb) - _bottom_z(path, p, bottom_pieces, sb))
            n = p.bar_count if (p.infill == "horizontal" and p.bar_count > 0) else \
                _count_by_spacing(H, size, spacing)
            clear = (H - n * size) / (n + 1) if n >= 0 else H
            res["max_clear"] = max(res["max_clear"], clear)
            brk = [s for s in rails.breakpoints(top_pieces) + rails.breakpoints(bottom_pieces or [])
                   if sa < s < sb]
            sts = sorted(set([sa] + brk + [sb]))
            for j in range(n):
                frac = (clear * (j + 1) + size * (j + 0.5))
                poly = []
                for s in sts:
                    zb, zt = _bottom_z(path, p, bottom_pieces, s), _top_z(p, top_pieces, s)
                    h = zt - zb
                    z = zb + (frac / H * h if H > 1e-9 else 0.0)
                    x, y = rails.plan_point(path, s, inset)
                    poly.append((x, y, z))
                key = "bars" if p.infill == "horizontal" else "cables"
                res[key].append({"polyline": poly, "profile": {"shape": "round" if key == "cables"
                                                                  else "rect", "size": size},
                                 "height_above_surface": frac})
        elif p.infill in ("glass", "mesh"):
            gap = p.glass_gap if p.infill == "glass" else p.mesh_frame / 2.0
            sa, sb = a + gap, b - gap
            if sb - sa < 1e-6:
                continue
            brk = [s for s in rails.breakpoints(top_pieces) + rails.breakpoints(bottom_pieces or [])
                   if sa < s < sb]
            sts = sorted(set([sa] + brk + [sb]))
            bottom, top = [], []
            for s in sts:
                sc = min(s, t_max)
                x, y = rails.plan_point(path, sc, inset)
                if p.infill == "glass":
                    zb = (rails.z_at(path["_ref"], sc) + p.glass_bottom_gap) if not bottom_pieces else \
                        _bottom_z(path, p, bottom_pieces, sc) + gap
                else:
                    zb = _bottom_z(path, p, bottom_pieces, sc) + gap
                zt = _top_z(p, top_pieces, sc) - gap
                bottom.append((x, y, zb))
                top.append((x, y, zt))
            polygon = bottom + list(reversed(top))
            thk = p.glass_thk if p.infill == "glass" else p.mesh_panel_thk
            area = _area_in_plane(polygon)
            panel = {"polygon": polygon, "thickness": thk, "kind": p.infill, "area_m2": area / 1e6,
                     "bay": (a, b)}
            res["panels"].append(panel)
            if p.infill == "glass":
                n_cl = max(2, int(math.ceil((sb - sa) / p.clamp_spacing)) + 1)
                for j in range(n_cl):
                    s = sa + (sb - sa) * j / (n_cl - 1)
                    sc = min(s, t_max)
                    x, y = rails.plan_point(path, sc, inset)
                    res["clamps"].append((x, y, bottom[0][2] if j == 0 else
                                          _interp_z(bottom, j / (n_cl - 1))))
            else:
                res["frames"].append({"polyline": polygon + [polygon[0]], "size": p.mesh_frame})
            res["max_clear"] = max(res["max_clear"], gap * 2 if p.infill == "glass" else p.mesh_frame)
    return res


def _interp_z(pts, u):
    return pts[0][2] + (pts[-1][2] - pts[0][2]) * u


def _area_in_plane(poly):
    """Area of a (nearly) planar vertical polygon: use (plan length, z) coordinates."""
    s = [0.0]
    for a, b in zip(poly, poly[1:]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    # unfold: station along the polygon edges is not monotonic for the top edge, so use
    # a 2D projection onto the plane direction of the first edge
    if len(poly) < 3:
        return 0.0
    d = (poly[-1][0] - poly[0][0], poly[-1][1] - poly[0][1])
    L = math.hypot(*d)
    if L < 1e-9:
        d = (poly[1][0] - poly[0][0], poly[1][1] - poly[0][1])
        L = math.hypot(*d) or 1.0
    u = (d[0] / L, d[1] / L)
    pts2 = [((q[0] - poly[0][0]) * u[0] + (q[1] - poly[0][1]) * u[1], q[2]) for q in poly]
    area = 0.0
    for (x0, y0), (x1, y1) in zip(pts2, pts2[1:] + pts2[:1]):
        area += x0 * y1 - x1 * y0
    return abs(area) / 2.0
