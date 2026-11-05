"""Guard / railing parameters. Lengths in mm, angles in degrees.

Heights are measured vertically: on flights from the nosing line, on landings and
floors (and in curve mode) from the walking surface. The guard plane is the vertical
plane through the path line, moved ``inset`` towards the stair (negative = outwards).
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

MODES = ("stair", "curve")
SIDES = ("left", "right", "both")
CONTEXTS = ("residential", "other")
POST_SHAPES = ("square", "rect", "round", "custom")
RAIL_SHAPES = ("rect", "round", "custom")
MOUNTS = ("top", "fascia", "embedded")
TRANSITIONS = ("smooth", "sharp")
INFILLS = ("balusters", "horizontal", "cable", "glass", "mesh", "none")
POST_RULES = ("every_step", "every_n_steps", "max_spacing", "corners", "ends")
POST_ON_TREAD = ("centre", "nosing")
HANDRAIL_SIDES = ("same", "left", "right", "both")


@dataclass
class GuardParams:
    # --- input ------------------------------------------------------------------------
    mode: str = "stair"                           # stair | curve
    guard_path: Optional[dict] = None             # stair mode: docs/guard_path.md
    sides: str = "both"                           # stair mode: left | right | both
    curves: Optional[List[List[Tuple[float, float, float]]]] = None   # curve mode: polylines
    curves_closed: Optional[List[bool]] = None
    curve_outward: str = "right"                  # curve mode: falling side = left | right of travel
    context: str = "residential"                  # guard height context (config)
    # --- heights ----------------------------------------------------------------------
    height_flight: Optional[float] = None         # top of the top rail above the nosing line
    height_landing: Optional[float] = None        # top of the top rail above the surface
    inset: Optional[float] = None                 # guard plane from the edge; None = post_size / 2
    transition: str = "smooth"                    # flight <-> landing: smooth | sharp
    # --- posts ------------------------------------------------------------------------
    post_rules: List[str] = field(default_factory=lambda: ["every_step", "corners", "ends"])
    post_every_n: int = 2
    post_max_spacing: float = 1200.0
    post_on_tread: str = "centre"                 # centre | nosing (+ post_tread_offset)
    post_tread_offset: float = 0.0                # from the nosing, along the flight
    post_shape: str = "square"                    # square | rect | round | custom
    post_size: float = 50.0                       # square side / rect width / round diameter
    post_depth: float = 50.0                      # rect only (along the guard)
    post_rotation: float = 0.0
    post_custom_profile: Optional[List[Tuple[float, float]]] = None   # closed, mm, centred
    post_mount: str = "top"                       # top | fascia | embedded
    fascia_drop: float = 200.0                    # fascia: post base below the surface
    fascia_offset: float = 40.0                   # fascia: post plane moved outwards
    embed_depth: float = 100.0
    # --- top rail ---------------------------------------------------------------------
    top_rail_shape: str = "rect"                  # rect | round | custom
    top_rail_w: float = 60.0
    top_rail_h: float = 40.0                      # rect height / round diameter
    top_rail_custom_profile: Optional[List[Tuple[float, float]]] = None
    top_rail_gap: float = 0.0                     # between the post top and the rail underside
    # --- bottom rail ------------------------------------------------------------------
    bottom_rail: bool = False                     # on stairs a bottom rail must sit near the nosings
    bottom_gap: float = 90.0                      # clear height above the surface / nosing line
    bottom_rail_w: float = 40.0
    bottom_rail_h: float = 30.0
    bottom_rail_shape: str = "rect"
    # --- handrail (separate) ----------------------------------------------------------
    handrail: bool = False
    handrail_sides: str = "same"                  # same (as the guard) | left | right | both
    handrail_height: Optional[float] = None       # None = middle of the configured range
    handrail_shape: str = "round"
    handrail_size: float = 42.0                   # round diameter / rect width
    handrail_h: float = 42.0                      # rect height
    handrail_offset: float = 75.0                 # from the path edge towards the stair
    bracket_spacing: float = 1200.0
    handrail_ext_top: float = 300.0               # horizontal extension beyond the top riser
    handrail_ext_bottom: float = 300.0            # horizontal extension beyond the bottom riser
    handrail_returns: bool = True                 # end returns (towards the wall)
    handrail_return_length: Optional[float] = None   # None = handrail_offset
    # --- infill -----------------------------------------------------------------------
    infill: str = "balusters"
    baluster_spacing: float = 100.0               # max clear spacing
    balusters_per_tread: int = 0                  # 0 = use spacing
    baluster_shape: str = "square"
    baluster_size: float = 20.0
    bar_count: int = 0                            # horizontal: 0 = from bar_spacing
    bar_spacing: float = 100.0                    # clear spacing
    bar_size: float = 12.0
    cable_diameter: float = 4.0
    cable_spacing: float = 80.0
    glass_thk: float = 10.0
    glass_gap: float = 15.0                       # glass to posts / rails
    glass_bottom_gap: float = 90.0                # glass to the surface / nosing line
    clamp_spacing: float = 600.0
    mesh_frame: float = 25.0
    mesh_panel_thk: float = 3.0
    # --- rules ------------------------------------------------------------------------
    rules: dict = field(default_factory=dict)

    def validate(self):
        p = self
        if p.mode not in MODES:
            raise ValueError("mode '{}' is not one of {}".format(p.mode, MODES))
        if p.mode == "stair":
            if not p.guard_path or "sides" not in p.guard_path:
                raise ValueError("stair mode needs a guard_path (see docs/guard_path.md)")
            if p.sides not in SIDES:
                raise ValueError("sides '{}' is not one of {}".format(p.sides, SIDES))
        else:
            if not p.curves or not any(len(c) >= 2 for c in p.curves):
                raise ValueError("curve mode needs at least one curve with 2 or more points")
            if p.curve_outward not in ("left", "right"):
                raise ValueError("curve_outward must be left or right")
        for name, allowed in (("context", CONTEXTS), ("post_shape", POST_SHAPES),
                              ("top_rail_shape", RAIL_SHAPES), ("bottom_rail_shape", RAIL_SHAPES),
                              ("handrail_shape", RAIL_SHAPES), ("post_mount", MOUNTS),
                              ("transition", TRANSITIONS), ("infill", INFILLS),
                              ("post_on_tread", POST_ON_TREAD), ("handrail_sides", HANDRAIL_SIDES),
                              ("baluster_shape", ("square", "round"))):
            if getattr(p, name) not in allowed:
                raise ValueError("{} '{}' is not one of {}".format(name, getattr(p, name), allowed))
        for r in p.post_rules:
            if r not in POST_RULES:
                raise ValueError("post rule '{}' is not one of {}".format(r, POST_RULES))
        for name in ("post_size", "post_depth", "top_rail_w", "top_rail_h", "bottom_rail_w",
                     "bottom_rail_h", "handrail_size", "handrail_h", "baluster_size", "bar_size",
                     "cable_diameter", "glass_thk", "post_max_spacing", "bracket_spacing",
                     "baluster_spacing", "bar_spacing", "cable_spacing", "clamp_spacing",
                     "mesh_frame"):
            if getattr(p, name) <= 0:
                raise ValueError("{} must be > 0 mm (got {})".format(name, getattr(p, name)))
        for name in ("bottom_gap", "glass_gap", "glass_bottom_gap", "top_rail_gap", "fascia_drop",
                     "fascia_offset", "embed_depth", "handrail_ext_top", "handrail_ext_bottom",
                     "post_tread_offset"):
            if getattr(p, name) < 0:
                raise ValueError("{} must be >= 0 mm (got {})".format(name, getattr(p, name)))
        for name in ("height_flight", "height_landing", "handrail_height"):
            v = getattr(p, name)
            if v is not None and v <= 0:
                raise ValueError("{} must be > 0 mm (got {})".format(name, v))
        if p.post_every_n < 1:
            raise ValueError("post_every_n must be >= 1")
        if p.post_shape == "custom" and (not p.post_custom_profile or len(p.post_custom_profile) < 3):
            raise ValueError("post_shape custom needs post_custom_profile with >= 3 points")
        if p.top_rail_shape == "custom" and (not p.top_rail_custom_profile or
                                             len(p.top_rail_custom_profile) < 3):
            raise ValueError("top_rail_shape custom needs top_rail_custom_profile")
        return self

    def as_dict(self):
        return asdict(self)
