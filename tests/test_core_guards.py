"""Tests for core/guards (pure Python, no Rhino)."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.stairs import StairParams, build_stair  # noqa: E402
from core.guards import GuardParams, build_guard  # noqa: E402
from core.guards import rails  # noqa: E402
from core.guards.path import side_paths_from_stair, kinks  # noqa: E402
from core.limits import load_limits  # noqa: E402

LIM = load_limits("guards")


def stair(**kw):
    return build_stair(StairParams(**kw))


def guard(gp, **kw):
    return build_guard(GuardParams(guard_path=gp, **kw))


def zlist(poly):
    return [q[2] for q in poly]


@pytest.fixture(scope="module")
def straight():
    return stair(stair_type="straight", tread_run=280)


@pytest.fixture(scope="module")
def l_stair():
    return stair(stair_type="L", tread_run=280)


# --- heights and rail profile ---------------------------------------------------------------
def test_top_rail_height_above_nosings_on_flight(straight):
    g = guard(straight["guard_path"], sides="left", height_flight=900, top_rail_h=40)
    path = side_paths_from_stair(straight["guard_path"], "left")[0]
    pieces = rails.profile(path, 880, 880, "smooth")
    # rail centreline = nosing z + 900 - 20 at every nosing station
    for st in path["steps"]:
        assert rails.z_at(pieces, st["t"]) == pytest.approx(st["z"] + 880)
    assert g["info"]["height_flight"] == 900
    assert len(g["top_rail"][0]["polyline"]) >= 2


def test_default_heights_come_from_config(straight):
    g = guard(straight["guard_path"], sides="left")
    assert g["info"]["height_flight"] == LIM.value("guard_height_residential_mm")
    g = guard(straight["guard_path"], sides="left", context="other")
    assert g["info"]["height_landing"] == LIM.value("guard_height_other_mm")


def test_rail_levels_out_at_top_floor(straight):
    g = guard(straight["guard_path"], sides="left", height_flight=900, height_landing=900,
              top_rail_h=40, transition="smooth")
    rail = g["top_rail"][0]["polyline"]
    assert rail[-1][2] == pytest.approx(2800 + 880)
    assert rail[-2][2] == pytest.approx(2800 + 880)      # level piece at the floor edge
    assert rail[-1][0] == pytest.approx(13 * 280)


def test_landing_rail_is_level_and_transition_smooth(l_stair):
    g = guard(l_stair["guard_path"], sides="right", height_flight=900, height_landing=900,
              top_rail_h=40)
    rail = g["top_rail"][0]
    z_land = 7 * 200 + 880
    level = [q for q in rail["polyline"] if abs(q[2] - z_land) < 1e-6]
    assert len(level) >= 3                                   # levels before the corner, corners
    assert "vertical" not in rail["kinds"]                   # smooth: no gooseneck on the outer side


def test_sharp_transition_has_vertical_pieces(l_stair):
    g = guard(l_stair["guard_path"], sides="right", transition="sharp")
    assert "vertical" in g["top_rail"][0]["kinds"]


def test_inner_corner_is_always_sharp(l_stair):
    g = guard(l_stair["guard_path"], sides="left", transition="smooth")
    assert "vertical" in g["top_rail"][0]["kinds"]
    poly = g["top_rail"][0]["polyline"]
    # the newel jump happens at the corner (1680, 450) moved inwards by the inset (25)
    jumps = [(a, b) for a, b in zip(poly, poly[1:]) if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-6]
    assert jumps and all(abs(a[0] - 1680) < 30 for a, b in jumps)


def test_different_flight_and_landing_heights(l_stair):
    g = guard(l_stair["guard_path"], sides="right", height_flight=900, height_landing=1070,
              top_rail_h=40)
    zs = zlist(g["top_rail"][0]["polyline"])
    assert max(zs) == pytest.approx(2800 + 1070 - 20)
    assert any(abs(z - (1400 + 1070 - 20)) < 1e-6 for z in zs)


def test_rail_z_never_decreases(l_stair):
    for side in ("left", "right"):
        g = guard(l_stair["guard_path"], sides=side, bottom_rail=True)
        for key in ("top_rail", "bottom_rail"):
            zs = zlist(g[key][0]["polyline"])
            assert all(b >= a - 1e-6 for a, b in zip(zs, zs[1:])), key


def test_bottom_rail_gap(straight):
    g = guard(straight["guard_path"], sides="left", bottom_rail=True, bottom_gap=90, bottom_rail_h=30)
    rail = g["bottom_rail"][0]["polyline"]
    first = straight["guard_path"]["steps"][0]
    assert rail[0][2] == pytest.approx(first["z"] + 90 + 15)
    g = guard(straight["guard_path"], sides="left", bottom_rail=False)
    assert g["bottom_rail"] == []


# --- posts -----------------------------------------------------------------------------------
def test_posts_every_step_and_ends(straight):
    g = guard(straight["guard_path"], sides="left", post_rules=["every_step", "ends"])
    posts = g["posts"]
    assert len(posts) == 13 + 1
    reasons = [q["reason"] for q in posts]
    assert reasons[0] == "end" and reasons[-1] == "end"
    # post on the first tread centre: base z = tread 1 top, plan x = nosing + run / 2
    first = posts[0]
    assert first["base"][2] == pytest.approx(200)
    assert first["base"][0] == pytest.approx(-25 + 140)
    assert first["base"][1] == pytest.approx(450 - 25)       # inset by post_size / 2
    # top post stands on the floor beyond the edge
    top = posts[-1]
    assert top["base"][2] == pytest.approx(2800)
    assert top["base"][0] == pytest.approx(13 * 280 + 25)
    # posts stop under the top rail
    path = side_paths_from_stair(straight["guard_path"], "left")[0]
    pieces = rails.profile(path, 880, 880, "smooth")
    for q in posts:
        s = min(q["station"], path["t"][-1])
        assert q["top"][2] == pytest.approx(rails.z_at(pieces, s) - 20)


def test_posts_every_n_steps(straight):
    g = guard(straight["guard_path"], sides="left", post_rules=["every_n_steps", "ends"], post_every_n=3)
    steps = [q for q in g["posts"] if q["reason"] == "step"]
    assert len(steps) == 4     # treads 3, 6, 9, 12 (the first tread is the end post)


def test_posts_max_spacing(straight):
    g = guard(straight["guard_path"], sides="left", post_rules=["max_spacing", "ends"],
              post_max_spacing=1000)
    st = sorted(q["station"] for q in g["posts"])
    gaps = [b - a for a, b in zip(st, st[1:])]
    assert max(gaps) <= 1000 + 1e-6
    assert g["info"]["max_post_spacing"] <= 1000 + 1e-6


def test_posts_on_nosing_with_offset(straight):
    g = guard(straight["guard_path"], sides="left", post_on_tread="nosing", post_tread_offset=60)
    assert g["posts"][0]["base"][0] == pytest.approx(-25 + 60)


def test_post_corners_on_landings(l_stair):
    g = guard(l_stair["guard_path"], sides="both", post_rules=["ends"])
    corners = [q for q in g["posts"] if q["reason"] == "corner"]
    assert len(corners) == 2                                  # one per side
    assert all(q["base"][2] == pytest.approx(1400) for q in corners)


def test_post_profiles_and_mounts(straight):
    gp = straight["guard_path"]
    r = guard(gp, sides="left", post_shape="rect", post_size=40, post_depth=80)
    assert r["posts"][0]["profile"] == {"shape": "rect", "w": 40, "d": 80}
    r = guard(gp, sides="left", post_shape="round", post_size=42)
    assert r["posts"][0]["profile"] == {"shape": "round", "d": 42}
    r = guard(gp, sides="left", post_shape="custom", post_custom_profile=[(0, 0), (30, 0), (15, 40)])
    assert r["posts"][0]["profile"]["shape"] == "custom"
    fascia = guard(gp, sides="left", post_mount="fascia", fascia_drop=200, fascia_offset=40, post_size=50)
    assert fascia["posts"][0]["base"][2] == pytest.approx(0)          # 200 below tread 1
    assert fascia["posts"][0]["base"][1] == pytest.approx(450 + 40 + 25)  # outside the stringer
    emb = guard(gp, sides="left", post_mount="embedded", embed_depth=100)
    assert emb["posts"][0]["base"][2] == pytest.approx(100)
    rot = guard(gp, sides="left", post_rotation=45)
    assert rot["posts"][0]["rotation_deg"] == pytest.approx(45)


# --- infill ------------------------------------------------------------------------------------
def test_balusters_respect_sphere(straight):
    g = guard(straight["guard_path"], sides="left", infill="balusters", baluster_spacing=100,
              baluster_size=20, post_rules=["max_spacing", "ends"], post_max_spacing=1200)
    assert g["info"]["max_infill_clear"] <= 100 + 1e-6
    assert g["infill"]["balusters"][0]["bottom"][2] < 300          # lands on the nosing line
    assert g["info"]["baluster_count"] > 20
    assert not any(w.startswith("OPENING") for w in g["warnings"])
    b = g["infill"]["balusters"][0]
    assert b["top"][2] > b["bottom"][2] and b["top"][0] == b["bottom"][0]
    wide = guard(straight["guard_path"], sides="left", infill="balusters", baluster_spacing=150,
                 post_rules=["max_spacing", "ends"])
    assert any(w.startswith("OPENING") for w in wide["warnings"])


def test_balusters_per_tread(straight):
    g = guard(straight["guard_path"], sides="left", infill="balusters", balusters_per_tread=2,
              post_rules=["ends"])
    assert g["info"]["baluster_count"] == 2 * 12          # treads whose centre lies between the posts
    assert any(w.startswith("OPENING") for w in g["warnings"])   # 2 per 280 mm tread is too few


def test_horizontal_bars_and_climbable(straight):
    g = guard(straight["guard_path"], sides="left", infill="horizontal", bar_spacing=100,
              bar_size=12, post_rules=["ends"])
    assert g["infill"]["bars"] and g["info"]["max_infill_clear"] <= 100 + 1e-6
    assert any(w.startswith("CLIMBABLE") for w in g["warnings"])
    bar = g["infill"]["bars"][0]["polyline"]
    assert len(bar) >= 2 and bar[-1][2] > bar[0][2]            # follows the slope
    n = guard(straight["guard_path"], sides="left", infill="horizontal", bar_count=3,
              post_rules=["ends"])
    assert len(n["infill"]["bars"]) == 3


def test_cable_infill(straight):
    g = guard(straight["guard_path"], sides="left", infill="cable", cable_spacing=80,
              post_rules=["max_spacing", "ends"])
    assert g["infill"]["cables"] and g["infill"]["cables"][0]["profile"]["shape"] == "round"
    assert any(b["part"] == "cable" for b in g["bom"])


def test_glass_panels(straight):
    g = guard(straight["guard_path"], sides="left", infill="glass", glass_thk=10, glass_gap=15,
              post_rules=["max_spacing", "ends"], post_max_spacing=1200)
    panels = g["infill"]["panels"]
    assert panels and all(q["thickness"] == 10 for q in panels)
    assert g["info"]["glass_area_m2"] > 0.5
    assert g["infill"]["clamps"]
    assert any(b["part"] == "glass panel" for b in g["bom"])
    poly = panels[0]["polygon"]
    assert len(poly) >= 4 and max(zlist(poly)) > min(zlist(poly)) + 500


def test_mesh_panels(straight):
    g = guard(straight["guard_path"], sides="left", infill="mesh", post_rules=["max_spacing", "ends"])
    assert g["infill"]["panels"] and g["infill"]["frames"]
    assert g["infill"]["panels"][0]["kind"] == "mesh"


def test_no_infill(straight):
    g = guard(straight["guard_path"], sides="left", infill="none")
    assert g["info"]["baluster_count"] == 0 and g["info"]["panel_count"] == 0


# --- handrail ------------------------------------------------------------------------------------
def test_handrail_extensions_and_returns(straight):
    g = guard(straight["guard_path"], sides="left", handrail=True, handrail_height=900,
              handrail_ext_top=300, handrail_ext_bottom=300, handrail_returns=True,
              handrail_offset=75, handrail_size=42)
    hr = g["handrail"][0]
    poly, kinds = hr["polyline"], hr["kinds"]
    assert kinds[0] == "return" and kinds[-1] == "return"
    assert kinds[1] == "level" and kinds[-2] == "level"
    # bottom extension: 300 mm back from the first nosing, level
    assert poly[1][0] == pytest.approx(-25 - 300) and poly[1][2] == pytest.approx(poly[2][2])
    # top extension: 300 mm beyond the floor edge
    assert poly[-2][0] == pytest.approx(13 * 280 + 300)
    # return towards the wall (outward = +Y on the left side)
    assert poly[0][1] == pytest.approx(poly[1][1] + 75)
    # handrail 75 mm in from the edge
    assert poly[2][1] == pytest.approx(450 - 75)
    assert g["brackets"] and all(b["direction"][1] > 0 for b in g["brackets"])
    assert g["info"]["handrail_height"] == 900
    off = guard(straight["guard_path"], sides="left", handrail=True, handrail_ext_top=0,
                handrail_ext_bottom=0, handrail_returns=False)
    assert "return" not in off["handrail"][0]["kinds"]


def test_handrail_height_check(straight):
    g = guard(straight["guard_path"], sides="left", handrail=True, handrail_height=800)
    assert any(w.startswith("HANDRAIL_HEIGHT") for w in g["warnings"])
    g = guard(straight["guard_path"], sides="left", handrail=True)
    assert g["info"]["handrail_height"] == pytest.approx(915)
    assert not any(w.startswith("HANDRAIL_HEIGHT") for w in g["warnings"])


def test_handrail_sides(l_stair):
    g = guard(l_stair["guard_path"], sides="both", handrail=True, handrail_sides="left")
    assert len(g["handrail"]) == 1 and g["handrail"][0]["side"] == "left"


# --- code checks -----------------------------------------------------------------------------------
def test_guard_height_check(straight):
    g = guard(straight["guard_path"], sides="left", height_flight=850)
    assert any(w.startswith("GUARD_HEIGHT") for w in g["warnings"])
    assert all("verify" in w for w in g["warnings"])
    g = guard(straight["guard_path"], sides="left", height_flight=900, context="other")
    assert any("1070" in w for w in g["warnings"])


def test_triangle_check(straight):
    g = guard(straight["guard_path"], sides="left", bottom_rail=True, bottom_gap=150, infill="glass")
    assert any(w.startswith("TRIANGLE") for w in g["warnings"])
    g = guard(straight["guard_path"], sides="left", bottom_rail=True, bottom_gap=0, infill="glass")
    assert not any(w.startswith("TRIANGLE") for w in g["warnings"])   # 280/200 legs: 136 mm sphere


def test_bottom_gap_opening_on_landing(l_stair):
    g = guard(l_stair["guard_path"], sides="right", bottom_rail=True, bottom_gap=120, infill="glass")
    assert any(w.startswith("OPENING") and "landings" in w for w in g["warnings"])
    assert any(w.startswith("CLIMBABLE") for w in g["warnings"]) is False   # 120 < 140


def test_bottom_rail_in_climbable_zone(straight):
    g = guard(straight["guard_path"], sides="left", bottom_rail=True, bottom_gap=200, infill="none")
    assert any(w.startswith("CLIMBABLE") for w in g["warnings"])


def test_warning_index_matches(straight):
    g = guard(straight["guard_path"], sides="left", height_flight=800, bottom_rail=True,
              bottom_gap=150, infill="glass")
    assert len(g["warning_index"]) == len(g["warnings"]) >= 2


def test_rules_override(straight):
    g = build_guard(GuardParams(guard_path=straight["guard_path"], sides="left", height_flight=950,
                                rules={"guard_height_residential_mm": 1000}))
    assert any(w.startswith("GUARD_HEIGHT") for w in g["warnings"])


# --- every stair type ------------------------------------------------------------------------------
@pytest.mark.parametrize("stair_type,winders", [("straight", False), ("L", False), ("L", True),
                                                ("U", False), ("U", True), ("U2", False),
                                                ("U2", True), ("spiral", False)])
@pytest.mark.parametrize("turn", ["left", "right"])
def test_every_type_builds_both_sides(stair_type, winders, turn):
    st = stair(stair_type=stair_type, winders=winders, well_gap=0, turn=turn)
    g = guard(st["guard_path"], sides="both", handrail=True, infill="balusters",
              post_rules=["every_step", "max_spacing", "corners", "ends"])
    assert len(g["top_rail"]) == 2 and len(g["handrail"]) == 2
    per_side = g["info"]["posts_per_side"].values()
    n_tr, n_w = st["info"]["n_treads"], st["info"]["n_winders"]
    # outer side: a post on every tread and winder plus the top end; inner side: winders
    # collapse onto the newel (and a spiral's inner side is a 60 mm column)
    assert max(per_side) >= n_tr + n_w + 1
    if stair_type != "spiral":
        assert min(per_side) >= n_tr + 1
    for rail in g["top_rail"] + g["bottom_rail"]:
        zs = zlist(rail["polyline"])
        assert all(b >= a - 1e-6 for a, b in zip(zs, zs[1:]))
        assert zs[0] == pytest.approx(st["info"]["rise"] + g["info"]["height_flight"] - 20) or \
            zs[0] == pytest.approx(st["info"]["rise"] + 90 + 15)
        assert zs[-1] == pytest.approx(2800 + g["info"]["height_landing"] - 20) or \
            zs[-1] == pytest.approx(2800 + 90 + 15) or st["info"]["stair_type"] == "spiral"
    for q in g["posts"]:
        assert q["top"][2] > q["base"][2] + 500
    assert not any(w.startswith("OPENING") for w in g["warnings"])
    assert g["bom"][0]["part"] == "post"


def test_u2_landing_corner_posts():
    st = stair(stair_type="U2")
    g = guard(st["guard_path"], sides="both", post_rules=["ends"])
    corners = [q for q in g["posts"] if q["reason"] == "corner"]
    assert len(corners) == 4


def test_winder_newel_is_a_corner():
    st = stair(stair_type="L", winders=True)
    paths = side_paths_from_stair(st["guard_path"], "left")
    assert kinks(paths[0])
    g = guard(st["guard_path"], sides="left", post_rules=["ends"])
    assert any(q["reason"] == "corner" for q in g["posts"])


# --- curve mode --------------------------------------------------------------------------------------
def test_closed_curve_guard():
    g = build_guard(GuardParams(mode="curve", curves=[[(0, 0, 0), (3000, 0, 0), (3000, 2000, 0),
                                                        (0, 2000, 0)]], curves_closed=[True],
                                post_rules=["max_spacing", "corners"], post_max_spacing=1000,
                                infill="balusters"))
    assert g["info"]["post_count"] >= 10
    reasons = {q["reason"] for q in g["posts"]}
    assert "corner" in reasons and "end" not in reasons
    rail = g["top_rail"][0]["polyline"]
    assert rail[0] == pytest.approx(rail[-1])               # closed loop
    assert all(abs(z - 880) < 1e-6 for z in zlist(rail))
    assert g["info"]["max_post_spacing"] <= 1000 + 1e-6


def test_open_3d_curve_guard_follows_surface():
    curve = [(0, 0, 0), (1000, 0, 0), (2000, 0, 300), (3000, 500, 600)]
    g = build_guard(GuardParams(mode="curve", curves=[curve], post_rules=["max_spacing", "corners", "ends"],
                                post_max_spacing=800, handrail=True, infill="glass"))
    rail = g["top_rail"][0]["polyline"]
    assert rail[0][2] == pytest.approx(880) and rail[-1][2] == pytest.approx(600 + 880)
    assert any(q["reason"] == "corner" for q in g["posts"])    # the 26 degree bend
    assert g["posts"][0]["base"] == pytest.approx((0, 25, 0))   # outward = right (-Y): inset moves to +Y
    assert g["handrail"] and g["infill"]["panels"]


def test_curve_outward_side_flips_inset():
    curve = [(0, 0, 0), (2000, 0, 0)]
    r = build_guard(GuardParams(mode="curve", curves=[curve], curve_outward="right", post_size=50))
    l = build_guard(GuardParams(mode="curve", curves=[curve], curve_outward="left", post_size=50))
    assert r["posts"][0]["base"][1] == pytest.approx(25) and l["posts"][0]["base"][1] == pytest.approx(-25)


def test_two_curves_make_two_guards():
    g = build_guard(GuardParams(mode="curve", curves=[[(0, 0, 0), (1000, 0, 0)],
                                                       [(0, 500, 0), (1000, 500, 0)]]))
    assert len(g["top_rail"]) == 2 and g["info"]["sides"] == ["curve0", "curve1"]


# --- errors and edge cases ----------------------------------------------------------------------------
@pytest.mark.parametrize("kw", [
    dict(mode="stair", guard_path=None), dict(mode="curve", curves=[[(0, 0, 0)]]),
    dict(mode="curve", curves=[[(0, 0, 0), (1, 0, 0)]], curve_outward="up"),
    dict(mode="stair", guard_path={"sides": {}}, sides="middle"),
    dict(mode="curve", curves=[[(0, 0, 0), (1, 0, 0)]], post_size=0),
    dict(mode="curve", curves=[[(0, 0, 0), (1, 0, 0)]], infill="wire"),
    dict(mode="curve", curves=[[(0, 0, 0), (1, 0, 0)]], post_rules=["everywhere"]),
    dict(mode="curve", curves=[[(0, 0, 0), (1, 0, 0)]], post_shape="custom"),
    dict(mode="curve", curves=[[(0, 0, 0), (1, 0, 0)]], bottom_gap=-1),
    dict(mode="curve", curves=[[(0, 0, 0), (1, 0, 0)]], height_flight=0),
])
def test_bad_input_raises(kw):
    with pytest.raises(ValueError):
        build_guard(GuardParams(**kw))


def test_one_riser_stair_has_no_guard():
    st = stair(floor_to_floor=150)
    with pytest.raises(ValueError):
        guard(st["guard_path"], sides="both")


def test_tiny_curve_single_bay():
    g = build_guard(GuardParams(mode="curve", curves=[[(0, 0, 0), (60, 0, 0)]], post_size=50))
    assert len(g["posts"]) >= 1


def test_bom_contents(l_stair):
    g = guard(l_stair["guard_path"], sides="both", handrail=True, infill="balusters", bottom_rail=True)
    parts = {b["part"] for b in g["bom"]}
    assert {"post", "top rail", "bottom rail", "handrail", "handrail bracket", "baluster"} <= parts
    assert g["bom"][0]["count"] == g["info"]["post_count"]


def test_dict_input(straight):
    g = build_guard({"guard_path": straight["guard_path"], "sides": "left"})
    assert g["posts"]
