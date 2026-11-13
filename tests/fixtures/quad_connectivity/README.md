# Quad-connectivity regression fixtures

| File | What it is |
|---|---|
| `island6-750-extra-seed22-layout.obj` | A raw layout of the packaged engine (`constrained-sizes-19`): toilet island 6, request 750, the authored guide (`../island6-authored-guide.json`), "Add faces where the shape needs them", seed 22. 1,425 quads, the 75-vertex source boundary and one three-sided hole. |

`tests/test_quad_connectivity.py` uses it for `fill_triangle_holes`. The chord
from one edge of this hole runs round and ends on another edge of the same
hole. Splitting that edge only moves the hole, so the repair used to repeat
without end and the job never returned (found 2026-11-10; the same symptom as
the island 4 hang recorded in `HANDOFF.md`). Such a chord is now refused and
the hole is closed through another of its edges; the number of rounds is
bounded as well.
