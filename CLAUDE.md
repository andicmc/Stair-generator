# Grasshopper/Rhino Building Element Library — Rules

## Architecture
- Every element has two layers:
  1. `core/` — pure Python, NO Rhino imports. Takes numbers/points, returns plain data
     (points, polylines, dimensions, warnings). Fully unit-tested with pytest.
  2. `adapters/` — thin RhinoCommon wrapper used inside a GH Python Script component.
     Converts core data to Rhino geometry. Keep logic out of adapters.
- Detect the existing Rhino/GH Python version from the current scripts and match it.
  If starting fresh, target Rhino 8 GH Script component (Python 3).
- Units: millimetres everywhere. Z-up. Origin = base point input.

## Code limits
- All building-code limits live in `config/code_limits.json`, each with a source note
  (e.g. "OBC 9.8 — verify"). Never hard-code limits in logic.
- Code checks produce warnings (list of strings + failing geometry index), never
  silently alter the design.

## Outputs (every component)
- Geometry grouped by part (e.g. treads, stringers, posts) as separate outputs.
- `info` output: key computed values (counts, actual rise/run, lengths).
- `warnings` output: code-check failures.
- `bom` output: simple quantity list (part, count, length/area).

## Working style (autopilot)
- Read existing code first; do not break existing working features.
- Small commits with clear messages. Keep `CHANGELOG.md` and `BACKLOG.md` updated.
- Every new feature needs pytest cases, including edge cases (zero/negative input,
  odd riser counts, very small/large sizes). Run the tests before every commit.
- Because Rhino is not available in the cloud, write `TESTING.md` for each element:
  a short checklist of what Andi should check visually in Rhino, with slider values.
- If something is ambiguous, choose the most common North American residential
  convention, note the assumption in `ASSUMPTIONS.md`, and keep going.

## Running the tests
```
pip install pytest
python -m pytest -q
```
