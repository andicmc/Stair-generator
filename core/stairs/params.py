"""Stair parameters. All lengths in mm, angles in degrees.

Frame: the base point is the centre of the bottom of the first riser, at floor level
(0, 0, 0). The first flight runs along +X. Looking up the stair, left is +Y.
``turn`` = "left" means the stair turns towards the left of someone walking up.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

STAIR_TYPES = ("straight", "L", "U", "U2", "spiral")
STRINGER_TYPES = ("closed", "cut", "centre", "none")
TURNS = ("left", "right")
TOP_CONNECTIONS = ("floor", "top_tread")
BOTTOM_CONNECTIONS = ("floor", "starter_tread")


@dataclass
class StairParams:
    # --- type and size ---------------------------------------------------------------
    stair_type: str = "straight"          # straight | L | U | U2 | spiral
    floor_to_floor: float = 2800.0        # finished floor to finished floor
    width: float = 900.0                  # clear width between stringers (spiral: R - column)
    riser_count: Optional[int] = None     # None = auto from rise_max
    tread_run: Optional[float] = None     # None = auto (comfort rule, clamped to config)
    turn: str = "left"                    # L, U, U2 and spiral: direction going up
    # --- flights and landings (L, U, U2) ----------------------------------------------
    flight_risers: Optional[List[int]] = None   # risers per flight; overrides riser_count
    landing_depth: Optional[float] = None       # default = width
    landing_depths: Optional[List[float]] = None  # per landing, overrides landing_depth
    well_gap: float = 0.0                 # U: gap between the flights; U2: minimum gap
    # --- winders instead of landings (L, U, U2) ---------------------------------------
    winders: bool = False
    winder_count: int = 3                 # winders per 90 degree turn
    # --- treads and risers -----------------------------------------------------------
    nosing: float = 25.0                  # tread projection past the riser
    tread_thk: float = 38.0
    riser_thk: float = 19.0
    open_risers: bool = False
    landing_thk: float = 250.0
    # --- stringers -------------------------------------------------------------------
    stringer_type: str = "closed"         # closed | cut | centre | none
    stringer_depth: float = 286.0         # vertical depth below the nosing/throat line
    stringer_thk: float = 38.0
    stringer_top_margin: float = 90.0     # closed stringer: top edge above the nosing line
    # --- ends ------------------------------------------------------------------------
    top_connection: str = "floor"         # floor = last riser meets the floor | top_tread
    bottom_connection: str = "floor"      # floor | starter_tread (wider first tread)
    starter_extension: float = 150.0      # starter tread: extra width each side
    # --- spiral ----------------------------------------------------------------------
    spiral_radius: float = 1000.0         # outer radius
    spiral_column_radius: float = 60.0
    turn_angle: float = 360.0             # first riser to last riser
    # --- headroom --------------------------------------------------------------------
    slab_thk: float = 250.0               # floor above; ceiling = floor_to_floor - slab_thk
    ceiling_z: Optional[float] = None     # underside of the floor above, overrides slab_thk
    opening: Optional[List[Tuple[float, float]]] = None  # floor opening above, plan polygon
    # --- rules -----------------------------------------------------------------------
    rules: dict = field(default_factory=dict)   # overrides for config/code_limits.json

    def validate(self):
        """Raise ValueError for impossible input (code limits are warnings, not errors)."""
        p = self
        if p.stair_type not in STAIR_TYPES:
            raise ValueError("stair_type '{}' is not one of {}".format(p.stair_type, STAIR_TYPES))
        if p.turn not in TURNS:
            raise ValueError("turn '{}' is not one of {}".format(p.turn, TURNS))
        if p.stringer_type not in STRINGER_TYPES:
            raise ValueError("stringer_type '{}' is not one of {}".format(
                p.stringer_type, STRINGER_TYPES))
        if p.top_connection not in TOP_CONNECTIONS:
            raise ValueError("top_connection '{}' is not one of {}".format(
                p.top_connection, TOP_CONNECTIONS))
        if p.bottom_connection not in BOTTOM_CONNECTIONS:
            raise ValueError("bottom_connection '{}' is not one of {}".format(
                p.bottom_connection, BOTTOM_CONNECTIONS))
        if not p.floor_to_floor or p.floor_to_floor <= 0:
            raise ValueError("floor_to_floor must be > 0 mm (got {})".format(p.floor_to_floor))
        if not p.width or p.width <= 0:
            raise ValueError("width must be > 0 mm (got {})".format(p.width))
        if p.riser_count is not None and int(p.riser_count) < 1:
            raise ValueError("riser_count must be >= 1 (got {})".format(p.riser_count))
        if p.tread_run is not None and p.tread_run <= 0:
            raise ValueError("tread_run must be > 0 mm (got {})".format(p.tread_run))
        if p.flight_risers is not None:
            if not p.flight_risers or any(int(n) < 1 for n in p.flight_risers):
                raise ValueError("flight_risers: every flight needs >= 1 riser (got {})".format(
                    p.flight_risers))
        for name in ("nosing", "tread_thk", "riser_thk", "landing_thk", "stringer_depth",
                     "stringer_thk", "stringer_top_margin", "starter_extension", "well_gap",
                     "slab_thk"):
            if getattr(p, name) < 0:
                raise ValueError("{} must be >= 0 mm (got {})".format(name, getattr(p, name)))
        if p.landing_depth is not None and p.landing_depth <= 0:
            raise ValueError("landing_depth must be > 0 mm (got {})".format(p.landing_depth))
        if p.landing_depths is not None and any(d <= 0 for d in p.landing_depths):
            raise ValueError("landing_depths must all be > 0 mm (got {})".format(p.landing_depths))
        if p.winders and int(p.winder_count) < 1:
            raise ValueError("winder_count must be >= 1 (got {})".format(p.winder_count))
        if p.stair_type == "spiral":
            if p.spiral_radius <= p.spiral_column_radius:
                raise ValueError("spiral_radius ({}) must be larger than spiral_column_radius "
                                 "({})".format(p.spiral_radius, p.spiral_column_radius))
            if p.spiral_column_radius < 0:
                raise ValueError("spiral_column_radius must be >= 0")
            if p.turn_angle <= 0:
                raise ValueError("turn_angle must be > 0 degrees (got {})".format(p.turn_angle))
        if p.opening is not None and len(p.opening) < 3:
            raise ValueError("opening needs at least 3 points")
        return self

    def n_turns(self):
        return {"straight": 0, "L": 1, "U": 1, "U2": 2, "spiral": 0}[self.stair_type]

    def turn_angles(self):
        return {"straight": [], "L": [90], "U": [180], "U2": [90, 90], "spiral": []}[self.stair_type]

    def as_dict(self):
        return asdict(self)
