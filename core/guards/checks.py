"""Guard code checks: warnings + failing element index, never design changes."""
import math


def run_checks(p, limits, sides_out, info):
    warnings, idx = [], []

    def warn(code, text, limit_name=None, index=-1):
        src = limits.source(limit_name) if limit_name else ""
        warnings.append("{}: {}{}".format(code, text, " ({})".format(src) if src else ""))
        idx.append(int(index))

    sphere = limits.value("max_opening_sphere_mm")
    h_req = limits.value("guard_height_residential_mm" if p.context == "residential"
                         else "guard_height_other_mm")
    h_key = "guard_height_residential_mm" if p.context == "residential" else "guard_height_other_mm"
    if info["height_flight"] < h_req - 1e-6:
        warn("GUARD_HEIGHT", "guard height on flights {:.0f} mm < required {} mm".format(
            info["height_flight"], h_req), h_key)
    if info["height_landing"] < h_req - 1e-6:
        warn("GUARD_HEIGHT", "guard height on landings {:.0f} mm < required {} mm".format(
            info["height_landing"], h_req), h_key)
    if p.handrail:
        lo, hi = limits.value("handrail_height_min_mm"), limits.value("handrail_height_max_mm")
        if not (lo - 1e-6 <= info["handrail_height"] <= hi + 1e-6):
            warn("HANDRAIL_HEIGHT", "handrail height {:.0f} mm outside {}-{} mm".format(
                info["handrail_height"], lo, hi), "handrail_height_min_mm")
    for side in sides_out:
        name = side["side"]
        inf = side["infill"]
        if p.infill == "balusters" and inf["max_clear"] > sphere + 1e-6:
            warn("OPENING", "{}: clear spacing between balusters {:.0f} mm > {} mm sphere".format(
                name, inf["max_clear"], sphere), "max_opening_sphere_mm")
        if p.infill in ("horizontal", "cable") and inf["max_clear"] > sphere + 1e-6:
            warn("OPENING", "{}: clear spacing between {} {:.0f} mm > {} mm sphere".format(
                name, "bars" if p.infill == "horizontal" else "cables", inf["max_clear"], sphere),
                "max_opening_sphere_mm")
        if p.infill == "glass" and p.glass_gap * 2 > sphere + 1e-6:
            warn("OPENING", "{}: glass gap to posts {:.0f} mm each side > {} mm sphere".format(
                name, p.glass_gap, sphere), "max_opening_sphere_mm")
        # gap under the bottom element on landings (vertical) and on flights (perpendicular)
        bottom_gap = p.glass_bottom_gap if (p.infill == "glass" and not p.bottom_rail) else \
            (p.bottom_gap if (p.bottom_rail or p.infill == "glass") else None)
        if bottom_gap is not None and p.infill != "balusters":
            if bottom_gap > sphere + 1e-6 and side["has_level"]:
                warn("OPENING", "{}: gap under the bottom rail {:.0f} mm > {} mm sphere on landings".format(
                    name, bottom_gap, sphere), "max_opening_sphere_mm")
            for fl in side["flights"]:
                perp = bottom_gap * math.cos(math.atan(fl["slope"]))
                if perp > sphere + 1e-6:
                    warn("OPENING", "{}: gap under the bottom rail {:.0f} mm (perpendicular) > {} mm "
                         "sphere on flight {}".format(name, perp, sphere, fl["flight"]),
                         "max_opening_sphere_mm", fl["first_step"])
                    break
        # triangle under the bottom rail on stairs: largest sphere between rail, tread and riser
        if bottom_gap is not None and limits.has("stair_triangle_sphere_mm"):
            tri = limits.value("stair_triangle_sphere_mm")
            for fl in side["flights"]:
                if fl["rise"] <= 0 or fl["run"] <= 0:
                    continue
                m = fl["rise"] / fl["run"]
                r = (fl["rise"] + bottom_gap) / (1.0 + m + math.sqrt(1.0 + m * m))
                if 2 * r > tri + 1e-6:
                    warn("TRIANGLE", "{}: opening between bottom rail, tread and riser passes a "
                         "{:.0f} mm sphere > {} mm on flight {}".format(name, 2 * r, tri, fl["flight"]),
                         "stair_triangle_sphere_mm", fl["first_step"])
                    break
        # climbable horizontal elements
        lo, hi = limits.value("climbable_zone_low_mm"), limits.value("climbable_zone_high_mm")
        if p.infill in ("horizontal", "cable"):
            heights = [b["height_above_surface"] + (p.bottom_gap + p.bottom_rail_h if p.bottom_rail else 0)
                       for b in (inf["bars"] + inf["cables"])]
            if any(lo <= h <= hi for h in heights):
                warn("CLIMBABLE", "{}: horizontal infill between {} and {} mm above the surface "
                     "could be climbable".format(name, lo, hi), "climbable_zone_low_mm")
        if p.bottom_rail and lo <= p.bottom_gap <= hi:
            warn("CLIMBABLE", "{}: bottom rail {:.0f} mm above the surface is within the climbable "
                 "zone {}-{} mm".format(name, p.bottom_gap, lo, hi), "climbable_zone_low_mm")
    return warnings, idx
