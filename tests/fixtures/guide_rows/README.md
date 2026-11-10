# Guide-row regression fixtures

Inputs for `tests/test_guide_rows.py` (`IslandSixGuide`). They pin the reported
case so the guide check cannot accept a zig-zag chain again.

| File | What it is | SHA-256 |
|---|---|---|
| `../island6-guide-483afe83.json` | The one authored guide of job `483afe83c71d40d2858066813a3f553a` (323 samples, 13.7 requested faces long, source coordinates). Copy of that job's `curves.json`. | `96a7338c519b31c8d041193afb98dfd019ca741ed9e2a8dc6176b6a51ce05aa4` |
| `../crease_rows/island6-source.obj` | Toilet island 6 (part `skp-6`), exact source. | `854500955181659b19c786f66c56fde5a6a2e8e8c80af680e8c866786748c003` |
| `island6-200-zigzag-209.obj` | The 209-quad output of job `483afe83…` (request 200, 30° creases, that guide), accepted on 2026-11-10 before the guide check asked for a loop. | `e18428ba9a5ded5794957731e44601eaee72f60db0ccb55b58d37996b1e89141` |
| `island6-200-native-guide-532.obj` | Native ZBrush ZRemesher on the same source with the same guide at Curves Strength 100, keep creases at 30°, request 200: 455 quads and 77 triangles. From `runs/native-rim-investigation/native-captures/guide/island6-guide-keep-creases-0.2k-guide100-b1/after.obj`. | `0c15860a5bcb98fed82ac9d8c55c3278400ff0aa308d8277976cd2f819f9a7b1` |

What the tests assert, at a requested spacing h = 0.0823:

- The zig-zag mesh fails on `turns` and on nothing else: its cheapest connected
  path along the guide has 15 vertices and turns onto another edge loop at 8 of
  them, while lying within 0.12 h of the guide everywhere. The older limits
  (0.20 h at the 95th percentile, 30° direction) still pass it.
- The native mesh passes: one loop of 14 vertices, no turns, 0.14 h at the 95th
  percentile, 0.19 h maximum, 0.54 h at the open ends.
- The native mesh made without the guide (`../crease_rows/island6-200-native-374.obj`)
  fails, so the check is not satisfied by any nearby edges.

The native mesh is the reference for what following a guide means. It is not an
acceptance standard for face count or quad shape (532 faces for a request of
200, 77 of them triangles) and is not used by the solver.
