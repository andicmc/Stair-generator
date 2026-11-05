"""Guard / railing core: posts, rails, handrail and infill along a stair or a curve.

    from core.guards import GuardParams, build_guard
    r = build_guard(GuardParams(mode="stair", guard_path=stair_result["guard_path"], sides="both"))
    r["posts"], r["top_rail"], r["bottom_rail"], r["handrail"], r["brackets"], r["infill"],
    r["info"], r["warnings"], r["warning_index"], r["bom"]
"""
from .params import GuardParams
from .layout import build_guard

__all__ = ["GuardParams", "build_guard"]
