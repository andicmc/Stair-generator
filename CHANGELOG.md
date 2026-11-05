# Changelog

## Unreleased — 2026-11-05
### Added
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
- `tests/test_core_stairs.py`: 97 tests (solver, every type, winders, spiral, guard path,
  stringers, code checks, edge cases).
- `AUDIT_staircase.md`, `ASSUMPTIONS.md`, `TESTING.md`, `BACKLOG.md`, `CLAUDE.md`.

## 2026-11-01
- v01 component: portable library lookup (no F: path), document units, input checks,
  Elefont-style layer paths, 49 tests with Rhino stand-ins.
