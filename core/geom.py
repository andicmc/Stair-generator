"""Small vector helpers. Points are tuples (x, y) or (x, y, z); mm; Z up. No Rhino."""
import math

EPS = 1e-9


def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, s):
    return tuple(x * s for x in a)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def length(a):
    return math.sqrt(dot(a, a))


def dist(a, b):
    return length(sub(a, b))


def unit(a):
    n = length(a)
    if n < EPS:
        raise ValueError("zero-length vector")
    return mul(a, 1.0 / n)


def rot90(v):
    """Rotate a 2D vector +90 degrees (counter-clockwise, seen from above)."""
    return (-v[1], v[0])


def rotate(v, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def angle_of(v):
    """Angle of a 2D vector in degrees, counter-clockwise from +X."""
    return math.degrees(math.atan2(v[1], v[0]))


def to3(p, z):
    return (p[0], p[1], z)


def xy(p):
    return (p[0], p[1])


def midpoint(a, b):
    return tuple((x + y) / 2.0 for x, y in zip(a, b))


def centroid(points):
    n = float(len(points))
    return tuple(sum(c) / n for c in zip(*points))


def signed_area(poly):
    """Signed area of a polygon from its x, y (positive = counter-clockwise)."""
    a = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i][0], poly[i][1]
        x1, y1 = poly[(i + 1) % len(poly)][0], poly[(i + 1) % len(poly)][1]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def polygon_area(poly):
    return abs(signed_area(poly))


def point_in_polygon(pt, poly):
    """Ray casting on x, y. Points on an edge count as inside (within EPS)."""
    x, y = pt[0], pt[1]
    inside = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i][0], poly[i][1]
        x1, y1 = poly[(i + 1) % n][0], poly[(i + 1) % n][1]
        # on the edge?
        ex, ey = x1 - x0, y1 - y0
        seg = ex * ex + ey * ey
        if seg > EPS:
            t = ((x - x0) * ex + (y - y0) * ey) / seg
            if -EPS <= t <= 1 + EPS:
                px, py = x0 + t * ex, y0 + t * ey
                if abs(px - x) < 1e-6 and abs(py - y) < 1e-6:
                    return True
        if (y0 > y) != (y1 > y):
            xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xi:
                inside = not inside
    return inside


def ray_hit_polyline(origin, direction, polyline):
    """First hit of a 2D ray on an open polyline: (point, segment_index, t) or None."""
    best = None
    ox, oy = origin[0], origin[1]
    dx, dy = direction[0], direction[1]
    for i in range(len(polyline) - 1):
        ax, ay = polyline[i][0], polyline[i][1]
        bx, by = polyline[i + 1][0], polyline[i + 1][1]
        ex, ey = bx - ax, by - ay
        den = dx * ey - dy * ex
        if abs(den) < EPS:
            continue
        t = ((ax - ox) * ey - (ay - oy) * ex) / den     # along the ray
        u = ((ax - ox) * dy - (ay - oy) * dx) / den     # along the segment
        if t > 1e-7 and -1e-7 <= u <= 1 + 1e-7:
            if best is None or t < best[2]:
                best = ((ox + t * dx, oy + t * dy), i, t)
    return best


def dedupe(points, tol=1e-6):
    """Drop consecutive duplicate points."""
    out = []
    for p in points:
        if not out or dist(out[-1], p) > tol:
            out.append(p)
    return out


def polyline_length(points):
    return sum(dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] if len(p) > 2 else 0.0 for p in points]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))
