# Changelog

## Unreleased — 2026-11-05
### Changed
- Stair `guard_path`: a flight leaving a landing starts its nosing line at the exit edge.

### Added
- `core/guards`: guard / railing core. Stair mode from `guard_path` (left / right / both)
  and curve mode (any polylines, open or closed, optional base surface heights). Posts by
  rule (every step / every N / max spacing / corners / ends), on tread centre or offset
  from the nosing, square / rect / round / custom profiles, top / fascia / embedded mounts.
  Top rail, optional bottom rail, separate handrail with extensions, returns and brackets;
  sloped on flights, level on landings, smooth or sharp transitions. Infill: balusters,
  horizontal bars, cable, glass (clamps), mesh (frame). Code checks: guard height by
  context, handrail height, 100 mm sphere, stair triangle (150 mm), climbable zone.
  `info`, `warnings` + index, `bom`.
- `adapters/guards_rhino.py` and `grasshopper/guard_component.py`.
- `tests/test_core_guards.py` (67) and `tests/test_guard_adapter_and_component.py` (11).
- `core/stairs`: pure-Python stair core (straight, L, U, **U2 with two landings**, spiral)
  with equal risers, configurable landing depths, left/right turns, winders (L, U, U2),
  nosing / tread / riser thickness, open risers, stringer types (closed, cut, centre,
  none), top and bottom connection options, headroom check (floor above + stacked
  flights), `guard_path` output, `info`, `warnings` + `warning_index`, `bom`.
- `config/code_limits.json`: all limits with source notes (rise 200 / run 255 / width
  860 / headroom 1950 defaults, all "verify").
- `adapters/stairs_rhino.py`: RhinoCommon adapter (polygons → capped Breps, placement,
  unit scaling, guard path JSON).
- `grasshopper/stair_component_v2.py`: thin GH component using core + adapter.
- `docs/guard_path.md`: guard interface contract.
- `tests/test_core_stairs.py`: 97 tests; `tests/test_adapter_and_component_v2.py`: 19 (solver, every type, winders, spiral, guard path,
  stringers, code checks, edge cases).
- `AUDIT_staircase.md`, `ASSUMPTIONS.md`, `TESTING.md`, `BACKLOG.md`, `CLAUDE.md`.

## 2026-11-01
- v01 component: portable library lookup (no F: path), document units, input checks,
  Elefont-style layer paths, 49 tests with Rhino stand-ins.
