"""Tests for grasshopper/stair_generator_component.py outside Rhino.

Rhino, Grasshopper and scriptcontext are replaced by small stand-ins, and a fake
'stairgen' library is written to a temporary folder. This checks the component's own
logic (library lookup, units, document handling, input checks, set-up keys); it does
not check the real stair library or real Rhino geometry.
"""
import os
import sys
import types

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "grasshopper",
                      "stair_generator_component.py")
SOURCE = open(SCRIPT, encoding="utf-8").read()

UNITS_TO_MM = {"Millimeters": 1.0, "Centimeters": 10.0, "Meters": 1000.0, "Inches": 25.4}


# --- stand-ins for the Rhino / Grasshopper API -------------------------------------
class Point3d:
    def __init__(self, x, y, z):
        self.X, self.Y, self.Z = x, y, z


Point3d.Origin = Point3d(0, 0, 0)


class Transform:
    @staticmethod
    def Scale(origin, f):
        return ("scale", f)


class FakeGeom:
    """Curve/Brep stand-in that remembers its total scale."""
    def __init__(self, name, scale=1.0):
        self.name, self.scale = name, scale

    def Duplicate(self):
        return FakeGeom(self.name, self.scale)

    def Transform(self, xf):
        self.scale *= xf[1]
        return True


class UnitSystem:
    Millimeters = "UnitSystem.Millimeters"


class FakeRhinoDoc:
    def __init__(self, units="Millimeters", tol=0.01, path=None):
        self.ModelUnitSystem = "UnitSystem." + units
        self.ModelAbsoluteTolerance = tol
        self.ModelAngleToleranceDegrees = 1.0
        self.Path = path


class Messages:
    def __init__(self):
        self.items = []

    def AddRuntimeMessage(self, level, text):
        self.items.append((level, text))


class Param:
    def __init__(self, nick):
        self.NickName = nick


class FakeGhDoc:
    def __init__(self, path):
        self.FilePath = path
        self.IsFilePathDefined = path is not None
        self.scheduled = []

    def ScheduleSolution(self, ms, cb):
        self.scheduled.append(cb)


class Component(Messages):
    def __init__(self, inputs, gh_path):
        super().__init__()
        self.Params = types.SimpleNamespace(Input=[Param(n) for n in inputs])
        self.InstanceGuid = "guid-1"
        self.Message = ""
        self.doc = FakeGhDoc(gh_path)

    def OnPingDocument(self):
        return self.doc


def install_fakes(monkeypatch, rdoc, sticky):
    rhino = types.ModuleType("Rhino")
    rhino.RhinoDoc = types.SimpleNamespace(ActiveDoc=rdoc)
    rhino.UnitSystem = UnitSystem
    rhino.RhinoMath = types.SimpleNamespace(
        UnitScale=lambda a, b: UNITS_TO_MM[a.split(".")[-1]] / UNITS_TO_MM[b.split(".")[-1]])
    geom = types.ModuleType("Rhino.Geometry")
    geom.Point3d, geom.Transform = Point3d, Transform
    rhino.Geometry = geom
    gh = types.ModuleType("Grasshopper")
    kernel = types.ModuleType("Grasshopper.Kernel")
    kernel.GH_RuntimeMessageLevel = types.SimpleNamespace(Error="Error")
    kernel.GH_Document = types.SimpleNamespace(GH_ScheduleDelegate=lambda f: f)
    gh.Kernel = kernel
    sc = types.ModuleType("scriptcontext")
    sc.sticky = sticky
    for name, mod in [("Rhino", rhino), ("Rhino.Geometry", geom), ("Grasshopper", gh),
                      ("Grasshopper.Kernel", kernel), ("scriptcontext", sc)]:
        monkeypatch.setitem(sys.modules, name, mod)


FAKE_LIB = '''
CALLS = {}
class Stair: pass
def _geo(name): 
    import builtins
    return builtins.__dict__["_FakeGeom"](name)
def _to_curve(v):
    return v
def run_design(ghenv, **kw):
    CALLS["design"] = kw
    if kw["stair_type"] == "boom":
        raise ValueError("library exploded")
    return {"stair": Stair(), "messages": [], "report": "REPORT", "status": "OK",
            "n_risers": 16, "riser_h": 175.0, "tread_d": 280.0, "flights": 1, "headroom": 2100.0}
def run_geometry(stair):
    return {"messages": [], "solids": [_geo("solid")], "treads": [_geo("tread")],
            "risers": [], "stringers": [], "landings": []}
def run_annotation(stair, flag):
    return {"messages": [], "numbers_pt": [], "numbers_txt": [], "arrows": [],
            "up_pt": None, "up_txt": "UP"}
def boundary_check(stair, curve):
    CALLS["boundary"] = curve
    return True, ""
def bake(*args):
    CALLS["bake"] = args
    return "baked"
def post_messages(ghenv, msgs):
    CALLS["messages"] = msgs
'''


def make_library(folder):
    for pkg in ("stairgen", "stairgen_rhino"):
        os.makedirs(os.path.join(folder, pkg), exist_ok=True)
        open(os.path.join(folder, pkg, "__init__.py"), "w").close()
    with open(os.path.join(folder, "stairgen_rhino", "gh.py"), "w") as f:
        f.write(FAKE_LIB)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """SCRIPT/ holds the .gh; the library is in SCRIPT/stair-generator/stair-generator."""
    script_dir = tmp_path / "SCRIPT"
    lib = script_dir / "stair-generator" / "stair-generator"
    make_library(str(lib))
    monkeypatch.delenv("STAIRGEN_PATH", raising=False)
    import builtins
    monkeypatch.setattr(builtins, "_FakeGeom", FakeGeom, raising=False)
    yield types.SimpleNamespace(root=tmp_path, script_dir=script_dir, lib=lib,
                                gh=str(script_dir / "stair.gh"))
    for name in list(sys.modules):
        if name.split(".")[0] in ("stairgen", "stairgen_rhino"):
            del sys.modules[name]
    sys.path[:] = [p for p in sys.path if str(tmp_path) not in p]


def run(monkeypatch, gh_path, rdoc=None, inputs=None, setup_done=True, sticky=None,
        source=SOURCE, **values):
    sticky = {} if sticky is None else sticky
    install_fakes(monkeypatch, rdoc, sticky)
    ns = {"__name__": "__main__"}
    exec(compile(source.split("\nimport math\nimport scriptcontext")[0], SCRIPT, "exec"), ns)
    expected = ns["EXPECTED_INPUTS"]
    comp = Component(inputs if inputs is not None else expected, gh_path)
    if setup_done:
        sticky["stairgen_refresh_{}_{}".format(comp.InstanceGuid, ns["VERSION"])] = True
    g = {"__name__": "__main__", "ghenv": types.SimpleNamespace(Component=comp)}
    g.update({n: None for n in expected})
    g.update(values)
    exec(compile(source, SCRIPT, "exec"), g)
    lib = sys.modules.get("stairgen_rhino.gh")
    return types.SimpleNamespace(g=g, comp=comp, calls=getattr(lib, "CALLS", {}),
                                 errors=[t for lvl, t in comp.items if lvl == "Error"],
                                 sticky=sticky)


# --- no hardcoded paths --------------------------------------------------------------
def test_no_hardcoded_drive_paths():
    import re
    assert not re.search(r"[A-Za-z]:\\\\", SOURCE.replace("e.g. C:\\\\", ""))
    assert "F:\\" not in SOURCE and "CMC" not in SOURCE


def test_finds_library_next_to_gh_file(project, monkeypatch):
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), stair_type="straight")
    assert r.errors == []
    assert sys.modules["stairgen_rhino.gh"].__file__.startswith(str(project.lib))
    assert r.g["n_risers"] == 16


def test_library_in_parent_folder(tmp_path, monkeypatch, project):
    gh = str(project.script_dir / "sub" / "deeper" / "x.gh")
    r = run(monkeypatch, gh, FakeRhinoDoc(), stair_type="straight")
    assert r.errors == []


def test_env_var(tmp_path, monkeypatch, project):
    other = tmp_path / "elsewhere" / "lib"
    make_library(str(other))
    monkeypatch.setenv("STAIRGEN_PATH", str(other))
    r = run(monkeypatch, None, FakeRhinoDoc(), stair_type="straight")  # unsaved .gh
    assert r.errors == []
    assert sys.modules["stairgen_rhino.gh"].__file__.startswith(str(other))


def test_script_setting_relative_to_gh(project, monkeypatch):
    src = SOURCE.replace('STAIRGEN_PATH = ""', 'STAIRGEN_PATH = r"stair-generator/stair-generator"')
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), source=src, stair_type="straight")
    assert r.errors == []


def test_unsaved_gh_falls_back_to_rhino_file_folder(project, monkeypatch):
    rdoc = FakeRhinoDoc(path=str(project.script_dir / "model.3dm"))
    r = run(monkeypatch, None, rdoc, stair_type="straight")
    assert r.errors == []


def test_unsaved_gh_and_rhino_gives_clear_error(project, monkeypatch):
    r = run(monkeypatch, None, FakeRhinoDoc(), stair_type="straight")
    assert len(r.errors) == 1
    assert "Stair library not found" in r.errors[0] and "not saved" in r.errors[0]


def test_missing_library_lists_where_it_looked(tmp_path, monkeypatch, project):
    gh = str(tmp_path / "empty" / "x.gh")
    os.makedirs(os.path.dirname(gh))
    r = run(monkeypatch, gh, FakeRhinoDoc(), stair_type="straight")
    assert "Looked in" in r.errors[0] and str(tmp_path / "empty") in r.errors[0]


def test_bad_configured_path_is_reported(project, monkeypatch):
    src = SOURCE.replace('STAIRGEN_PATH = ""', 'STAIRGEN_PATH = r"Z:/nowhere"')
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), source=src, stair_type="straight")
    assert "Z:/nowhere" in r.errors[0] or "nowhere" in r.errors[0]


def test_stale_copy_on_sys_path_is_replaced(tmp_path, monkeypatch, project):
    old = tmp_path / "old_drive" / "lib"
    make_library(str(old))
    sys.path.insert(0, str(old))
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), stair_type="straight")
    assert r.errors == []
    assert str(old) not in sys.path
    assert sys.modules["stairgen_rhino.gh"].__file__.startswith(str(project.lib))


# --- document handling ---------------------------------------------------------------
def test_no_rhino_document(project, monkeypatch):
    r = run(monkeypatch, project.gh, None, stair_type="straight")
    assert r.errors and "No Rhino document" in r.errors[0]


# --- units ---------------------------------------------------------------------------
def test_mm_document_passes_inputs_through_unchanged(project, monkeypatch):
    p, path = Point3d(1, 2, 3), FakeGeom("path")
    r = run(monkeypatch, project.gh, FakeRhinoDoc("Millimeters"), stair_type="straight",
            start=p, path=path)
    assert r.calls["design"]["start"] is p and r.calls["design"]["path"] is path
    assert r.g["solids"][0].scale == 1.0
    assert "Rhino units: Millimeters" in r.g["report"]


def test_metre_document_converts_in_and_out(project, monkeypatch):
    p = Point3d(1.5, 0, 3)
    r = run(monkeypatch, project.gh, FakeRhinoDoc("Meters", tol=0.001), stair_type="straight",
            start=p, path=FakeGeom("path"), opening=FakeGeom("open"),
            boundary=FakeGeom("bnd"), bake=True)
    d = r.calls["design"]
    assert (d["start"].X, d["start"].Z) == (1500.0, 3000.0)
    assert d["path"].scale == 1000.0 and d["opening"].scale == 1000.0
    assert r.calls["boundary"].scale == 1000.0
    assert r.g["solids"][0].scale == pytest.approx(0.001)  # output back in metres
    assert r.calls["bake"][1][0].scale == pytest.approx(0.001)  # baked in metres
    assert "converted to meters" in r.g["report"]
    assert "tolerance 1 mm" in r.g["report"]
    assert r.g["riser_h"] == 175.0  # numbers stay in mm


def test_coarse_tolerance_warns(project, monkeypatch):
    r = run(monkeypatch, project.gh, FakeRhinoDoc("Meters", tol=0.01), stair_type="straight")
    assert any(lvl == "warning" and "tolerance" in t for lvl, t in r.calls["messages"])


def test_inch_document(project, monkeypatch):
    r = run(monkeypatch, project.gh, FakeRhinoDoc("Inches"), stair_type="straight",
            start=Point3d(10, 0, 0))
    assert r.calls["design"]["start"].X == pytest.approx(254.0)
    assert r.g["solids"][0].scale == pytest.approx(1 / 25.4)


# --- input checks --------------------------------------------------------------------
@pytest.mark.parametrize("value,expected", [("straight", "straight"), ("Straight", "straight"),
                                            ("l", "L"), (' "U" ', "U"), ("SPIRAL", "spiral"),
                                            (None, None)])
def test_stair_type_is_normalised(project, monkeypatch, value, expected):
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), stair_type=value)
    assert r.errors == []
    assert r.calls["design"]["stair_type"] == expected


def test_mistyped_stair_type_is_a_component_error_not_a_traceback(project, monkeypatch, capsys):
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), stair_type="stright")
    assert r.errors == ["stair_type = 'stright' is not valid. Use one of: straight, L, U, spiral."]
    assert "Traceback" not in capsys.readouterr().err
    assert "design" not in r.calls


def test_bad_turn_and_location(project, monkeypatch):
    assert "turn" in run(monkeypatch, project.gh, FakeRhinoDoc(), turn="up").errors[0]
    assert "location" in run(monkeypatch, project.gh, FakeRhinoDoc(), location="mid").errors[0]


def test_non_numeric_auto_input(project, monkeypatch):
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), riser_count="many")
    assert "riser_count" in r.errors[0] and "not a number" in r.errors[0]


def test_zero_means_auto(project, monkeypatch):
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), riser_count=0, tread_depth=0)
    assert r.calls["design"]["riser_count"] is None and r.calls["design"]["tread_depth"] is None


def test_stringers_off(project, monkeypatch):
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), stringer_on="No")
    assert "stringer_thk = 0" in r.calls["design"]["options"]


def test_library_exception_is_short_error(project, monkeypatch, capsys):
    src = SOURCE  # 'boom' is rejected before the library; call the library with a valid type
    lib_src = FAKE_LIB.replace('kw["stair_type"] == "boom"', 'True')
    with open(os.path.join(str(project.lib), "stairgen_rhino", "gh.py"), "w") as f:
        f.write(lib_src)
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), source=src, stair_type="straight")
    assert r.errors[0].startswith("Stair generator failed: ValueError: library exploded")
    assert "Traceback" in capsys.readouterr().err  # details still available in 'out'


def test_relative_rules_path(project, monkeypatch):
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), rules="rules/my_rules.txt")
    assert r.calls["design"]["rules"] == os.path.normpath(
        os.path.join(str(project.script_dir), "rules", "my_rules.txt"))


def test_relative_rules_path_unsaved_gh(project, monkeypatch, tmp_path):
    monkeypatch.setenv("STAIRGEN_PATH", str(project.lib))
    r = run(monkeypatch, None, FakeRhinoDoc(), rules="rules.txt")
    assert "save the .gh file first" in r.errors[0]


# --- set-up keys ---------------------------------------------------------------------
def test_setup_runs_once_for_new_component(project, monkeypatch):
    sticky = {}
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), inputs=["x"], setup_done=False,
            sticky=sticky)
    assert len(r.comp.doc.scheduled) == 1
    r2 = run(monkeypatch, project.gh, FakeRhinoDoc(), inputs=["x"], setup_done=False,
             sticky=sticky)
    assert r2.comp.doc.scheduled[0].__name__ == "_refresh"  # no second set-up


def test_rebuild_works_after_first_setup(project, monkeypatch):
    sticky = {}
    run(monkeypatch, project.gh, FakeRhinoDoc(), inputs=["x"], setup_done=False, sticky=sticky)
    src = SOURCE.replace("REBUILD = False", "REBUILD = True")
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), source=src, sticky=sticky)
    assert [f.__name__ for f in r.comp.doc.scheduled] == ["_setup"]
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), source=src, sticky=sticky)
    assert r.comp.doc.scheduled == []  # only once while REBUILD stays True
    run(monkeypatch, project.gh, FakeRhinoDoc(), sticky=sticky)  # back to False ...
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), source=src, sticky=sticky)
    assert [f.__name__ for f in r.comp.doc.scheduled] == ["_setup"]  # ... and True again


def test_setup_does_not_need_the_library(tmp_path, monkeypatch, project):
    gh = str(tmp_path / "nolib" / "x.gh")
    r = run(monkeypatch, gh, None, inputs=["x"], setup_done=False)
    assert r.errors == [] and len(r.comp.doc.scheduled) == 1


def test_dotnet_style_list_output_is_converted(project, monkeypatch):
    class NetList:  # iterable, not a Python list
        def __init__(self, items):
            self.items = items

        def __iter__(self):
            return iter(self.items)
    lib = os.path.join(str(project.lib), "stairgen_rhino", "gh.py")
    src = open(lib).read().replace('"solids": [_geo("solid")]',
                                   '"solids": __import__("builtins")._NetList([_geo("solid")])')
    open(lib, "w").write(src)
    import builtins
    monkeypatch.setattr(builtins, "_NetList", NetList, raising=False)
    r = run(monkeypatch, project.gh, FakeRhinoDoc("Meters", tol=0.001))
    assert r.g["solids"][0].scale == pytest.approx(0.001)


# --- typed layer paths (Elefont style) -------------------------------------------------
def _bake(monkeypatch, project, **values):
    return run(monkeypatch, project.gh, FakeRhinoDoc(), bake=True, **values)


@pytest.mark.parametrize("bake_layer,text_layer,expected", [
    (None, None, ("03_ARCH::A-STAIR", "03_ARCH::A-STAIR")),          # office defaults
    ("", "same", ("03_ARCH::A-STAIR", "03_ARCH::A-STAIR")),
    ("PROJ::Stairs::Core-A", None, ("PROJ::Stairs::Core-A", "PROJ::Stairs::Core-A")),
    (" 03_ARCH :: A-STAIR ", "09_DOC::D-TEXT", ("03_ARCH::A-STAIR", "09_DOC::D-TEXT")),
    ('"03_ARCH::A-STAIR"', "NONE", ("03_ARCH::A-STAIR", None)),      # no annotation
    ("Stairs", "Same", ("Stairs", "Stairs")),                         # top-level layer
])
def test_layer_paths(project, monkeypatch, bake_layer, text_layer, expected):
    r = _bake(monkeypatch, project, bake_layer=bake_layer, text_layer=text_layer)
    assert r.errors == []
    assert (r.calls["bake"][2], r.calls["bake"][3]) == expected


@pytest.mark.parametrize("value", ["03_ARCH::", "::A-STAIR", "03_ARCH::::A-STAIR", "A{STAIR}"])
def test_bad_layer_path_is_reported_before_baking(project, monkeypatch, value):
    r = run(monkeypatch, project.gh, FakeRhinoDoc(), bake_layer=value)  # Bake not pressed
    assert r.errors and "bake_layer" in r.errors[0]
    assert "design" not in r.calls


def test_bad_text_layer(project, monkeypatch):
    r = _bake(monkeypatch, project, text_layer="09_DOC::")
    assert r.errors and "text_layer" in r.errors[0] and "bake" not in r.calls


def test_layer_controls_are_text_panels_with_office_defaults():
    ns = {}
    exec(compile(SOURCE.split("\nimport math\nimport scriptcontext")[0], SCRIPT, "exec"), ns)
    controls = {c[0]: c for c in ns["CONTROLS"]}
    assert controls["bake_layer"][1:] == ("text", "03_ARCH::A-STAIR")
    assert controls["text_layer"][1:] == ("text", "same")
    assert ns["VERSION"] == 10  # existing .gh files migrate their drop-downs once


@pytest.mark.parametrize("name,expression,text", [
    ("bake_layer", '"03_ARCH::A-STAIR"', "03_ARCH::A-STAIR"),
    ("text_layer", '"same"', "same"),
    ("text_layer", '""', "none"),                      # old "No annotation"
    ("text_layer", '"09_DOC::D-TEXT"', "09_DOC::D-TEXT"),
])
def test_old_drop_down_choice_is_kept(name, expression, text):
    ns = {}
    exec(compile(SOURCE.split("\nimport math\nimport scriptcontext")[0], SCRIPT, "exec"), ns)
    assert ns["list_choice_to_text"](name, expression) == text
