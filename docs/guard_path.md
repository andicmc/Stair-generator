# `guard_path` contract (version 1)

Every stair type outputs a `guard_path` object that a guard / railing component can
consume without knowing how the stair was built. The core returns it as a Python dict
(`result["guard_path"]`); the Grasshopper component outputs it as a **JSON string**
(output `guard_path`) with every point already moved into the document frame.

Units: millimetres in the core. In the JSON from the component the points are in the
document's units and `document_scale` says what one mm became (1.0 in a mm document,
0.001 in a metre document); `width`, `rise`, `run`, `length` are scaled the same way.

```json
{
  "version": 1,
  "units": "mm",
  "stair_type": "L",             "turn": "left",
  "width": 900.0,                "rise": 200.0,
  "sides": {
    "left":  { "polyline": [[x, y, z], ...],
               "segments": [ {"kind": "flight",  "flight": 0, "start": 0, "end": 7},
                             {"kind": "landing", "flight": 0, "start": 7, "end": 8},
                             {"kind": "flight",  "flight": 1, "start": 9, "end": 15} ],
               "breaks": [7, 9],
               "length": 5123.4 },
    "right": { ... }
  },
  "steps": [
    { "index": 0, "kind": "step", "flight": 0,
      "nosing": [x, y, z], "nosing_left": [x, y, z], "nosing_right": [x, y, z],
      "tread_centre": [x, y, z], "z": 200.0,
      "direction": [dx, dy], "run": 255.0, "rise": 200.0 },
    ...
  ]
}
```

## Sides

`left` / `right` are **looking up the stair**. For a left-turning stair the left side is
the inner (well / newel) side.

Each side is one 3D polyline from the bottom of the stair to the upper floor:

| segment `kind` | what the points are |
|---|---|
| `flight`  | the **nosing line**: one point per tread at the nosing (front-top edge, after the nosing projection), at the stair edge; then the point where the flight meets the landing / upper floor edge (at that surface's height). For a spiral: outer / inner nosing points. |
| `landing` | the landing's **walking surface edge** on that side, corner by corner, level. Inner side of a 90° landing = 1–2 points, outer side = 3 points; 180° landing outer side = 4 points. |
| `winders` | inner side: the newel corner at the bottom and at the top of the winder set (a vertical pair). Outer side: the outer end of each winder's nosing, then the exit edge point. |

`segments[i]` gives index ranges into `polyline` (inclusive). Consecutive segments
either **share** their junction point (`start == previous end`) or are adjacent
(`start == previous end + 1`). `breaks` lists the `start` index of every segment whose
kind differs from the one before it: these are the points where a flight meets a landing
or a winder set.

Between a landing's exit point and the first nosing of the next flight the path rises by
one riser (the first nosing is one rise above the landing). The guard component resolves
this (gooseneck / transition) using the two `flight` nosing lines and the level landing.

Points are deduplicated: no two consecutive polyline points coincide. `z` never decreases
along a side.

## Steps

One entry per walking surface, in walking order, `index` = position in the list:

- `kind`: `step` (flight tread, also the top tread when `top_connection = "top_tread"`),
  `winder`, `landing`.
- `flight`: index of the flight the step belongs to; a landing / winder set carries the
  index of the flight **before** it.
- `nosing`: centre of the leading edge (spiral and winders: at the walk line,
  `walkline_offset_mm` from the inner edge). `nosing_left` / `nosing_right`: the ends of
  the leading edge. For a landing: the leading edge of the landing.
- `tread_centre`: centroid of the walking surface.
- `direction`: unit vector of travel (x, y) at that step.
- `run`: going at the walk line; `rise`: height of the riser **below** this step (0 for a
  landing and for the first winder, which is reached by the flight's last riser).

## Guarantees

- Both polylines start at the first nosing (z = one rise) and end at the upper floor
  (z = floor_to_floor) — except `bottom_connection = "starter_tread"` does not change the
  path (the extension is outside the clear width).
- `steps` count = treads + winders + landings; indices are contiguous from 0.
- Right-turn stairs are exact mirrors of left-turn stairs (y → −y) with the side labels
  swapped.
