"""A tiny stand-in for the parts of RhinoCommon / Grasshopper the adapters use.

Only for tests outside Rhino. Transform is a real 4x4 matrix so placement maths is checked.
Install with ``install(monkeypatch, doc)``.
"""
import math
import sys
import types


class Point3d(object):
    def __init__(self, x=0.0, y=0.0, z=0.0):
        if isinstance(x, (Point3d, Vector3d)):
            x, y, z = x.X, x.Y, x.Z
        elif isinstance(x, (tuple, list)):
            x, y, z = (list(x) + [0.0, 0.0])[:3]
        self.X, self.Y, self.Z = float(x), float(y), float(z)

    def Transform(self, xf):
        self.X, self.Y, self.Z = xf.apply((self.X, self.Y, self.Z), 1.0)

    def DistanceTo(self, o):
        return math.sqrt((self.X - o.X) ** 2 + (self.Y - o.Y) ** 2 + (self.Z - o.Z) ** 2)

    def __repr__(self):
        return "Point3d({:.3f}, {:.3f}, {:.3f})".format(self.X, self.Y, self.Z)


class Vector3d(object):
    def __init__(self, x=0.0, y=0.0, z=0.0):
        if isinstance(x, (Point3d, Vector3d)):
            x, y, z = x.X, x.Y, x.Z
        self.X, self.Y, self.Z = float(x), float(y), float(z)

    def Transform(self, xf):
        self.X, self.Y, self.Z = xf.apply((self.X, self.Y, self.Z), 0.0)

    def Unitize(self):
        n = math.sqrt(self.X ** 2 + self.Y ** 2 + self.Z ** 2)
        if n > 0:
            self.X, self.Y, self.Z = self.X / n, self.Y / n, self.Z / n
        return n > 0

    def __mul__(self, s):
        return Vector3d(self.X * s, self.Y * s, self.Z * s)

    @property
    def Length(self):
        return math.sqrt(self.X ** 2 + self.Y ** 2 + self.Z ** 2)


Point3d.Origin = Point3d(0, 0, 0)
Vector3d.ZAxis = Vector3d(0, 0, 1)


class Transform(object):
    def __init__(self, m=None):
        self.m = m or [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]

    @staticmethod
    def Scale(origin, s):
        return Transform([[s, 0, 0, 0], [0, s, 0, 0], [0, 0, s, 0], [0, 0, 0, 1]])

    @staticmethod
    def Rotation(angle, axis, centre):
        c, s = math.cos(angle), math.sin(angle)
        return Transform([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])

    @staticmethod
    def Translation(x, y=None, z=None):
        if isinstance(x, Vector3d):
            x, y, z = x.X, x.Y, x.Z
        return Transform([[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]])

    def __mul__(self, o):
        a, b = self.m, o.m
        return Transform([[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
                          for i in range(4)])

    def apply(self, p, w):
        v = (p[0], p[1], p[2], w)
        return tuple(sum(self.m[i][k] * v[k] for k in range(4)) for i in range(3))

    def TryGetInverse(self):
        m = self.m
        a = [[m[i][j] for j in range(3)] for i in range(3)]
        det = (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
               - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
               + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))
        if abs(det) < 1e-15:
            return False, Transform()
        inv = [[0.0] * 3 for _ in range(3)]
        for i in range(3):
            for j in range(3):
                minor = [[a[r][c] for c in range(3) if c != i] for r in range(3) if r != j]
                cof = minor[0][0] * minor[1][1] - minor[0][1] * minor[1][0]
                inv[i][j] = ((-1) ** (i + j)) * cof / det
        t = [m[0][3], m[1][3], m[2][3]]
        it = [-sum(inv[i][k] * t[k] for k in range(3)) for i in range(3)]
        return True, Transform([inv[0] + [it[0]], inv[1] + [it[1]], inv[2] + [it[2]], [0, 0, 0, 1]])


class PolylineCurve(object):
    def __init__(self, pts):
        self.pts = [Point3d(p) for p in pts]

    @property
    def PointCount(self):
        return len(self.pts)

    def Point(self, i):
        return self.pts[i]

    def ToPolyline(self, tol, ang, mn, mx):
        return self

    def ToNurbsCurve(self):
        return self


Curve = PolylineCurve


class Brep(object):
    def __init__(self, curve, vector=None):
        self.curve, self.vector = curve, vector

    def CapPlanarHoles(self, tol):
        return self

    @staticmethod
    def CreatePlanarBreps(curve, tol):
        return [Brep(curve)]

    @property
    def points(self):
        return self.curve.pts


class _Surface(object):
    def __init__(self, curve, vector):
        self.curve, self.vector = curve, vector

    def ToBrep(self):
        return Brep(self.curve, self.vector)


class Surface(object):
    @staticmethod
    def CreateExtrusion(curve, vector):
        return _Surface(curve, vector)


UNITS = {"Millimeters": 1.0, "Centimeters": 10.0, "Meters": 1000.0, "Inches": 25.4}


class Doc(object):
    def __init__(self, units="Millimeters", tol=0.01, path=None):
        self.ModelUnitSystem = "UnitSystem." + units
        self.ModelAbsoluteTolerance = tol
        self.Path = path


def install(monkeypatch, doc):
    rhino = types.ModuleType("Rhino")
    geom = types.ModuleType("Rhino.Geometry")
    for cls in (Point3d, Vector3d, Transform, PolylineCurve, Curve, Brep, Surface):
        setattr(geom, cls.__name__, cls)
    geom.Curve = PolylineCurve
    rhino.Geometry = geom
    rhino.RhinoDoc = types.SimpleNamespace(ActiveDoc=doc)
    rhino.UnitSystem = types.SimpleNamespace(Millimeters="UnitSystem.Millimeters")
    rhino.RhinoMath = types.SimpleNamespace(
        UnitScale=lambda a, b: UNITS[a.split(".")[-1]] / UNITS[b.split(".")[-1]])
    gh = types.ModuleType("Grasshopper")
    kernel = types.ModuleType("Grasshopper.Kernel")
    kernel.GH_RuntimeMessageLevel = types.SimpleNamespace(Error="Error", Warning="Warning",
                                                          Remark="Remark")
    gh.Kernel = kernel
    for name, mod in (("Rhino", rhino), ("Rhino.Geometry", geom), ("Grasshopper", gh),
                      ("Grasshopper.Kernel", kernel)):
        monkeypatch.setitem(sys.modules, name, mod)
    for name in [n for n in sys.modules if n.split(".")[0] in ("adapters",)]:
        monkeypatch.delitem(sys.modules, name)
    return rhino
