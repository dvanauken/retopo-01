# Corner-zone regression fixtures

Inputs for `tests/test_corner_zones.py` (`IslandSixCorners`) and
`tests/test_crease_rows.py` (`IslandSixLocalFaces`). They pin the reported
case, the two back corners of toilet island 6 where the lip turns down into a
small foot, so that a chunky corner is named and the extra-faces result keeps
following its feet.

All meshes are island 6 (part `skp-6`), request 200, keep creases at 30°, with
the guide of job `483afe83…` (`../island6-guide-483afe83.json`). Requested
spacing h = 0.0823.

| File | What it is | SHA-256 |
|---|---|---|
| `../crease_rows/island6-source.obj` | The exact source. | `854500955181659b19c786f66c56fde5a6a2e8e8c80af680e8c866786748c003` |
| `island6-200-guide-strict-204.obj` | Strict count, 204 quads: output of the user's UI job `cfaf2c05ab3f4145bf94996391e09021` (2026-11-10, before this work; layout seed 52). The worker matrix returns the same layout for this case with vertices a few 1e-4 h away (SHA `48c6cea3…3d4c`, unchanged by this work; zone numbers 0.273 / 0.414). | `ea28aa6aa069794bcb0936aad7dd30efa1c7c37c33cb68aeeaf3578aa2fa8c01` |
| `island6-200-guide-extra-380-before.obj` | "Add faces where the shape needs them" before this work, 380 quads: output of job `registered-a1acaa465892-island6-200-guide`. | `2d0df069eb88f8653d6a70494738b9258d96a54544c494eca5ccfdda9cc26d78` |
| `island6-200-guide-extra-faces.obj` | The same option now, 436 quads: output of job `registered-f7b0f9f02bb3-island6-200-guide` (`tests/extra-faces/corners-1/extra-200-guide/`). | `af8c5381061fbb078786246691ab450e9594351b76724bd173fc849c66378015` |
| `../guide_rows/island6-200-native-guide-532.obj` | Native ZBrush ZRemesher, same source, guide at Curves Strength 100, request 200: 455 quads and 77 triangles. | `0c15860a5bcb98fed82ac9d8c55c3278400ff0aa308d8277976cd2f819f9a7b1` |

What the tests assert:

- The fixed zone the corners were first compared in (source vertices with
  y > 0.05: 633 vertices, both feet and the back of the lip), distance from
  each source vertex to the output, 95th percentile / maximum in h:
  strict 0.273 / 0.414, extra faces before 0.279 / 0.407, ZBrush 0.246 / 0.304.
  The extra-faces result is no worse than ZBrush on both (0.116 / 0.257).
- The automatic corner zones (`corner_zones.zones`) are the two feet and the
  front lip: 280, 278 and 135 source vertices. The strict mesh and the earlier
  extra-faces mesh each fail one foot on its 95th percentile (0.33 and 0.36 h
  against 0.25 h); the extra-faces result passes all three.
- With local faces (`crease_rows.local_sizes`) 18 crease chains need a row:
  the four long ones and 14 short ones in the feet. ZBrush has all 18, the
  strict mesh 11, the earlier extra-faces mesh 13, the extra-faces result 18.
  With requested faces the three-row check is unchanged and still passes the
  strict mesh.

ZBrush's mesh is the reference for what following the feet means. It is not an
acceptance standard: one of its feet is at 0.26 h on the 95th percentile,
just over this application's 0.25 h corner limit, and its quads fail every
shape limit of the application (39 % of them have an edge ratio above 3.5).
