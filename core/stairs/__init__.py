"""Stair core: numbers in, plain geometry data out. No Rhino imports.

    from core.stairs import StairParams, build_stair
    result = build_stair(StairParams(stair_type="L", floor_to_floor=2800))
    result["treads"], result["info"], result["warnings"], result["bom"], result["guard_path"]
"""
from .params import StairParams, STAIR_TYPES, STRINGER_TYPES
from .layout import build_stair

__all__ = ["StairParams", "build_stair", "STAIR_TYPES", "STRINGER_TYPES"]
