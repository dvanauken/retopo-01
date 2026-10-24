# Surface guide editor

This subsystem is based on **Draw 2D 3.0.0-draft.21**, revised 2026-09-16:
[authoritative publication](https://parastrate.com/books/053c26bbd7c6/draw2d-spec-v3.pdf).
It implements the agreed guide-specific adaptation, not the specification's full
Base 2D profile. Base requires thirteen primitives and editable Text. This product
exposes Polyline, Spline and Circle guides, with a freehand Polyline construction.

## Drawing and editing

| Input | Behavior |
| --- | --- |
| G / Draw | Drag a freehand surface guide. Empty space splits it into provisional parts. Release commits all parts in one undo unit. |
| P / Polyline | Click authored vertices; Enter completes without the hover point. |
| C / Circle | Click the center, then the radius point. A center over the hole is supported; the rim selects the source face plane. |
| S / Spline | Click authored fit points; Enter completes a smooth surface guide without the hover point. |
| Alt+Enter | Close a clicked construction, with at least three points. |
| Backspace during construction | Remove the last accepted point. |
| Return to the first point | Within 5 CSS pixels, the first point turns green and preview snaps to it. Click (Polyline/Spline) or release (freehand) closes with no duplicate authored endpoint; ordinary point snapping need not be enabled. At least three accepted positions are required. |
| Close the next stroke | Capture explicit closure intent at the first input; clicked construction closes on completion. Freehand proximity closure uses the same 5 CSS-pixel threshold. |
| V / Select / Whole guides | Object Selection. Body click selects a guide; drag an eligible body to move the selected guides on the surface. |
| A / Edit points / Enter on Canvas / double activation | Direct Selection of the active selected guide. Drag its authored vertices or fit points. |
| Click an exposed endpoint | Direct Selection on that endpoint. An unselected endpoint can be selected and moved in one drag. |
| Shift-click guide / list entry | Toggle that whole guide; retain a surviving active Direct Selection owner. |
| Drag empty Canvas | Full-containment rectangle selection in either direction. Shift adds, preserving the existing order. |
| Delete | Delete selected guides, or the selected direct point. Invalid point counts reject atomically. |
| Reverse | Reverse selected authored point sequences, preserving IDs and closure. |
| Escape during a gesture | Discard its candidate and release native capture immediately. A point editor remains ready. |
| Escape from ready Direct Selection | Return to Object Selection, retaining the selected guide IDs. |
| Ctrl/Command+Z / Shift+Z | Document undo / redo. Selection and camera changes do not enter history. |
| Snap to guide points | Optional soft snapping: acquire at 8 CSS pixels, release at 12. Alt bypasses it, including on release. |
| Hold Space | Product extension: temporary orbit retains pointer-free construction/selection. Key release returns; Escape, blur, hidden-document and context loss discard retained interaction. Activation during an owned guide drag is rejected. |

Controls and Canvas are one focus scope. Native text fields own their keys, and
buttons retain native Enter/Space activation. Switching persistent tools discards
unfinished guide construction; selecting the already active tool is a no-op.

## State and mutation boundary

`src/domain/GuideDocument.js` owns immutable authored guides, runtime identity
counters, the document epoch, and sequential atomic Commands. Its transaction is
`execute(label, afterValues, expectedTargets, epoch)`. Each history record has its
own ID, label, complete before/after values, and an implicit complete affected set
computed from those values. There are no concurrent Scene writers. An equal
result creates no history, revision increment or publication and preserves redo.

An edit captures its source guide IDs, revisions, immutable values and original
press point. Each pointer sample derives from those baselines. Candidates never
replace accepted guides before release. Invalid movement keeps the baseline and
reports invalid status; invalid release rejects the submission rather than
committing an older valid preview. Undo/redo restore exact authored values while
runtime revisions continue increasing, including after deletion and restoration.

`src/view/GuideController.js` owns routing, selection, construction, pointer
ownership, temporary navigation and cleanup. Browser adapters copy native input
into normalized values. Its immutable inspection snapshot is copied separately
from live draft buffers. Document updates reconcile selection before UI refresh.

The renderer subdues the baseline while painting an edit candidate. A separate
passive Canvas paints selection frames, fixed CSS-pixel handles, a start marker,
direction arrows, a rectangle preview and snap feedback. Handle paint and hit
testing consume the same descriptions. Both comparison panes edit the original
source surface. Hidden or occluded guide points cannot be hit. Body hit tests use
projected segments, including derived spline segments, rather than sample dots.

## Surface extension and declared policies

Input is 2D Canvas CSS-pixel input; authored positions are finite **source-frame
XYZ**. Source SHA-256 binds exported records to the mesh. There is no global flat
2D coordinate chart for this mesh, and the perspective camera replaces the
specification's planar affine Viewport contract.

Polyline segments and Spline spans are authored geometry; their derived solver
paths are lifted to the nearest source triangle. Triangle traversal order breaks
equal-distance ties. An input or intermediate sample farther than **0.05 source
units** from the source rejects, including a segment across the through-hole.
Whole-guide movement applies the Canvas displacement to each baseline point's
projection and raycasts it back to the source. It can deform a guide on a curved
surface; it is explicitly a surface move, not a rigid 3D translation. Every point
of every selected guide must project successfully or the whole move rejects.

The Spline algorithm is `centripetal-catmull-rom-v2-surface-xyz`. It extends the
specification's Barry–Goldman evaluator componentwise to XYZ, using 3D chord length,
alpha 0.5, the fixed 1e-9 knot floor, reflected open endpoints and wrapped closed
fit points. It has its own identifier because it is not the normative 2D evaluator.
Cubic control-hull subdivision bounds the unprojected curve at 0.002 source units
and limits chord length to 0.04 before lifting. Polyline segments use a maximum
0.04 source-unit sampling step. These do not constitute a certificate of the
continuous projected path or resolve arbitrary thin-sheet/nearest-surface branch
ambiguity. No successful partial sampling result is substituted on budget failure.

Limits are 48 guides, 2048 authored points per guide, 2048 derived samples per
guide, 8192 derived samples per document and 8192 evaluator/subdivision work units
per Spline flattening call. Numeric operation failure is explicit. Selection drag
threshold is greater than 4 CSS pixels; double activation is at most 400 ms and
6 CSS pixels. Point/segment hit tolerance is 8 CSS pixels. Snap candidates are
ordered by distance then stable guide/point ID, with hysteresis validated against
document epoch/generation and camera revision. Self-edited guides are excluded.
Only point snapping is offered; grid, tangent and intersection snapping are absent.

Scale, rotation, unrestricted topology insertion, Bezier/NURBS, filled Polygons,
analytic Arc/Ellipse construction and standalone Point/Vertex creation are
not offered. No controls or handles imply those capabilities.

## Native guide IO

`src/io/GuideSerializer.js` writes deterministic JSON with lexically sorted keys,
fixed whitespace and authored array ordering. Version 3 stores `format`,
`schemaVersion`, `coordinateFrame`, `sourceSha256`, and immutable `guides` with
stable guide/point IDs, type, closure and the Spline algorithm ID. Circle retains its analytic radius, normal and radial axis plus one stable center record; its radius grip has a stable semantic ID. It is never serialized as a sampled polygon. Version 2 Polyline/Spline files remain readable. Runtime revisions
and selection are not persisted. Signed zero has no distinct authored meaning.

The additional `curves` field is a **derived compatibility export** for the current
worker/legacy tools. It is not a second authoring authority. Closure is an explicit
flag in authored data; the solver adapter derives its repeated first sample.
Write/read/write preserves the native file bytes on the same source and policy.

Versionless legacy `coordinateFrame: source, curves: [...]` packets migrate into
Polyline records with newly allocated IDs, recognizing a repeated closing sample.
Legacy local storage is migrated the same way. New packets require a matching
source hash; future schema versions, unknown fields inside authored records,
invalid counts/IDs/numbers, dangerous data keys and excessive nesting reject
before mutation. File reads capture an epoch, generation and import ticket; a
late result cannot replace another source or newer edits. Loading guides is one
undoable replacement Command. Browser local storage remains an optional convenience;
Export/Save guides writes an explicit portable file, not a filesystem save guarantee.

## Requirements and evidence

| Specification authority | Adapted behavior | Evidence |
| --- | --- | --- |
| §§0.2, 1.2, 1.5 | Pure geometry, immutable boundaries, declared numerical policy, versioned evaluator | Node regression suite; module import check |
| §§2.1.5, 2.2 | Stable identities, monotonic revisions, sequential atomic history, no-op and stale-edit handling | Node multi-target failure, history, epoch and no-op tests |
| §3.2.2 | Object/Direct Selection, hit-sensitive entry, ordered membership, containment and model transitions | Real browser selection and marquee tests |
| §3.2.5 | Baseline-derived candidates, point editing, multi-edit, cancellation, Reverse and point deletion | Real browser mid-gesture snapshots and screenshots |
| §3.2.6 | Explicit soft point snap policy, stamps, exclusions, hysteresis and bypass | Node snap tests and actual browser point drags |
| §§3.3.6–3.3.11 | Native capture, final release sample, split construction, focus/cancellation and retained construction | Real browser capture-before-up, touch cancellation, temporary navigation and split-stroke checks |
| §§4.2–4.3 | One frame owner; passive chrome; shared handle paint/hit descriptions | Dark/light, preview, right-pane and narrow-layout screenshots |
| §§5.1.1, 5.1.5 | Bounded native parsing, exact authored IO, migration, source/epoch guards | Node byte-roundtrip tests; actual download, file input and browser reload |
| §6 | Composed application behavior and solver integration | `tests/verify_guide_editor.py`, including real freehand and Spline worker solves |

Run:

```powershell
node --test tests/guide-editor.test.mjs
python -X utf8 tests/verify_guide_editor.py
python -X utf8 tests/verify_guide_additions.py
python -X utf8 tests/verify_guide_influence.py
```

The browser test owns a temporary server on a free loopback port and a separate
browser context. It does not clear an existing user's origin or restart their server.
Evidence and screenshots are in `tests/guide-editor/`. Historical verification under
other test directories describes earlier snapshots; `BUILD_MANIFEST.json` remains
the original import's manifest, not a claim about these changed files.

Circle body selection enters Direct Selection. Center and radius edits are independent, revision-validating undo units; Reverse is unavailable. The center may remain off the surface over a hole, while the derived circumference must pass the same source-lifting checks as other guides. The Circle sampling bound uses circular sagitta and maximum chord length.

The original plain white toilet is available as a source test subject. See `assets/raw/toilet/preparation.json` and `scripts/import_toilet.py` for reproducible Draco decoding and the six local conformity operations. The current general solver rejects this mesh during numerical conditioning; drawing, selection, editing and guide IO work, but no qualified toilet retopology is claimed.

The application shell follows the user’s North / West / Center / East / South layout. Drawing and edit commands live in the ribbon; source and guide navigation are left; Circle radius, drawing and solver properties are right; measured results, history and logs live in the bottom dock. Shell focus transfers and panel resizing preserve pointer-free construction. See `WORKSPACE_LAYOUT.md`.
