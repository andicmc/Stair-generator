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

## Known visual simplifications
- Spiral arcs are 10° polyline segments (treads are planar polygons).
- No landing framing, no bull-nose, no newels (the guard component adds posts).
