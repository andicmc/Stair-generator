"""Assemble the ``guard_path`` contract (docs/guard_path.md) from the build."""
from ..geom import dist


def assemble_guard_path(b, p):
    sides = {}
    for side in ("left", "right"):
        polyline, segments, breaks = [], [], []
        for kind, flight, pts in b.guard[side]:
            pts = list(pts)
            if polyline and pts and dist(polyline[-1], pts[0]) < 1e-6:
                start = len(polyline) - 1          # touches the previous segment: share the point
                pts = pts[1:]
            else:
                start = len(polyline)
            # drop duplicates inside the segment
            for q in pts:
                if not polyline or dist(polyline[-1], q) > 1e-6:
                    polyline.append(q)
            end = len(polyline) - 1
            if segments and segments[-1]["kind"] != kind:
                breaks.append(start)
            segments.append({"kind": kind, "flight": flight, "start": start, "end": end})
        sides[side] = {"polyline": polyline, "segments": segments, "breaks": breaks,
                       "length": _length(polyline)}
    return {"version": 1, "units": "mm", "stair_type": p.stair_type, "turn": p.turn,
            "width": p.width, "rise": b.flights_meta[0]["rise"] if b.flights_meta else None,
            "sides": sides, "steps": [dict(s) for s in b.steps]}


def _length(pts):
    return sum(dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
