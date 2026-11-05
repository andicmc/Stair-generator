# Testing

```
pip install pytest
python -m pytest -q tests
```

`tests/test_component.py` runs `grasshopper/stair_generator_component.py` outside Rhino. Rhino,
Grasshopper and `scriptcontext` are replaced by small stand-ins (`FakeRhinoDoc`, `FakeStrings`
for the document user text, `Component`), and a fake `stairgen` library is written to a temporary
folder. The tests check the component's own logic, not the stair library or real geometry.

## What is covered

| Area | Tests |
|---|---|
| Library lookup | next to the .gh, parent folders, `STAIRGEN_PATH` setting and env var, unsaved .gh, missing library message, stale copy on `sys.path` |
| Units | mm document unchanged; metre / inch documents convert inputs in and outputs out; coarse tolerance warning |
| Input checks | drop-down values normalised, bad values are component errors not tracebacks, zero = auto, stringers off |
| Set-up | runs once per component, `REBUILD`, works without the library |
| Bake layers | typed paths, office defaults, invalid names reported before baking, old drop-down migration |
| **Levels (project reference)** | both names → floor height and start Z from the document key `project_reference`; empty names → `floor_height` slider; one name, unknown name, top below bottom, wrong `schema_version` → clear errors; wired `reference` overrides the document; reference units (m) converted to mm; metre document |

## Not covered here

Real Rhino geometry, the `stairgen` library, Grasshopper UI (controls, panels) and baking need
Rhino 8. Open the `.gh`, set the two level names after running `BES_ProjectReference` with
`Save = True`, and check the report line `Levels: … from the project reference`.
