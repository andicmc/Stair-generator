# Backlog

## Needs Andi
- [ ] Verify every value in `config/code_limits.json` against the OBC (all marked "verify").
- [ ] Commit the `stairgen` / `stairgen_rhino` library (v01 component) or retire it in
      favour of `core/stairs` + `stair_component_v2.py`.
- [ ] Run TESTING.md in Rhino and report.
- [ ] Decide: winder walk-line run limit (0 = dwelling unit, 255 otherwise).

## Stairs
- [ ] Winders with `landing_depth` larger than the width (currently a square set).
- [ ] 180° winders with a well gap > 0 (currently falls back to a landing).
- [ ] Bull-nose / curved starter tread; return nosings.
- [ ] Landing framing (stringers / headers around landings).
- [ ] True arcs for spiral treads in the adapter (currently 10° polyline segments).
- [ ] Spiral: top landing / platform option; handrail-side selection.
- [ ] Walkline run check for curved flights at the narrow end (OBC 9.8.4.6 min run at
      the narrow end).
- [ ] Uniformity check between flights (`uniformity_tol_mm` is loaded but all risers
      are equal by construction, so no check is needed yet).
- [ ] v01 `.gh` still embeds the old script; save a v02 `.gh` after pasting.

## Guard / railing (next task)
- [ ] Component per the brief (stair mode from `guard_path`, curve mode).

## Not in this session
- Windows and doors (dropped by Andi on 2026-11-05).
