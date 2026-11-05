"""Guard adapter (fake RhinoCommon) and the guard GH component end to end."""
import json
import os
import sys
import types

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))

import fake_rhino  # noqa: E402
from core.stairs import StairParams, build_stair  # noqa: E402
from core.guards import GuardParams, build_guard  # noqa: E402

SCRIPT = os.path.join(ROOT, "grasshopper", "guard_component.py")
SOURCE = open(SCRIPT, encoding="utf-8").read()
STAIR_SCRIPT = os.path.join(ROOT, "grasshopper", "stair_component_v2.py")
STAIR_SOURCE = open(STAIR_SCRIPT, encoding="utf-8").read()


@pytest.fixture
def rhino(monkeypatch):
    return fake_rhino.install(monkeypatch, fake_rhino.Doc())


def test_adapter_builds_every_part(rhino):
    from adapters import guards_rhino as ad
    st = build_stair(StairParams(stair_type="L"))
    g = build_guard(GuardParams(guard_path=st["guard_path"], handrail=True, infill="balusters",
                                bottom_rail=True))
    geo = ad.to_rhino(g, 1.0, 0.01)
    assert len(geo["posts"]) == g["info"]["post_count"]
    assert geo["top_rail"] and geo["bottom_rail"] and geo["handrail"]
    assert len(geo["balusters"]) == g["info"]["baluster_count"]
    assert geo["brackets"] and len(geo["rail_lines"]) == 6
    # a post prism: base corner at the post base height, extruded up to the rail underside
    post = g["posts"][0]
    brep = geo["posts"][0]
    assert all(abs(p.Z - post["base"][2]) < 1e-9 for p in brep.points)
    assert brep.vector.Z == pytest.approx(post["top"][2] - post["base"][2])


def test_adapter_glass_and_mesh(rhino):
    from adapters import guards_rhino as ad
    st = build_stair(StairParams())
    for infill in ("glass", "mesh", "cable", "horizontal"):
        g = build_guard(GuardParams(guard_path=st["guard_path"], sides="left", infill=infill,
                                    post_rules=["max_spacing", "ends"]))
        geo = ad.to_rhino(g, 1.0, 0.01)
        if infill in ("glass", "mesh"):
            assert len(geo["panels"]) == g["info"]["panel_count"]
            assert geo["panels"][0].vector is not None
        if infill == "mesh":
            assert geo["frames"]
        if infill == "glass":
            assert geo["clamps"]
        if infill == "cable":
            assert geo["cables"]
        if infill == "horizontal":
            assert geo["bars"]


def test_adapter_profiles(rhino):
    from adapters import guards_rhino as ad
    plane = fake_rhino.Plane(fake_rhino.Point3d(0, 0, 0), fake_rhino.Vector3d(1, 0, 0),
                             fake_rhino.Vector3d(0, 1, 0))
    rect = ad.profile_curve({"shape": "rect", "w": 60, "h": 40}, plane, 0.001)
    xs = [p.X for p in rect.pts]
    assert max(xs) == pytest.approx(0.03) and min(xs) == pytest.approx(-0.03)
    circ = ad.profile_curve({"shape": "round", "d": 42}, plane, 1.0)
    assert circ.PointCount == 17
    cust = ad.profile_curve({"shape": "custom", "points": [(0, 0), (10, 0), (5, 8)]}, plane, 1.0)
    assert cust.PointCount == 4


def test_curves_to_polylines(rhino):
    from adapters import guards_rhino as ad
    c = fake_rhino.PolylineCurve([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 0, 0)])
    polys, closed = ad.curves_to_polylines([c, None], 0.01)
    assert polys == [[(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 0, 0)]] and closed == [True]


# --- component end to end --------------------------------------------------------------------------
class Messages(object):
    def __init__(self):
        self.items, self.Message = [], ""

    def AddRuntimeMessage(self, level, text):
        self.items.append((level, text))

    def OnPingDocument(self):
        return types.SimpleNamespace(FilePath=None, IsFilePathDefined=False)


def run_script(monkeypatch, source, path, doc, **values):
    fake_rhino.install(monkeypatch, doc)
    monkeypatch.setenv("STAIRGEN_PATH", os.path.abspath(ROOT))
    comp = Messages()
    g = {"__name__": "__main__", "ghenv": types.SimpleNamespace(Component=comp)}
    g.update(values)
    exec(compile(source, path, "exec"), g)
    return g, comp


def stair_json(monkeypatch, doc, **values):
    g, comp = run_script(monkeypatch, STAIR_SOURCE, STAIR_SCRIPT, doc, **values)
    assert [t for l, t in comp.items if l == "Error"] == []
    return g["guard_path"]


def test_component_stair_mode(monkeypatch):
    doc = fake_rhino.Doc()
    gp = stair_json(monkeypatch, doc, stair_type="L")
    g, comp = run_script(monkeypatch, SOURCE, SCRIPT, doc, guard_path=gp, side="both",
                         handrail=True, infill="balusters")
    assert [t for l, t in comp.items if l == "Error"] == []
    assert g["posts"] and g["top_rail"] and g["handrail"] and g["balusters"]
    assert g["warnings"] == [] and "GUARD (stair mode" in g["report"]
    assert comp.Message.endswith("0 warn")


def test_component_metre_document_round_trip(monkeypatch):
    doc = fake_rhino.Doc("Meters", 0.001)
    gp = stair_json(monkeypatch, doc, base_pt=fake_rhino.Point3d(10, 0, 0))
    assert json.loads(gp)["document_scale"] == 0.001
    g, comp = run_script(monkeypatch, SOURCE, SCRIPT, doc, guard_path=gp, side="left",
                         post_size=50)
    assert [t for l, t in comp.items if l == "Error"] == []
    post = g["posts"][0]
    zs = [p.Z for p in post.points]
    assert min(zs) == pytest.approx(0.2)                     # on tread 1, in metres
    assert all(abs(p.X - 10) < 1 for p in post.points)       # at the stair's base point
    assert post.vector.Z == pytest.approx(0.88 - 0.02 + 0.1, abs=0.005)   # mid-tread: + half a rise
    xs = [p.X for p in post.points]
    assert max(xs) - min(xs) == pytest.approx(0.05)          # 50 mm post in metres


def test_component_curve_mode(monkeypatch):
    curve = fake_rhino.PolylineCurve([(0, 0, 0), (3000, 0, 0), (3000, 2000, 0), (0, 2000, 0), (0, 0, 0)])
    g, comp = run_script(monkeypatch, SOURCE, SCRIPT, fake_rhino.Doc(), curves=[curve],
                         post_rules=["max_spacing"], infill="glass")
    assert [t for l, t in comp.items if l == "Error"] == []
    assert g["panels"] and len(g["posts"]) >= 10


def test_component_needs_input(monkeypatch):
    g, comp = run_script(monkeypatch, SOURCE, SCRIPT, fake_rhino.Doc())
    assert any("Connect guard_path" in t for l, t in comp.items)


def test_component_bad_values(monkeypatch):
    doc = fake_rhino.Doc()
    gp = stair_json(monkeypatch, doc)
    g, comp = run_script(monkeypatch, SOURCE, SCRIPT, doc, guard_path=gp, infill="wire")
    assert any("infill 'wire'" in t for l, t in comp.items if l == "Error")
    g, comp = run_script(monkeypatch, SOURCE, SCRIPT, doc, guard_path="{not json")
    assert any("guard_path is not valid JSON" in t for l, t in comp.items)


def test_component_warnings(monkeypatch):
    doc = fake_rhino.Doc()
    gp = stair_json(monkeypatch, doc)
    g, comp = run_script(monkeypatch, SOURCE, SCRIPT, doc, guard_path=gp, height_flight=800,
                         infill="horizontal")
    codes = {w.split(":")[0] for w in g["warnings"]}
    assert {"GUARD_HEIGHT", "CLIMBABLE"} <= codes
    assert [t for l, t in comp.items if l == "Warning"] == g["warnings"]


def test_scripts_are_python39():
    import ast
    ast.parse(SOURCE, feature_version=(3, 9))
    ast.parse(open(os.path.join(ROOT, "adapters", "guards_rhino.py")).read(), feature_version=(3, 9))
    for fn in os.listdir(os.path.join(ROOT, "core", "guards")):
        if fn.endswith(".py"):
            ast.parse(open(os.path.join(ROOT, "core", "guards", fn)).read(), feature_version=(3, 9))
