"""Code checks: warnings (strings) + the index of the failing step, never design changes."""
from ..geom import point_in_polygon, sub, dot, rot90


def run_checks(b, p, limits, info):
    warnings, idx = [], []

    def warn(code, text, limit_name=None, step=-1):
        src = limits.source(limit_name) if limit_name else ""
        warnings.append("{}: {}{}".format(code, text, " ({})".format(src) if src else ""))
        idx.append(int(step))

    rise, run = info["rise"], info["run"]
    if rise > limits.value("rise_max_mm"):
        warn("RISE_MAX", "rise {:.1f} mm > max {} mm".format(rise, limits.value("rise_max_mm")),
             "rise_max_mm")
    if rise < limits.value("rise_min_mm"):
        warn("RISE_MIN", "rise {:.1f} mm < min {} mm".format(rise, limits.value("rise_min_mm")),
             "rise_min_mm")
    if p.stair_type != "spiral":
        if run < limits.value("run_min_mm"):
            warn("RUN_MIN", "run {:.1f} mm < min {} mm".format(run, limits.value("run_min_mm")),
                 "run_min_mm")
        if limits.has("run_max_mm") and run > limits.value("run_max_mm"):
            warn("RUN_MAX", "run {:.1f} mm > max {} mm".format(run, limits.value("run_max_mm")),
                 "run_max_mm")
    if p.width < limits.value("width_min_mm"):
        warn("WIDTH_MIN", "width {:.0f} mm < min {} mm".format(p.width, limits.value("width_min_mm")),
             "width_min_mm")
    if p.nosing > limits.value("nosing_max_mm"):
        warn("NOSING_MAX", "nosing {:.0f} mm > max {} mm".format(p.nosing, limits.value("nosing_max_mm")),
             "nosing_max_mm")
    for i, fr in enumerate(info["flight_rise"]):
        if fr > limits.value("max_rise_per_flight_mm"):
            warn("FLIGHT_RISE_MAX", "flight {} rises {:.0f} mm > max {} mm between landings".format(
                i + 1, fr, limits.value("max_rise_per_flight_mm")), "max_rise_per_flight_mm",
                b.flights_meta[i]["first_step"] if i < len(b.flights_meta) else -1)
    # landings
    for lm in b.landings_meta:
        need = p.width if limits.value("landing_depth_min_equals_width") else 0.0
        need = max(need, limits.value("landing_depth_min_mm") if limits.has("landing_depth_min_mm") else 0.0)
        if lm["depth"] < need - 1e-6:
            warn("LANDING_DEPTH", "landing {} depth {:.0f} mm < required {:.0f} mm".format(
                lm["index"] + 1, lm["depth"], need), "landing_depth_min_equals_width",
                _landing_step(b, lm["index"]))
    # winders
    for ws in b.winder_sets:
        if ws["angle"] > limits.value("winder_max_turn_per_set_deg"):
            warn("WINDER_TURN", "winder set {} turns {:.0f} deg > max {} deg per set".format(
                ws["index"] + 1, ws["angle"], limits.value("winder_max_turn_per_set_deg")),
                "winder_max_turn_per_set_deg", ws["first_step"])
        if ws["walkline_run"] < limits.value("winder_min_run_at_walkline_mm"):
            warn("WINDER_RUN", "winder set {} run at the walk line {:.0f} mm < min {} mm".format(
                ws["index"] + 1, ws["walkline_run"], limits.value("winder_min_run_at_walkline_mm")),
                "winder_min_run_at_walkline_mm", ws["first_step"])
        per = ws["angle"] / ws["count"]
        if limits.has("winder_turn_per_tread_deg") and per > limits.value("winder_turn_per_tread_deg") + 1e-6:
            warn("WINDER_ANGLE", "winder set {}: {:.1f} deg per tread > {} deg".format(
                ws["index"] + 1, per, limits.value("winder_turn_per_tread_deg")),
                "winder_turn_per_tread_deg", ws["first_step"])
    # spiral
    if p.stair_type == "spiral":
        sp = info["spiral"]
        if sp["walkline_run"] < limits.value("spiral_min_run_at_walkline_mm"):
            warn("SPIRAL_RUN", "run at the walk line {:.0f} mm < min {} mm".format(
                sp["walkline_run"], limits.value("spiral_min_run_at_walkline_mm")),
                "spiral_min_run_at_walkline_mm")
    # headroom
    headroom = _headroom(b, p, limits)
    if headroom["checked"] and headroom["min"] is not None and \
            headroom["min"] < limits.value("headroom_min_mm"):
        warn("HEADROOM", "headroom {:.0f} mm < min {} mm at step {}".format(
            headroom["min"], limits.value("headroom_min_mm"), headroom["step"]),
            "headroom_min_mm", headroom["step"])
    return warnings, idx, headroom


def _landing_step(b, landing_index):
    for s in b.steps:
        if s["kind"] == "landing" and s.get("landing") == landing_index:
            return s["index"]
    return -1


def _soffit_above(b, p, q, z_walk):
    """Lowest soffit of any flight / landing / winder that is above the plan point q."""
    best = None
    for fm in b.flights_meta:
        if fm.get("spiral"):
            continue
        rel = sub((q[0], q[1]), fm["origin"])
        s, y = dot(rel, fm["dir"]), dot(rel, rot90(fm["dir"]))
        if -1e-6 <= s <= fm["plan_length"] + 1e-6 and abs(y) <= fm["width"] / 2 + p.stringer_thk:
            soffit = fm["z0"] + fm["rise"] + fm["rise"] / fm["run"] * s - fm["soffit_depth"]
            if soffit > z_walk + 1.0:
                best = soffit if best is None else min(best, soffit)
    for lm in b.landings_meta:
        if point_in_polygon(q, lm["polygon"]) and lm["soffit"] > z_walk + 1.0:
            best = lm["soffit"] if best is None else min(best, lm["soffit"])
    for ws in b.winder_sets:
        if point_in_polygon(q, ws["polygon_plan"]) and ws["soffit"] > z_walk + 1.0:
            best = ws["soffit"] if best is None else min(best, ws["soffit"])
    return best


def _headroom(b, p, limits):
    ceiling = p.ceiling_z if p.ceiling_z is not None else p.floor_to_floor - p.slab_thk
    use_ceiling = p.opening is not None
    result = {"min": None, "step": -1, "checked": False, "ceiling_z": ceiling,
              "ceiling_checked": use_ceiling}
    spiral = b.flights_meta[0] if p.stair_type == "spiral" else None
    for st in b.steps:
        points = [st["nosing"], st["tread_centre"]]
        if spiral is not None:
            # the tread one full turn above this step (walk line), if the stair turns that far
            j = int((st["index"] * spiral["dtheta"] + 360.0) // spiral["dtheta"] + 1e-9)
            if j < spiral["n_treads"]:
                h = (j + 1) * spiral["rise"] - p.tread_thk - st["z"]
                result["checked"] = True
                if result["min"] is None or h < result["min"]:
                    result["min"], result["step"] = h, st["index"]
        if st["kind"] == "landing":
            points = [st["tread_centre"], st["nosing"], st["nosing_left"], st["nosing_right"]]
        for q in points:
            z_walk = q[2]
            hs = []
            soffit = _soffit_above(b, p, q, z_walk)
            if soffit is not None:
                hs.append(soffit - z_walk)
            if use_ceiling and not point_in_polygon(q, p.opening) and ceiling > z_walk + 1.0:
                hs.append(ceiling - z_walk)
            for h in hs:
                result["checked"] = True
                if result["min"] is None or h < result["min"]:
                    result["min"], result["step"] = h, st["index"]
    return result
