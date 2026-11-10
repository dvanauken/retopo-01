# Crease-row regression fixtures

Inputs for `tests/test_crease_rows.py` (`IslandSixRim`). They pin the reported
jagged-rim case so the crease check cannot accept it again.

| File | What it is | SHA-256 |
|---|---|---|
| `island6-source.obj` | Toilet island 6 (part `skp-6`), exact source: 1,441 vertices, 2,824 triangles. Copy of `runs/parts/617dd8f6…/source.obj`. | `854500955181659b19c786f66c56fde5a6a2e8e8c80af680e8c866786748c003` |
| `island6-200-screenshot-188.obj` | The 188-quad output of job `3029972da0174acd9845b6ec0df6e3ea` (request 200, 30° creases) that passed every check on 2026-10-28 while its rim was jagged. | `685670dd365d067ee21b3c0d753a3b30b8f53a8d3a4a3d1861b54e3f48ff4cfe` |
| `island6-200-native-374.obj` | Native ZBrush ZRemesher on the same source, keep creases at 30°, request 200: 364 quads and 10 triangles. From `runs/native-rim-investigation/native-captures/baseline/island6-keep-creases-0.2k-current30-a1/after.obj`. | `8ad49f146bcd1dbee7e40886d74e515af5c4f4d11c2429eede58cfa79bfd71bd` |

What the tests assert, at a requested spacing h = 0.0823:

- The representative crease chains are the upper rim (source vertices 613 to
  1321, 34.3 h), the hinge underside step (489 to 1202) and the hinge top edge
  (724 to 1426). The witness edge [1308, 1309] lies on the first.
- The screenshot mesh fails on its rim row (0.32 h from its best connected edge
  path at the 95th percentile, against the 0.25 h limit) and on nothing else:
  every older nearest-edge limit still passes it.
- The native mesh passes all three rows. The test measures its 364 quads; its
  10 triangles are left out of the edge graph.

The native mesh is a reference for what a rim row looks like at about twice the
face budget. It is not an acceptance standard and is not used by the solver.
