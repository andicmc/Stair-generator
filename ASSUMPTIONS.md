# Assumptions (chosen when the brief was ambiguous; North American residential convention)

## Stairs (core/stairs)
1. **Frame.** Base point = centre of the bottom of the first riser at floor level. First
   flight along +X; looking up the stair, left is +Y. `turn = "left"` turns towards the
   walker's left. Right-turn stairs are mirrored left-turn stairs.
2. **Riser count** = the fewest equal risers with rise ≤ `rise_max_mm` (ceil(H / 200)).
   The upper floor is the last walking surface: n risers give n − 1 treads
   (`top_connection = "floor"`).
3. **Default run** = 630 − 2 × rise (comfort rule 2R + G = 630), clamped to
   [`run_min_mm`, `run_max_mm`]. Override with `tread_run`.
4. **Riser split** over flights: as even as possible; extra risers go to the lower flights.
5. **Landing depth** default = stair width. For a 90° landing deeper than the width, the
   next flight aligns with the far (outer) edge of the landing.
6. **U2 well gap**: the gap between flights 1 and 3 follows from flight 2's length;
   `well_gap` is a *minimum*: landing 2 grows (when its depth is auto) to reach it.
   `info["well_gap"]` reports the actual gap.
7. **Winders** replace a landing with a square set (width × width); `landing_depth` is
   ignored for that turn. A winder set of k treads uses k − 1 risers (the first winder is
   reached by the previous flight's last riser). Rays from the inner corner at equal
   angles. 180° winders (U stair) need `well_gap = 0` (kite winders around one newel);
   otherwise a landing is used and a remark says so.
8. **Winder walk line** = `walkline_offset_mm` (300) from the inner corner. The
   `winder_min_run_at_walkline_mm` limit defaults to 0 because 30° winders within a
   dwelling unit have no walk-line run requirement (OBC 9.8.4.7 — verify). Set it to 255
   for stairs outside a dwelling unit.
9. **Tread polygon** runs from the nosing to the next riser face (`run + nosing` deep).
   Riser boards sit behind the riser face. `open_risers` gives zero-thickness riser faces
   (kept for reference, not in the BOM).
10. **Stringers.** `closed` (housed) stringers sit *outside* the clear width (overall width
    = width + 2 × thickness) with the top edge `stringer_top_margin` above the nosing line
    and the bottom `stringer_depth` below it; plumb cut at the top, level cut at the
    floor. `cut` stringers sit *inside* the width; treads bear on the seats, riser cuts
    are set back by the riser thickness. `centre` = one cut stringer on the centre line.
    Landings are slabs (`landing_thk`); no landing framing is modelled.
11. **Spiral.** Base point = column centre; risers at equal angles, the last riser at
    `turn_angle`; treads are wedges from the column to the outer radius (arcs as 10°
    segments, the adapter can rebuild true arcs later). Nosing projection rotates the
    leading edge back by `nosing / R`. Width = R − column radius. No stringers; one column.
12. **Headroom.** Checked at every nosing and tread centre against (a) any flight,
    landing or winder set above it (soffit = tread top − tread thickness − stringer depth)
    and (b) the floor above, **only when `opening` is given**: points outside the opening
    polygon are under the slab, ceiling = `ceiling_z` or `floor_to_floor − slab_thk`.
    Spirals also check the tread one full turn above.
13. **Starter tread** = first tread widened by `starter_extension` on both sides
    (rectangular; a bull-nose can be added later).
14. **Defaults**: tread 38 mm, riser 19 mm, nosing 25 mm, stringer 2×12 (286 × 38),
    landing slab 250 mm, slab above 250 mm.

## Code limits (config/code_limits.json)
All values are marked "verify": rise max 200 / min 125, run min 255 / max 355, width min
860, headroom min 1950, nosing max 25, max rise per flight 3700, landing depth ≥ width and
≥ 860, winders max 90° per set and 30° per tread, walk line 300 mm. Guard values:
900 / 1070 guard height, handrail 865–965, 100 mm sphere, climbable zone 140–900.
