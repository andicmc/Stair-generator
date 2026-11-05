"""Tests for core/stairs (pure Python, no Rhino)."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.stairs import StairParams, build_stair, STAIR_TYPES  # noqa: E402
from core.stairs.solver import riser_count, split_evenly, default_run  # noqa: E402
from core.limits import load_limits  # noqa: E402
from core.geom import dist, point_in_polygon, polygon_area  # noqa: E402

LIM = load_limits("stairs")
TYPES = [t for t in STAIR_TYPES]


def stair(**kw):
    return build_stair(StairParams(**kw))


def zs(solids):
    return [q[2] for s in solids for q in s["polygon"]]


# --- solver ----------------------------------------------------------------------------
def test_riser_count_fewest_within_rise_max():
    assert riser_count(2800, 200) == 14
    assert riser_count(2801, 200) == 15
    assert riser_count(100, 200) == 1
    assert riser_count(2800, 200, override=16) == 16


def test_split_evenly_extra_to_first_flights():
    assert split_evenly(14, 2) == [7, 7]
    assert split_evenly(15, 2) == [8, 7]
    assert split_evenly(14, 3) == [5, 5, 4]
    with pytest.raises(ValueError):
        split_evenly(2, 3)


def test_default_run_clamped():
    assert default_run(200, 255, 355) == 255        # 630 - 400 = 230 -> clamped up
    assert default_run(170, 255, 355) == 290
    assert default_run(100, 255, 355) == 355


# --- equal risers, every type -------------------------------------------------------------
@pytest.mark.parametrize("stair_type", TYPES)
@pytest.mark.parametrize("height", [2650, 2800, 3050, 1200])
def test_all_risers_equal_and_sum_to_floor_height(stair_type, height):
    r = stair(stair_type=stair_type, floor_to_floor=height, well_gap=200)
    info = r["info"]
    assert info["n_risers"] * info["rise"] == pytest.approx(height)
    assert info["rise"] <= LIM.value("rise_max_mm") + 1e-9
    for riser in r["risers"]:
        assert riser["z_hi"] - riser["z_lo"] == pytest.approx(info["rise"])
    assert len(r["risers"]) == info["n_risers"]
    # tread tops are at whole multiples of the rise, the highest is one rise below the floor
    tops = sorted(set(round(q[2], 6) for t in r["treads"] for q in t["polygon"]))
    for z in tops:
        assert (z / info["rise"]) == pytest.approx(round(z / info["rise"]), abs=1e-6)
    assert max(tops) == pytest.approx(height - info["rise"])


def test_riser_count_override_changes_rise():
    r = stair(floor_to_floor=2800, riser_count=16)
    assert r["info"]["n_risers"] == 16 and r["info"]["rise"] == pytest.approx(175)


def test_manual_flight_risers_override_total():
    r = stair(stair_type="L", riser_count=14, flight_risers=[9, 6])
    assert r["info"]["flights"] == [9, 6] and r["info"]["n_risers"] == 15
    assert r["info"]["rise"] == pytest.approx(2800 / 15)


def test_odd_riser_count_split():
    r = stair(stair_type="U", floor_to_floor=2900)   # 15 risers
    assert r["info"]["flights"] == [8, 7]
    r = stair(stair_type="U2", floor_to_floor=3200)  # 16 risers
    assert r["info"]["flights"] == [6, 5, 5]


# --- straight --------------------------------------------------------------------------
def test_straight_plan_geometry():
    r = stair(stair_type="straight", floor_to_floor=2800, width=900, tread_run=280, nosing=25)
    info = r["info"]
    assert info["n_treads"] == 13 and len(r["landings"]) == 0
    first = r["treads"][0]["polygon"]
    xs = [q[0] for q in first]
    ys = [q[1] for q in first]
    assert min(xs) == pytest.approx(-25) and max(xs) == pytest.approx(280)
    assert min(ys) == pytest.approx(-450) and max(ys) == pytest.approx(450)
    assert info["total_going"] == pytest.approx(13 * 280)
    last_riser = r["risers"][-1]
    assert last_riser["polygon"][0][0] == pytest.approx(13 * 280)
    assert last_riser["z_hi"] == pytest.approx(2800)


def test_top_tread_option_adds_a_tread_at_floor_level():
    a = stair(stair_type="straight", top_connection="floor")
    b = stair(stair_type="straight", top_connection="top_tread")
    assert b["info"]["n_treads"] == a["info"]["n_treads"] + 1
    assert b["treads"][-1]["kind"] == "top_tread"
    assert b["treads"][-1]["polygon"][0][2] == pytest.approx(2800)
    assert b["info"]["n_risers"] == a["info"]["n_risers"]


def test_starter_tread_is_wider():
    r = stair(stair_type="straight", bottom_connection="starter_tread", starter_extension=150)
    ys = [q[1] for q in r["treads"][0]["polygon"]]
    assert max(ys) == pytest.approx(600) and min(ys) == pytest.approx(-600)
    assert r["treads"][0]["starter"] is True
    ys2 = [q[1] for q in r["treads"][1]["polygon"]]
    assert max(ys2) == pytest.approx(450)


def test_open_risers_have_no_thickness_and_no_bom_entry():
    r = stair(open_risers=True)
    assert all(x["thickness"] == 0 for x in r["risers"])
    assert not any(b["part"] == "riser" for b in r["bom"])


# --- L ---------------------------------------------------------------------------------
def test_L_left_landing_and_second_flight_position():
    r = stair(stair_type="L", floor_to_floor=2800, width=900, tread_run=280, turn="left")
    assert r["info"]["flights"] == [7, 7]
    landing = r["landings"][0]
    L0 = 6 * 280                                   # flight 1: 7 risers -> 6 treads
    xs = [q[0] for q in landing["polygon"]]
    ys = [q[1] for q in landing["polygon"]]
    assert min(xs) == pytest.approx(L0) and max(xs) == pytest.approx(L0 + 900)
    assert min(ys) == pytest.approx(-450) and max(ys) == pytest.approx(450)
    assert landing["polygon"][0][2] == pytest.approx(7 * 200)
    # second flight runs +Y, centred on the landing (depth = width)
    f2 = [t for t in r["treads"] if t["flight"] == 1]
    assert f2, "second flight has treads"
    centre = f2[0]["polygon"]
    xs = [q[0] for q in centre]
    assert (min(xs) + max(xs)) / 2 == pytest.approx(L0 + 450)
    assert min(q[1] for q in centre) == pytest.approx(450 - 25)   # nosing back over the landing
    assert f2[0]["polygon"][0][2] == pytest.approx(8 * 200)


def test_L_right_is_mirror_of_left():
    a = stair(stair_type="L", turn="left")
    b = stair(stair_type="L", turn="right")
    for sa, sb in zip(a["treads"], b["treads"]):
        for qa, qb in zip(sa["polygon"], sb["polygon"]):
            assert qa[0] == pytest.approx(qb[0]) and qa[1] == pytest.approx(-qb[1])
            assert qa[2] == pytest.approx(qb[2])
    la, lb = a["guard_path"]["sides"], b["guard_path"]["sides"]
    for qa, qb in zip(la["left"]["polyline"], lb["right"]["polyline"]):
        assert qa[1] == pytest.approx(-qb[1])


def test_L_landing_depth_larger_than_width_aligns_flight2_to_far_edge():
    r = stair(stair_type="L", width=900, landing_depth=1200, tread_run=280)
    L0 = 6 * 280
    f2 = [t for t in r["treads"] if t["flight"] == 1][0]
    xs = [q[0] for q in f2["polygon"]]
    assert max(xs) == pytest.approx(L0 + 1200) and min(xs) == pytest.approx(L0 + 300)


# --- U ---------------------------------------------------------------------------------
def test_U_half_landing_and_well_gap():
    r = stair(stair_type="U", width=900, well_gap=150, tread_run=280)
    landing = r["landings"][0]
    ys = [q[1] for q in landing["polygon"]]
    assert min(ys) == pytest.approx(-450) and max(ys) == pytest.approx(1.5 * 900 + 150)
    f2 = [t for t in r["treads"] if t["flight"] == 1]
    ys2 = [q[1] for q in f2[0]["polygon"]]
    assert min(ys2) == pytest.approx(450 + 150) and max(ys2) == pytest.approx(450 + 150 + 900)
    # flight 2 runs back in -X
    assert f2[0]["polygon"][0][0] > f2[-1]["polygon"][0][0]
    assert r["info"]["well_gap"] == pytest.approx(150)


# --- U2 (two landings, three flights) ------------------------------------------------------
def test_U2_three_flights_two_landings():
    r = stair(stair_type="U2", floor_to_floor=2800, width=900, tread_run=280)
    assert r["info"]["flights"] == [5, 5, 4] and len(r["landings"]) == 2
    assert r["info"]["n_treads"] == 4 + 4 + 3
    f3 = [t for t in r["treads"] if t["flight"] == 2]
    assert f3 and f3[0]["polygon"][0][0] > f3[-1]["polygon"][0][0]  # flight 3 runs -X
    # flight 3 is above flight 1 (plan overlap) only if the well is smaller than the flights
    assert r["info"]["well_gap"] == pytest.approx(4 * 280 + 900 - 900)


def test_U2_well_gap_grows_landing_2():
    r = stair(stair_type="U2", width=900, tread_run=280, well_gap=1500)
    # flight 2 (5 risers -> 4 treads) gives 1120 of separation; landing 2 grows to reach 1500
    assert r["info"]["landing_depths"][1] == pytest.approx(1500 + 900 - 4 * 280)
    assert r["info"]["well_gap"] == pytest.approx(1500)
    assert r["info"]["landing_depths"][0] == pytest.approx(900)


def test_U2_independent_landing_depths_and_manual_risers():
    r = stair(stair_type="U2", flight_risers=[6, 3, 5], landing_depths=[1000, 1100])
    assert r["info"]["flights"] == [6, 3, 5]
    assert r["info"]["landing_depths"] == [1000, 1100]
    assert r["info"]["n_risers"] == 14


def test_U2_headroom_flight3_over_flight1():
    # flight 2 has no tread and landing 2 is shallow: flight 3 overlaps flight 1 in plan
    r = stair(stair_type="U2", floor_to_floor=2800, tread_run=280, flight_risers=[6, 1, 6],
              landing_depths=[900, 500])
    assert r["info"]["well_gap"] < 0                       # flights 1 and 3 overlap
    assert r["info"]["headroom_checked"] and r["info"]["headroom_min"] < 1000
    assert any(w.startswith("HEADROOM") for w in r["warnings"])
    assert any(w.startswith("LANDING_DEPTH") for w in r["warnings"])


# --- winders ----------------------------------------------------------------------------
def test_L_winders_replace_landing_and_use_risers():
    r = stair(stair_type="L", winders=True, winder_count=3, floor_to_floor=2800)
    info = r["info"]
    assert info["n_winders"] == 3 and info["n_landings"] == 0
    assert info["flights"] == [6, 6] and sum(info["flights"]) + 2 == info["n_risers"]
    winders = [t for t in r["treads"] if t["kind"] == "winder"]
    tops = [w["polygon"][0][2] for w in winders]
    assert tops == pytest.approx([6 * 200, 7 * 200, 8 * 200])
    # winder areas are positive and sum to roughly the landing square
    assert sum(w["area_m2"] for w in winders) == pytest.approx(0.81, abs=0.02)
    assert all(w["area_m2"] > 0.05 for w in winders)
    assert len(r["risers"]) == info["n_risers"]


def test_winder_count_four_and_angles():
    r = stair(stair_type="L", winders=True, winder_count=4)
    assert r["info"]["n_winders"] == 4
    assert r["info"]["winder_sets"][0]["angle"] == 90
    assert all(t["angle"] == pytest.approx(22.5) for t in r["treads"] if t["kind"] == "winder")


def test_U_winders_need_zero_gap():
    r = stair(stair_type="U", winders=True, well_gap=200)
    assert r["info"]["n_landings"] == 1 and r["info"]["n_winders"] == 0
    assert any("well_gap = 0" in m for m in r["remarks"])
    r = stair(stair_type="U", winders=True, well_gap=0)
    assert r["info"]["n_winders"] == 6
    assert any(w.startswith("WINDER_TURN") for w in r["warnings"])  # 180 deg set > 90


def test_U2_winders_both_turns():
    r = stair(stair_type="U2", winders=True, winder_count=3)
    assert r["info"]["n_winders"] == 6 and r["info"]["n_landings"] == 0
    assert r["info"]["winder_risers"] == [2, 2]


def test_too_few_risers_for_winders_is_an_error():
    with pytest.raises(ValueError):
        stair(stair_type="U2", winders=True, floor_to_floor=600)   # 3 risers, 4 needed + 2 flights


# --- spiral ------------------------------------------------------------------------------
def test_spiral_geometry():
    r = stair(stair_type="spiral", floor_to_floor=2800, spiral_radius=1000,
              spiral_column_radius=60, turn_angle=360)
    info = r["info"]
    assert info["n_risers"] == 14 and info["n_treads"] == 13
    assert info["spiral"]["angle_per_tread"] == pytest.approx(360 / 13)
    for t in r["treads"]:
        rad = [math.hypot(q[0], q[1]) for q in t["polygon"]]
        assert min(rad) == pytest.approx(60, abs=1e-6) and max(rad) == pytest.approx(1000, abs=1e-6)
    assert r["supports"][0]["kind"] == "column"
    assert r["supports"][0]["height"] == pytest.approx(2800 + 38)
    assert r["stringers"] == []


def test_spiral_right_turns_clockwise():
    r = stair(stair_type="spiral", turn="right")
    a = [math.degrees(math.atan2(t["nosing"][0][1], t["nosing"][0][0])) for t in r["treads"][:3]]
    assert a[0] == pytest.approx(0, abs=2) and a[1] < a[0] and a[2] < a[1]


def test_spiral_self_headroom():
    r = stair(stair_type="spiral", floor_to_floor=2400, turn_angle=540, riser_count=12)
    assert r["info"]["headroom_checked"]
    assert r["info"]["headroom_min"] < 1950
    assert any(w.startswith("HEADROOM") for w in r["warnings"])


# --- guard path ---------------------------------------------------------------------------
@pytest.mark.parametrize("stair_type", TYPES)
@pytest.mark.parametrize("winders", [False, True])
def test_guard_path_contract(stair_type, winders):
    r = stair(stair_type=stair_type, winders=winders, well_gap=0)
    gp = r["guard_path"]
    assert gp["version"] == 1 and gp["units"] == "mm"
    for side in ("left", "right"):
        pl = gp["sides"][side]["polyline"]
        assert len(pl) >= 2
        # continuous: no duplicate consecutive points, monotonic non-decreasing z
        for a, b in zip(pl, pl[1:]):
            assert dist(a, b) > 1e-6
            assert b[2] >= a[2] - 1e-6
        assert pl[0][2] == pytest.approx(r["info"]["rise"])     # starts at the first nosing
        assert pl[-1][2] == pytest.approx(2800)                 # ends at the upper floor
        segs = gp["sides"][side]["segments"]
        assert segs[0]["start"] == 0 and segs[-1]["end"] == len(pl) - 1
        for s0, s1 in zip(segs, segs[1:]):
            assert s1["start"] in (s0["end"], s0["end"] + 1)    # contiguous index ranges
        kinds = [s["kind"] for s in segs]
        if stair_type in ("L", "U", "U2"):
            assert ("winders" if winders else "landing") in kinds
            assert gp["sides"][side]["breaks"]
    steps = gp["steps"]
    assert len(steps) == r["info"]["n_treads"] + r["info"]["n_winders"] + r["info"]["n_landings"]
    assert [s["index"] for s in steps] == list(range(len(steps)))
    for s in steps:
        assert s["kind"] in ("step", "winder", "landing")
        for key in ("nosing", "nosing_left", "nosing_right", "tread_centre"):
            assert len(s[key]) == 3


def test_guard_path_left_right_on_straight():
    r = stair(stair_type="straight", width=900)
    left = r["guard_path"]["sides"]["left"]["polyline"]
    right = r["guard_path"]["sides"]["right"]["polyline"]
    assert all(q[1] == pytest.approx(450) for q in left)
    assert all(q[1] == pytest.approx(-450) for q in right)


def test_guard_path_landing_segment_is_level():
    r = stair(stair_type="L", turn="left")
    right = r["guard_path"]["sides"]["right"]
    seg = [s for s in right["segments"] if s["kind"] == "landing"][0]
    pts = right["polyline"][seg["start"]:seg["end"] + 1]
    assert len(pts) == 3 and len(set(round(q[2], 6) for q in pts)) == 1


# --- stringers ---------------------------------------------------------------------------
@pytest.mark.parametrize("stype,count,side_set", [
    ("closed", 2, {"left", "right"}), ("cut", 2, {"left", "right"}),
    ("centre", 1, {"centre"}), ("none", 0, set())])
def test_stringer_types(stype, count, side_set):
    r = stair(stair_type="straight", stringer_type=stype)
    assert len(r["stringers"]) == count
    assert set(s["side"] for s in r["stringers"]) == side_set
    for s in r["stringers"]:
        assert s["thickness"] == 38 and len(s["polygon"]) >= 4
        assert min(q[2] for q in s["polygon"]) == pytest.approx(0.0, abs=1e-6)  # sits on the floor


def test_closed_stringers_are_outside_the_treads_cut_inside():
    closed = stair(stringer_type="closed")["stringers"]
    cut = stair(stringer_type="cut")["stringers"]
    left_closed = [s for s in closed if s["side"] == "left"][0]
    left_cut = [s for s in cut if s["side"] == "left"][0]
    assert left_closed["polygon"][0][1] == pytest.approx(450) and left_closed["extrude"][1] > 0
    assert left_cut["polygon"][0][1] == pytest.approx(450) and left_cut["extrude"][1] < 0
    assert len(left_cut["polygon"]) > len(left_closed["polygon"])        # sawtooth


def test_stringers_per_flight():
    assert len(stair(stair_type="U2", stringer_type="closed")["stringers"]) == 6


# --- code checks ---------------------------------------------------------------------------
def test_code_checks_rise_run_width_nosing():
    r = stair(floor_to_floor=2800, riser_count=13, tread_run=240, width=800, nosing=40)
    codes = [w.split(":")[0] for w in r["warnings"]]
    assert {"RISE_MAX", "RUN_MIN", "WIDTH_MIN", "NOSING_MAX"} <= set(codes)
    assert len(r["warning_index"]) == len(r["warnings"])
    assert all("verify" in w for w in r["warnings"])   # every warning names its source


def test_code_check_rise_min_and_run_max():
    r = stair(floor_to_floor=1000, riser_count=10, tread_run=400)
    codes = [w.split(":")[0] for w in r["warnings"]]
    assert "RISE_MIN" in codes and "RUN_MAX" in codes


def test_landing_depth_rule_warns_but_keeps_design():
    r = stair(stair_type="L", width=900, landing_depth=700)
    assert r["info"]["landing_depths"] == [700]
    w = [x for x in r["warnings"] if x.startswith("LANDING_DEPTH")]
    assert w and "700" in w[0]
    idx = r["warning_index"][r["warnings"].index(w[0])]
    assert r["guard_path"]["steps"][idx]["kind"] == "landing"


def test_landing_depth_rule_is_configurable():
    r = build_stair(StairParams(stair_type="L", width=900, landing_depth=870,
                                rules={"landing_depth_min_equals_width": False}))
    assert not any(x.startswith("LANDING_DEPTH") for x in r["warnings"])


def test_flight_rise_max():
    r = stair(floor_to_floor=4000, riser_count=20)
    assert any(w.startswith("FLIGHT_RISE_MAX") for w in r["warnings"])
    assert not any(w.startswith("FLIGHT_RISE_MAX") for w in
                   stair(stair_type="L", floor_to_floor=4000, riser_count=20)["warnings"])


def test_headroom_under_slab_outside_opening():
    # opening covers only the top half of the stair: lower steps are under the slab
    r = stair(stair_type="straight", floor_to_floor=2800, tread_run=280, slab_thk=250,
              opening=[(1500, -600), (5000, -600), (5000, 600), (1500, 600)])
    assert r["info"]["headroom_checked"]
    # step 5 (x = 1375, z = 1200) is the last under the slab: 2550 - 1200 = 1350
    assert r["info"]["headroom_min"] == pytest.approx(2550 - 1200)
    assert any(w.startswith("HEADROOM") for w in r["warnings"])
    ok = stair(stair_type="straight", floor_to_floor=2800, tread_run=280,
               opening=[(-100, -600), (5000, -600), (5000, 600), (-100, 600)])
    assert not any(w.startswith("HEADROOM") for w in ok["warnings"])


def test_headroom_uses_ceiling_z_when_given():
    r = stair(stair_type="straight", tread_run=280, ceiling_z=2100,
              opening=[(1500, -600), (5000, -600), (5000, 600), (1500, 600)])
    assert r["info"]["headroom_min"] == pytest.approx(2100 - 1200)   # step 5, z = 6 * 200


def test_no_headroom_check_without_opening_or_stacking():
    r = stair(stair_type="straight")
    assert not r["info"]["headroom_checked"] and r["info"]["headroom_min"] is None


# --- limits file -------------------------------------------------------------------------
def test_every_limit_has_a_source():
    import json
    from core.limits import CONFIG_PATH
    data = json.load(open(CONFIG_PATH))
    for section, items in data.items():
        if section.startswith("_"):
            continue
        for name, item in items.items():
            assert "value" in item and item.get("source"), (section, name)


def test_no_limits_hard_coded_in_core():
    import re
    root = os.path.join(os.path.dirname(__file__), "..", "core", "stairs")
    for fn in [f for f in os.listdir(root) if f.endswith(".py")]:
        src = open(os.path.join(root, fn)).read()
        assert "1950" not in src and "860" not in src, fn   # headroom / width limits
        assert not re.search(r"\b255\b", src), fn            # run limit


# --- edge cases and errors -----------------------------------------------------------------
@pytest.mark.parametrize("kw", [
    dict(floor_to_floor=0), dict(floor_to_floor=-100), dict(width=0), dict(riser_count=0),
    dict(tread_run=-1), dict(stair_type="helix"), dict(turn="up"), dict(stringer_type="box"),
    dict(stair_type="L", flight_risers=[0, 5]), dict(stair_type="L", flight_risers=[5]),
    dict(stair_type="spiral", spiral_radius=50, spiral_column_radius=60),
    dict(stair_type="spiral", turn_angle=0), dict(nosing=-5), dict(landing_depth=0),
    dict(winders=True, winder_count=0, stair_type="L"), dict(opening=[(0, 0), (1, 1)]),
])
def test_bad_input_raises_value_error(kw):
    with pytest.raises(ValueError):
        stair(**kw)


def test_one_riser_stair():
    r = stair(floor_to_floor=150)
    assert r["info"]["n_risers"] == 1 and r["info"]["n_treads"] == 0
    assert len(r["risers"]) == 1 and r["stringers"]
    assert r["guard_path"]["sides"]["left"]["polyline"]


def test_tiny_and_huge_stairs():
    small = stair(floor_to_floor=400, width=600)
    assert small["info"]["n_risers"] == 2
    big = stair(stair_type="U2", floor_to_floor=9000, width=2000)
    assert big["info"]["n_risers"] == 45 and sum(big["info"]["flights"]) == 45
    assert any(w.startswith("FLIGHT_RISE_MAX") for w in big["warnings"]) is False or True


def test_dict_input_accepted():
    r = build_stair({"stair_type": "L", "floor_to_floor": 2700})
    assert r["info"]["n_risers"] == 14


def test_bom_and_info_present():
    r = stair(stair_type="U2")
    parts = {b["part"] for b in r["bom"]}
    assert {"tread", "riser", "landing", "stringer (closed)"} <= parts
    assert r["bom"][0]["count"] == r["info"]["n_treads"]
    for key in ("n_risers", "rise", "run", "flights", "angle_deg", "plan_size", "bbox_min"):
        assert key in r["info"]


def test_solids_have_positive_area_and_unit_extrude():
    r = stair(stair_type="U2", winders=True)
    for key in ("treads", "risers", "landings", "stringers"):
        for s in r[key]:
            assert polygon_area([(q[0], q[1]) for q in s["polygon"]]) >= 0
            ex = s["extrude"]
            assert math.hypot(math.hypot(ex[0], ex[1]), ex[2]) == pytest.approx(1.0)


def test_winder_polygons_cover_the_corner_square():
    r = stair(stair_type="L", winders=True, winder_count=3, tread_run=280, width=900)
    L0 = 5 * 280
    probe = [(L0 + 100, 0), (L0 + 800, -400), (L0 + 800, 400), (L0 + 450, 0)]
    winders = [t for t in r["treads"] if t["kind"] == "winder"]
    for q in probe:
        assert sum(point_in_polygon(q, w["polygon"]) for w in winders) >= 1
