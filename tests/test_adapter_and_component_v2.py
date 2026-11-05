"""Adapter (with a fake RhinoCommon), library locator, and the v2 GH component end to end."""
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
from adapters import locate  # noqa: E402

SCRIPT = os.path.join(ROOT, "grasshopper", "stair_component_v2.py")
SOURCE = open(SCRIPT, encoding="utf-8").read()


@pytest.fixture
def rhino(monkeypatch):
    return fake_rhino.install(monkeypatch, fake_rhino.Doc())


# --- adapter ------------------------------------------------------------------------------
def test_placement_scale_rotate_translate(rhino):
    from adapters import stairs_rhino as ad
    result = build_stair(StairParams(stair_type="straight", tread_run=280))
    base = fake_rhino.Point3d(1000, 2000, 0)
    geo = ad.to_rhino(result, base, 90.0, 0.001, 0.001)
    # first tread, first corner: core (-25, -450, 200) -> scale -> rotate 90 -> translate
    p = geo["treads"][0].points[0]
    assert (p.X, p.Y, p.Z) == pytest.approx((1000 + 0.45, 2000 - 0.025, 0.2))
    # riser extrude vector (+X in core) is rotated to +Y and scaled to the thickness
    v = geo["risers"][0].vector
    assert (v.X, v.Y, v.Z) == pytest.approx((0, 0.019, 0))
    # treads extrude down by the scaled thickness
    v = geo["treads"][0].vector
    assert (v.X, v.Y, v.Z) == pytest.approx((0, 0, -0.038))
    assert len(geo["treads"]) == 13 and len(geo["stringers"]) == 2
    assert len(geo["guard_lines"]) == 2 and geo["guard_lines"][0].PointCount == 14


def test_guard_path_json_is_in_document_frame(rhino):
    from adapters import stairs_rhino as ad
    result = build_stair(StairParams(stair_type="L"))
    geo = ad.to_rhino(result, fake_rhino.Point3d(10, 0, 0), 0.0, 0.001, 0.001)
    gp = json.loads(geo["guard_path_json"])
    assert gp["version"] == 1 and gp["document_scale"] == 0.001
    assert gp["width"] == pytest.approx(0.9) and gp["rise"] == pytest.approx(0.2)
    first = gp["sides"]["left"]["polyline"][0]
    assert first == pytest.approx([10 - 0.025, 0.45, 0.2])
    assert gp["steps"][0]["direction"] == pytest.approx([1, 0])
    assert gp["sides"]["left"]["segments"] == result["guard_path"]["sides"]["left"]["segments"]


def test_zero_thickness_gives_planar_face(rhino):
    from adapters import stairs_rhino as ad
    result = build_stair(StairParams(open_risers=True))
    geo = ad.to_rhino(result)
    assert all(b.vector is None for b in geo["risers"])


def test_opening_curve_back_to_core_frame(rhino):
    from adapters import stairs_rhino as ad
    # document in metres, stair at (10, 5) rotated 90 deg; opening drawn in the document
    curve = fake_rhino.PolylineCurve([(10, 5, 0), (10, 6, 0), (9, 6, 0), (9, 5, 0), (10, 5, 0)])
    poly = ad.curve_to_polygon_mm(curve, 1000.0, fake_rhino.Point3d(10, 5, 0), 90.0, 0.001)
    assert len(poly) == 4
    assert poly[0] == pytest.approx((0, 0))
    assert poly[1] == pytest.approx((1000, 0))      # +Y in the document = +X in the core
    assert poly[2] == pytest.approx((1000, 1000))


def test_document_units(rhino):
    from adapters import stairs_rhino as ad
    assert ad.document_units(fake_rhino.Doc("Meters", 0.001))[0] == 1000.0
    assert ad.document_units(fake_rhino.Doc("Inches"))[2] == "Inches"


# --- locator ------------------------------------------------------------------------------
def make_lib(folder):
    for pkg in ("core", "adapters"):
        os.makedirs(os.path.join(folder, pkg), exist_ok=True)
        open(os.path.join(folder, pkg, "__init__.py"), "w").close()


def test_locate_next_to_gh(tmp_path, monkeypatch):
    monkeypatch.delenv("STAIRGEN_PATH", raising=False)
    lib = tmp_path / "SCRIPT" / "stair-generator"
    make_lib(str(lib))
    found, looked = locate.find_library("", str(tmp_path / "SCRIPT" / "x.gh"), None)
    assert found == os.path.normpath(str(lib))


def test_locate_env_and_configured(tmp_path, monkeypatch):
    lib = tmp_path / "lib"
    make_lib(str(lib))
    monkeypatch.setenv("STAIRGEN_PATH", str(lib))
    assert locate.find_library("", None, None)[0] == os.path.normpath(str(lib))
    monkeypatch.delenv("STAIRGEN_PATH")
    assert locate.find_library("lib", str(tmp_path / "a.gh"), None)[0] == os.path.normpath(str(lib))
    found, looked = locate.find_library("lib", None, None)
    assert found is None and any("not saved" in x for x in looked)


def test_locate_not_found_lists_places(tmp_path, monkeypatch):
    monkeypatch.delenv("STAIRGEN_PATH", raising=False)
    found, looked = locate.find_library("", str(tmp_path / "x.gh"), None)
    assert found is None and str(tmp_path) in locate.not_found_message(looked)


# --- component v2 end to end ----------------------------------------------------------------
class Messages(object):
    def __init__(self):
        self.items, self.Message = [], ""

    def AddRuntimeMessage(self, level, text):
        self.items.append((level, text))

    def OnPingDocument(self):
        return types.SimpleNamespace(FilePath=None, IsFilePathDefined=False)


def run_component(monkeypatch, doc, **values):
    fake_rhino.install(monkeypatch, doc)
    monkeypatch.setenv("STAIRGEN_PATH", os.path.abspath(ROOT))
    comp = Messages()
    g = {"__name__": "__main__", "ghenv": types.SimpleNamespace(Component=comp)}
    g.update(values)
    exec(compile(SOURCE, SCRIPT, "exec"), g)
    return g, comp


def test_component_defaults(monkeypatch):
    g, comp = run_component(monkeypatch, fake_rhino.Doc())
    assert [t for l, t in comp.items if l == "Error"] == []
    assert len(g["treads"]) == 13 and len(g["risers"]) == 14
    assert g["warnings"] == [] and comp.Message == "14 risers, 0 warn"
    assert "STAIR straight" in g["report"] and "BOM" in g["report"]
    gp = json.loads(g["guard_path"])
    assert gp["stair_type"] == "straight"
    assert any(line.startswith("n_risers = 14") for line in g["info"])


def test_component_inputs_and_lists(monkeypatch):
    g, comp = run_component(monkeypatch, fake_rhino.Doc(), stair_type="U2", turn="Right",
                            flight_risers=[6, 4, 5], landing_depths=[1000, 1100],
                            winders=False, stringer_type="cut", rules='{"rise_max_mm": 190}',
                            tread_run=0, riser_count=0)
    assert [t for l, t in comp.items if l == "Error"] == []
    assert any(line == "flights = [6, 4, 5]" for line in g["info"])
    assert len(g["landings"]) == 2 and len(g["stringers"]) == 6


def test_component_warnings_are_runtime_messages(monkeypatch):
    g, comp = run_component(monkeypatch, fake_rhino.Doc(), riser_count=13, width=800)
    assert len(g["warnings"]) >= 2
    assert [t for l, t in comp.items if l == "Warning"] == g["warnings"]
    assert len(g["warning_index"]) == len(g["warnings"])


def test_component_bad_type_is_red_message(monkeypatch):
    g, comp = run_component(monkeypatch, fake_rhino.Doc(), stair_type="stright")
    errs = [t for l, t in comp.items if l == "Error"]
    assert len(errs) == 1 and "stair_type 'stright'" in errs[0]
    assert "treads" not in g


def test_component_bad_rules_json(monkeypatch):
    g, comp = run_component(monkeypatch, fake_rhino.Doc(), rules="{rise: 1}")
    assert any("rules is not valid JSON" in t for l, t in comp.items)


def test_component_no_document(monkeypatch):
    g, comp = run_component(monkeypatch, None)
    assert any("No Rhino document" in t for l, t in comp.items)


def test_component_metre_document_scales_geometry(monkeypatch):
    g, comp = run_component(monkeypatch, fake_rhino.Doc("Meters", 0.001),
                            base_pt=fake_rhino.Point3d(5, 5, 0))
    assert [t for l, t in comp.items if l == "Error"] == []
    p = g["treads"][0].points[0]
    assert (p.X, p.Y, p.Z) == pytest.approx((5 - 0.025, 5 - 0.45, 0.2))
    assert "document: Meters" in g["report"]


def test_component_opening_turns_on_headroom(monkeypatch):
    opening = fake_rhino.PolylineCurve([(1500, -600, 0), (5000, -600, 0), (5000, 600, 0),
                                        (1500, 600, 0), (1500, -600, 0)])
    g, comp = run_component(monkeypatch, fake_rhino.Doc(), opening=opening, tread_run=280)
    assert any(w.startswith("HEADROOM") for w in g["warnings"])
    assert "headroom min: 1350" in g["report"]


def test_component_missing_library_message(monkeypatch, tmp_path):
    fake_rhino.install(monkeypatch, fake_rhino.Doc())
    monkeypatch.setenv("STAIRGEN_PATH", str(tmp_path))
    comp = Messages()
    g = {"__name__": "__main__", "ghenv": types.SimpleNamespace(Component=comp)}
    src = SOURCE.replace('LIBRARY_PATH = ""', 'LIBRARY_PATH = r"{}"'.format(tmp_path))
    exec(compile(src, SCRIPT, "exec"), g)
    errs = [t for l, t in comp.items if l == "Error"]
    assert errs and "Stair library not found" in errs[0] and str(tmp_path) in errs[0]


def test_script_is_python39_syntax():
    import ast
    ast.parse(SOURCE, feature_version=(3, 9))
    for fn in ("adapters/stairs_rhino.py", "adapters/locate.py", "core/stairs/layout.py",
               "core/stairs/checks.py", "core/geom.py"):
        ast.parse(open(os.path.join(ROOT, fn)).read(), feature_version=(3, 9))
