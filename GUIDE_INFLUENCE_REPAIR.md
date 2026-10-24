# Guide influence and test subjects

The user-reported run was `bc9a3dc8914348a78335aedbfc891390`, at target 600,
with the exact 23 submitted surface samples retained in
`tests/guide-influence/original/curves.json`. The original result was labeled
Generated/Good, but its `guidePaths` array was empty.

The partial curve is monotonic in angular travel but reverses its radial travel.
The previous span-ratio classifier treated it as a radial spoke, sorted its samples
by radius and lost their authored traversal. Spokes also never produced measured
output paths, so the worker's guide-quality gate checked nothing for this curve.

Classification now considers monotonicity and retains angular parameterization
for this curve. True radial spokes retain their radial parameterization, displace
neighboring columns monotonically, and produce measured open edge chains. Every
guide handled by the structured backend must own an output-edge path; omission
rejects the candidate before successful export. The existing distance/tangent and
quad-quality limits remain in force.

| Independent output measurement | Original | Repaired |
| --- | ---: | ---: |
| Face count, target 600 | 624 | 600 |
| Guide-to-edge p95 distance | 0.06953876 | 0.01846834 |
| Guide-to-edge p95 tangent mismatch | 61.75465° | 11.67258° |
| Tracked connected output-edge path | Missing | Present |

`tests/verify_guide_influence.py` reproduces the exact submitted samples through
the real worker, compares a same-target unguided baseline, independently rereads
the OBJ, verifies the tracked path uses actual edges, and measures surface
preservation. It also verifies a true radial-spoke case and a negative control
that deliberately removes path evidence. That negative control must fail.
Outputs and measurements are retained under `tests/guide-influence/`.

The tracked contour is a complete grid cycle; an open input guide controls its
covered portion, with continuation elsewhere. This does not change the authored
guide's closure. Measurements remain bounded sampling, not a Hausdorff certificate
or a promise of exact interpolation of every freehand sample.

## Plain white toilet fixture

The source is the actual user-provided `SW_Toilet.closed.web.glb`, retained under
`assets/raw/toilet/`, SHA-256
`2c34e0475446d832c6e9eeeb97c749534b4553e6a5566626b502e3079c936d78`.
The gold variant is not imported. Blender's Draco importer decodes the original
12,000 vertices and 24,000 triangles. A similarity converts it to the application's
normalized Z-up source frame. Five original collapsed triangles require six local
conformity operations, splitting their opposite neighbors at already-existing
vertices. All vertex positions and the physical exterior are retained; no
decimation, replacement geometry or generated approximation is used.

The prepared mesh is one closed, consistently wound, genus-one component with
24,000 nondegenerate triangles. White `#f5f5f2`, metallic zero, and smooth porcelain
shading are presentation overrides. A bowl-contour preset is a real horizontal
section of the mesh at normalized z = 0.1. The nearest-surface adapter uses a spatial
index for this more detailed test fixture. Selection, drawing, editing, native
guide IO and both host themes are exercised in Chromium.

The current general solver **does not produce a qualified toilet retopology**.
Its actual guide-driven attempt passes source validation, then creates a
degenerate triangle inside its recovered quality/densification stage and rejects.
The fixture is marked experimental with this limitation in its visible solver note.
The failure is retained as evidence; it is not shown as a successful result or
replaced by a canned preview. Fixing general solver conditioning is separate from
importing the test subject. The existing recovered engine files remain untouched.

Reproduce import with Blender 5.1 and the project's Python environment:

```powershell
python -X utf8 scripts/import_toilet.py
```

Provenance and exact output hashes are in `assets/raw/toilet/preparation.json`.
Original source attribution was not recorded in the supplied model collection.
