# TESTING.md — what to check visually in Rhino

Rhino is not available in the cloud; the geometry is tested numerically. Please check
these in Rhino 8 / Grasshopper and note anything odd in BACKLOG.md.

## Set-up
1. Open `grasshopper/2026-10-31_..._v01.3dm` (mm, tolerance 0.01).
2. New Grasshopper file in the same folder (so the component finds the library); save it.
3. Python 3 Script component, paste `grasshopper/stair_component_v2.py`, add the inputs
   and outputs listed at the top of the script (names must match). Sliders in mm.
4. Expected: component message "14 risers, 0 warn"; the `report` panel shows the summary.

## Stairs — checklist (default sliders unless noted)

| # | Settings | Check |
|---|---|---|
| 1 | straight, floor_to_floor 2800, width 900 | 14 risers, 13 treads, rise 200, run 255. Treads overhang the risers by 25 (nosing). Last riser top at z = 2800; no tread at floor level. Two closed stringers outside the treads, top edge above the nosings, bottom resting on the floor. |
| 2 | 1 + `top_connection = top_tread` | An extra tread at z = 2800. |
| 3 | 1 + `bottom_connection = starter_tread` | First tread 150 wider each side. |
| 4 | 1 + `stringer_type = cut` | Sawtooth stringers inside the width, treads sitting on them. `centre`: one under the middle. `none`: none. |
| 5 | 1 + `open_risers = True` | Riser faces as flat surfaces only (no thickness), none in the BOM. |
| 6 | 1 + `riser_count 16` | Rise 175, warning-free. `riser_count 13` → RISE_MAX warning, geometry still built. |
| 7 | L, turn left | 7 + 7 risers, square landing 900 × 900 at z = 1400 at the end of flight 1; flight 2 leaves the landing to +Y (left when walking up). `turn right` → mirror image. |
| 8 | L + `landing_depth 1200` | Landing 1200 along flight 1; flight 2 aligned with the far edge; no LANDING_DEPTH warning. `landing_depth 700` → warning, landing still 700. |
| 9 | L + `winders = True`, winder_count 3 | Three 30° winders instead of the landing, rising 200 each; 6 + 6 risers in the flights (total still 14). Four winders → 22.5° each. |
| 10 | U, well_gap 150 | Half landing spanning both flights + gap; flight 2 comes back parallel to flight 1, 150 apart. |
| 11 | U + winders, well_gap 0 | Six kite winders turning 180° around one newel; WINDER_TURN warning. With well_gap > 0 a landing is used and a remark says why. |
| 12 | U2 | Three flights (5 + 5 + 4 risers), two 90° landings, flight 3 parallel to flight 1 running back. `well_gap 1500` → landing 2 deeper (1500 + 900 − 1020 = 1380) so the well is 1500. |
| 13 | U2 + `flight_risers = [6, 1, 6]`, `landing_depths = [900, 500]` | Flight 3 directly above flight 1 → HEADROOM warning with the step index; the shallow landing → LANDING_DEPTH warning. |
| 14 | spiral, radius 1000, column 60, turn_angle 360 | 13 wedge treads around a column, risers radial, last riser at 360°. `turn right` → clockwise. turn_angle 540 → HEADROOM warning (tread one turn above). |
| 15 | any + `opening` = closed rectangle drawn over the top half of the stair | report shows "headroom min ... at step n" for the steps under the slab (ceiling = 2800 − 250). |
| 16 | any | `guard_lines` = two polylines along the nosings (left / right), level on landings, from the first nosing to the upper floor. |
| 17 | document in **metres** | Same stair at 1/1000 scale; sliders still in mm; report says "document: Meters". |
| 18 | base_pt + rotation 90 | Stair moved and turned; `opening` is still interpreted correctly (draw it in the document frame). |

## Guard / railing — checklist

Set-up: second Python 3 Script component with `grasshopper/guard_component.py`; wire the
stair's `guard_path` output (text) into the guard's `guard_path` input. Defaults: both
sides, posts on every tread + corners + ends, 50 mm square posts, 60 × 40 top rail at
900 mm, balusters at ≤ 100 mm clear, no bottom rail, no handrail.

| # | Settings | Check |
|---|---|---|
| G1 | straight stair, defaults | A post at the centre of every tread (base on the tread, inset 25 so its face is flush with the edge) and one on the floor at the top edge. Top rail parallel to the nosing line, 880 mm above it (centre), levelling out just before the floor edge. Balusters from the nosing line to the rail underside, ≤ 100 clear. |
| G2 | `side = left` | Only the left guard (looking up). |
| G3 | L stair, defaults | Outer side: the rail levels out onto the landing without a step, turns the corner (post there), picks up the slope of flight 2 before the exit edge. Inner side: posts at the newel corner; the rail rises vertically at the newel (always sharp). |
| G4 | L + `transition = sharp` | Outer side: sloped rail to the landing edge, vertical gooseneck, level landing rail. |
| G5 | `height_landing 1070` | Landing rail higher than the flight rail; a step up at the top floor edge. |
| G6 | `post_rules = max_spacing`, `post_max_spacing 1000` | Posts only at ends, corners and ≤ 1000 apart. `every_n_steps`, `post_every_n 3` → every third tread. |
| G7 | `post_on_tread = nosing`, `post_tread_offset 60` | Posts 60 mm behind the nosings. |
| G8 | `post_shape = round / rect / custom` (+ `post_profile` curve) | Profiles; `post_rotation 45`. |
| G9 | `post_mount = fascia`, `fascia_drop 200` | Posts outside the stringer face, bases 200 below the treads. `embedded` → bases 100 below. |
| G10 | `bottom_rail = True`, `bottom_gap 90` | Bottom rail 90 clear above the nosing line / landing; TRIANGLE warning (190 mm sphere > 150) — expected on a 200/255 stair; `bottom_gap 20` passes. |
| G11 | `handrail = True` | Round 42 handrail at 915 mm, 75 mm in from the edge, 300 mm horizontal extensions beyond the bottom and top risers with end returns to the wall; brackets ≤ 1200 apart. `handrail_height 800` → HANDRAIL_HEIGHT warning. |
| G12 | `infill = horizontal`, `bar_spacing 100` | Bars following the slope; CLIMBABLE warning. `cable` → round cables. |
| G13 | `infill = glass`, posts `max_spacing 1200` | Glass panels between posts, 15 mm gaps, bottom 90 above the nosing line; clamp points along the bottom edge; BOM lists the glass area. `mesh` → panels with a 25 mm frame. |
| G14 | `height_flight 850` | GUARD_HEIGHT warning (900 residential); `context = other` → 1070 required. |
| G15 | U2 stair, winders on | Four landing corner posts (U2); with winders a post on each winder outer end and one at the newel. |
| G16 | spiral | Outer helix rail with a post per tread; inner side on the column: few posts (60 mm radius). |
| G17 | curve mode: closed rectangle 3 × 2 m, `post_rules = max_spacing` | Posts at the 4 corners and ≤ 1200 apart, level rail all round, no end posts. |
| G18 | curve mode: 3D polyline, `base` = a sloped Brep | Rail 900 above the surface along the curve; a post at the bend. |
| G19 | metre document | Stair + guard chain: guard geometry at the stair's base point at 1/1000 scale. |

## Known visual simplifications
- Spiral arcs are 10° polyline segments (treads are planar polygons).
- No landing framing, no bull-nose, no newels (the guard component adds posts).
- Rails are one prism per straight segment (not mitred at kinks); round rails are 16-gons.
- Guard: no newel caps, no bracket geometry (a line from the handrail to the wall).
