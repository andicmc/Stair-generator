# Stair Generator (Grasshopper, Rhino 8)

A parametric stair generator (straight, L, U, spiral) as one Grasshopper
Python 3 Script component, built on the `stairgen` / `stairgen_rhino` library.

> Design aid only, not a code compliance certification.

## Folder layout

```
<any folder>/
  2026-10-31_STAIR-GENERATOR_MDL_Parametric-Stair_v01.gh
  2026-10-31_STAIR-GENERATOR_MDL_Parametric-Stair_v01.3dm
  stair-generator/            <- library folder (any name containing "stair")
    stairgen/
    stairgen_rhino/
```

| Path in this repo | What it is |
|---|---|
| `grasshopper/stair_generator_component.py` | Source of the component script (paste into the component) |
| `grasshopper/*_v01.gh` / `*_v01.3dm` | v01 definition and model as uploaded. **The .gh still holds the old script with the `F:` path** (see below) |
| `tests/test_component.py` | Tests of the component logic with stand-ins for Rhino/Grasshopper |

**The `stairgen` and `stairgen_rhino` library is not in this repository yet.**
The component needs it to run. Copy it from the project folder into the repo
(e.g. `stair-generator/`) and commit it.

**Open question (units):** in a document that is not in mm, the component converts the
geometry it passes to `bake()` to model units. This is right only if `bake()` bakes the
geometry it is given and does not rebuild it from the stair object. Not checked yet,
because the library is not available here. Millimetre documents are not affected.

## Install on a computer

1. Copy the project folder anywhere (any drive letter, Windows or Mac).
2. Open the `.3dm`, then the `.gh`.
3. Double-click the Stair Generator component, replace its script with
   `grasshopper/stair_generator_component.py`, and save the `.gh` (e.g. as `v02`).

The component finds the library by itself in this order:

1. `STAIRGEN_PATH` at the top of the script, if not empty (absolute, or relative to the `.gh`).
2. The `STAIRGEN_PATH` environment variable (restart Rhino after setting it).
3. A search from the `.gh` folder (and the Rhino file's folder): the folder, up to 2
   parent folders, and sub-folders whose names contain "stair" (2 levels deep).

If it is not found, the component turns red and lists every place it looked.

## Units and tolerance

- Sliders, `riser_h`, `tread_d`, `headroom` and the report are always in **millimetres**.
- The library works in millimetres. The component reads the open Rhino document's
  units, converts `start`, `path`, `boundary` and `opening` to mm, and converts the
  output and baked geometry back to model units. In a mm document nothing is converted.
- The report states the document units and tolerance. A tolerance coarser than 1 mm
  gives a warning.
- After changing the document units, recompute Grasshopper (F5): Grasshopper is not
  told about unit changes.

## Levels from the project reference

The stair can take its height from the shared project reference (grids + levels) that
`andicmc/building-element-standard` stores in the Rhino document user text (key
`project_reference`, see its `docs/project_reference.md`).

| Input | Meaning |
|---|---|
| `level_bottom`, `level_top` | Level names, e.g. `L01` and `L02`. Both set: `floor_height` = elevation difference, and the start point is put on the bottom level. Both empty: the `floor_height` slider is used (raw fallback). One set: error. |
| `reference` | Optional wired reference JSON (from `BES_ProjectReference.JSON`); overrides the document. |

The reference's own `units` field is honoured (a reference saved in metres gives mm to the
library). An unknown level name lists the known names; a reference with another
`schema_version` is refused rather than guessed.

## Document checks

- No Rhino document open: red error, nothing is computed.
- `.gh` not saved yet: the library search uses the Rhino file's folder, the
  environment variable or `STAIRGEN_PATH`. A relative `rules` path needs a saved `.gh`.
- Bake uses the active Rhino document.

## Bake layers

Layers are typed as full paths, like Elefont: `Parent::Child::Grandchild`.

| Input | Empty | Other values |
|---|---|---|
| `bake_layer` | `03_ARCH::A-STAIR` (office default) | any layer path |
| `text_layer` | same as `bake_layer` | `same`, `none` (no annotation), or a layer path |

- Missing layers are created when baking.
- Spaces around `::` are removed. An empty level (`03_ARCH::`) or a name Rhino does not
  allow gives a red message straight away, before you press Bake.
- The office defaults are `DEFAULT_BAKE_LAYER` and `DEFAULT_TEXT_LAYER` at the top of the script.
- Opening a v01 `.gh`: the old layer drop-downs are replaced once by text panels that keep
  the layer you had chosen (`No annotation` becomes `none`).

## Script settings

| Setting | Default | Meaning |
|---|---|---|
| `STAIRGEN_PATH` | `""` | Library folder; empty = find it |
| `REBUILD` | `False` | `True` rebuilds the controls once (each time you set it to True) |
| `DEFAULT_BAKE_LAYER` | `03_ARCH::A-STAIR` | Bake layer when `bake_layer` is empty |
| `DEFAULT_TEXT_LAYER` | `same` | Annotation layer when `text_layer` is empty |
| `VERSION` | `11` | Bumped when the controls change; v01 definitions gain the level inputs once |
| `RELOAD_LIBRARY` | `True` | Re-import the library every solution (for library editing; set False for speed) |

## Tests

```
pip install pytest
python -m pytest -q tests
```
