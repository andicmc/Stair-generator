# Audit — staircase script (2026-11-05)

Scope: what is in this repository today. That is the Grasshopper component script
(`grasshopper/stair_generator_component.py`, extracted from the v01 `.gh`) and the v01
`.gh` / `.3dm` files. The `stairgen` / `stairgen_rhino` library that the component calls
(`run_design`, `run_geometry`, `run_annotation`, `boundary_check`, `bake`) lives on the
F: drive and is **not in the repository**, so its internals could not be read here.
Items that depend on it are marked *cannot verify here*. Where I knew the library's
behaviour from the earlier session (its 412 tests ran then), I say so.

## Checklist

| # | Item | Finding | Action |
|---|------|---------|--------|
| 1 | Riser count from floor-to-floor; all risers equal | Component passes `floor_height` and an optional `riser_count` to the library; the report shows one `riser_h`, so risers are equal within a stair. Division into flights (`flight1_risers`) keeps the same rise. *Library arithmetic cannot be re-verified here.* | New core: `n = ceil(H / rise_max)`, `rise = H / n`, one rise for the whole stair, checked by tests. |
| 2 | Consistent parameter names and units across types | Names are consistent in the component (`floor_height`, `width`, `tread_depth`, `riser_count`, `turn`, `landing_depth`, `well_gap`, `spiral_radius`, `turn_angle`). Two inconsistencies: `tread_depth` is "not used for spiral or a path", and `turn_angle` / `spiral_radius` apply only to spirals while living in the same list. Units are mm throughout the sliders; the library is mm-only (the v02 component converts document units). | Core uses one `StairParams` for all types; spiral-only and L/U-only parameters are grouped and documented. |
| 3 | Landing depth >= stair width (configurable) | Default landing depth = width (`0 = stair width`). Nothing stops a smaller value: slider range is 0–2000, and no warning was visible in the component. *Whether the library warns: cannot verify here.* | Rule in `config/code_limits.json` (`landing_depth_min_equals_width`); warning when violated. |
| 4 | Turn direction left/right for L and U | Present (`turn` drop-down). | Kept; also used by the new U-2-landing type and spiral (hand). |
| 5 | Code checks: rise, run, width, headroom | The library reads a "rules file" (`rules` input, "empty = example file (PLACEHOLDERS)"). The limits are therefore in a text file whose format and values are not in the repo; the example file was placeholders. Headroom check exists and is driven by `opening` + `slab_thk` (ceiling = floor height − slab). No min-width check was visible. | New `config/code_limits.json` with source notes; checks for max/min rise, min/max run, min width, min headroom, max rise per flight, landing depth, winder angle, nosing. Headroom takes an optional ceiling height + floor-opening polygon, and also checks a flight stacked above another (U stairs). |
| 6 | core/adapter structure | Not present. The component mixes UI building (sliders, groups, labels), orchestration and bake; the geometry is in the external library. | New `core/` (pure Python, tested) + `adapters/stairs_rhino.py` (thin RhinoCommon) + `grasshopper/stair_component_v2.py`. The v01 component stays untouched until the library is in the repo. |

## Other findings

- **Hard-coded path (fixed in v02 commit):** `STAIRGEN_PATH = r"F:\..."`. Replaced by
  configurable / relative lookup.
- **Error handling (fixed):** a mistyped `stair_type` produced a raw traceback.
- **`REBUILD` flag (fixed):** worked only once per Rhino session.
- **Unused code:** `_tidy()` in the component is never called. Harmless; left in place.
- **Units:** the v01 component assumed a millimetre document. Fixed in v02 (reads
  `RhinoDoc.ActiveDoc` units and tolerance).
- **Bake:** whether `bake()` bakes the geometry it is given or rebuilds it from the stair
  object is *not verifiable here*. Matters only in non-mm documents.
- **Stringers:** the v01 component has "with/without" and a thickness only. No stringer
  type (closed / cut / centre) and no stringer depth.
- **Risers:** open vs closed exists (`riser_thk = 0` = open). Nosing and tread thickness
  exist.
- **Top / bottom connection:** not configurable.
- **Winders:** not available.
- **U with two landings:** not available (`U` is one half-landing).
- **Guard interface:** none. The component outputs step numbers / arrows / UP text for
  annotation, nothing a guard component can consume.
- **Library in repo:** the biggest risk. Until `stairgen` / `stairgen_rhino` are committed,
  the v01 component cannot run from a fresh clone.

## Decision

Rather than patch the unseen library, the new feature work is built as a new, tested
`core/stairs` package following CLAUDE.md, with a new GH component (`v2`). The v01
component and library stay as they are so nothing that works today breaks. Once the
library is committed, `stairgen_rhino.gh` can be re-pointed at `core/stairs` or retired
(see BACKLOG.md).
