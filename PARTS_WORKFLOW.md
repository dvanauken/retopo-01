# Working with source parts

Use **Navigator → Parts** to work on a source region independently. The original
asset is never overwritten. All prepared pieces stay in the source coordinate
frame, so their results can be displayed and exported together.

## Toilet walkthrough

### Virgin SketchUp source

Choose **White toilet — original SKP parts** for the fresh import from
`C:/dbva/code/ach-symbols/models/SW_Toilet/SW_Toilet.skp`. A byte-for-byte source
copy is retained in `assets/raw/toilet-skp/SW_Toilet.skp`. This is separate from
the processed **White toilet** below.

The new source has 25,809 triangles in 11 selectable objects: ten connected
toilet islands and the original flat CAD reference. The hidden component
definition is not duplicated into the assembly. SketchUp faces are triangulated
for the viewer; coordinates are uniformly normalized and rotated, with no
welding, caps, hole filling, decimation, or remeshing. Original island names
are retained without guessing semantic part names. Two islands are closed;
the other nine preserve their original open boundaries.

Select a part directly in the viewport or Navigator (Shift-click toggles multiple
objects). Selection highlights it without changing the camera or working source.
Choose **Work on selected** to isolate one included part, then set its density
and guides. Or click **Generate selected** directly: it opens the selected part,
keeps the displayed target count and generates with that part's saved guides.
Multiple or excluded selected parts disable generation with a tooltip explaining
the reason. **Show assembly** returns to the full included assembly. Use
**Exclude selected** or **Keep only selected** to change inclusion, and
**Restore all** to bring original imported parts back. **Show other parts** adds
assembly context while working. Rename parts as they are identified and use
**Assembly OBJ** to export the included objects. Selection is global across
parts and current guides; working-part scope is a separate operation.
Original imported open parts can be generated independently with their open
boundaries preserved. No caps are added. Select **C-3639 island 2**, choose
**Work on selected**, and use target **500** for a verified first pass. It
produced 551 quads without a guide and 481 with a short browser-drawn guide;
both passed the same quality, boundary, surface, feature and contact gates.

This does not guarantee a remesh for every island/target. The large outer body,
several small fittings and the CAD reference failed checks at their default
targets in the broader audit. The app reports rejection and retains the original
and any last accepted result. Changing a target or guides is an explicit user
choice. `runs/open-parts-suite-1f0b00c7/report.json` and
`runs/open-corners-b553b327/report.json` retain those negative results.

**Undo inclusion / name** and **Redo** reverse an entire include/exclude/rename
command, including multi-part changes. Selection and camera changes do not
create history. The guide Undo/Redo controls apply to the current working
source; split restoration remains **Undo split**. These histories are session
scoped; saved projects retain accepted state and per-part inputs/results.

Reproduce with Blender's installed `sketchup_importer` using
`scripts/extract_skp_parts.py` (arguments after `--`: source SKP and
`assets/raw/toilet-skp/source-parts.json`), then run
`python scripts/import_toilet_skp.py`. The latter recreates prepared part files
under `runs/parts`; retain that folder or rerun preparation on another checkout.
`tests/verify_skp_parts.py` checks exact triangle partition conservation,
browser selection of all eleven parts, and multipart export. The parts document
tests cover imported roots, subsequent splits, undo, and project roundtrips.

### Previously processed closed source

1. Choose **White toilet**, then open **Split or exclude a region**.
2. Choose **Select flush handle**. This is an editable starting selection of
   273 source triangles, not automatic semantic part recognition.
3. Choose **Preview face split**. Orange shows the excluded region and gold
   shows the repair on the retained body. **Apply split** accepts that working
   source; **Cancel** leaves the source and part tree unchanged.
4. With the retained body active, name the next part **Tank lid**, turn off
   **Exclude selected region**, and set a **Z** plane cut to **0.82**.
5. Choose **Preview plane split**, review the two pieces and repair caps, then
   **Apply split**. The lid is now isolated. Set its target to **800** and use
   the existing drawing tools and **Generate** button.
6. **Assembly** shows the other included pieces in context. **Assembly OBJ**
   exports each piece as a named object, using accepted retopology where it is
   available and explicitly named working-source geometry elsewhere.

The 0.82 plane is a practical cut through this source's upper tank/lid region;
it is not a recovered manufacturer part boundary. Adjust it in the preview.

## Selection and independent editing

**Paint faces** selects only visible source faces. Drag to add, hold **Alt** to
remove, and orbit with the usual mouse controls. **Grow**, **Shrink**, and
**Clear** operate on the face selection. Face splitting follows existing
triangle edges. Plane splitting cuts intersected triangles at the exact plane,
adds new boundary vertices, and verifies closed pieces and volume conservation.

Each part has its own guides, target, source identity and accepted result.
Changing or generating one part preserves siblings. A changed guide or density
marks an existing result as previous; assembly export requires that part to be
regenerated. Excluded parts are omitted from the export. A missing accepted run
causes an export error instead of silently replacing its retopology with source
triangles.

Closed parts can be excluded and restored. An excluded open region, such as the
handle, is retained for inspection but cannot be solved independently. **Undo
split** restores its original attachment; undo later splits first. Earlier
branch records and accepted runs remain retained. The original reference is
always available through **Original**.

Parts and per-part guide settings are saved in this browser origin. **Save
parts / Load parts** transfer the project tree and settings within this local
checkout. Prepared sources and accepted job files live under `runs/`; keep that
folder with the project. The JSON is not a standalone geometry archive. Accepted
part viewing and native OBJ downloads also work after restarting the service.

## Boundary and validation scope

This milestone assembles **separate objects**. Repair caps remain on those
objects. It does not weld independently generated boundaries into a continuous
quad surface, and assembly export is not a claim of gap-free or collision-free
interfaces. Shared boundary constraints and a final stitched-surface audit are
needed for that later operation.

Face cuts currently accept one connected region with one simple, sufficiently
flat boundary loop. Branched boundaries, multiple openings, projected folds,
inverted caps and new cap/surface contacts reject without applying the split.
The positive side of a plane becomes the new part; planes producing disconnected
pieces reject. Existing source contacts are not relabeled as repaired by a cut.

Gold highlights the most recent cut's caps. Earlier repairs remain recorded in
the parent-source chain and can be reviewed by undoing to that step.

The solver validates each closed part against its explicitly prepared working
source, including repairs, with the existing source-feature, quad-quality,
surface, contact and guide-path gates. That is distinct from validating the
modified shape against the untouched toilet, which would demand restoring a
deliberately removed handle.

## Recorded checks

- `tests/test_mesh_parts.py`: original-coordinate preservation after handle
  exclusion, real toilet lid splitting, exact shared-plane coordinates, closed
  topology, volume conservation and rejected input.
- `tests/parts-document.test.mjs`: sibling output preservation, reversible
  state, project validation and OBJ object/index boundaries.
- `tests/test_parts_api.py`: immutable source binding, admission replay,
  changed-part conflicts, invalid IDs and foreign-source rejection.
- `tests/verify_parts_browser.py`: actual handle/lid workflow, selected-part
  worker, assembly download, settings/output reload, undo and project import.
- `tests/verify_parts_interactions.py`: real pointer selection, per-part guides,
  stale output handling, late preview cancellation and download after restart.

The first live browser lid job is
`runs/4156a46d05e54683a4124ce0938e7ab8`: **879 quads at target 800 in 22.66
seconds**. Its re-read OBJ passes the independent reference contact and
whole-surface audit in `reference-export-audit.json`. Browser evidence is in
`runs/parts-browser-8c865ea3/`. This timing applies to the isolated lid; the whole
toilet and arbitrary guide networks have different costs and may reject.

A real drawn guide on the isolated lid also passed through the live service:
`runs/53ccd0f4815d4eae85818f7d9af237e0`, **809 quads at target 850 in 80.75
seconds**. The interaction report and screenshot are in
`runs/parts-interactions/`. Run the browser workflow test before the interaction
test; the first writes a manifest identifying its fresh project and job for the
second. Both accept `--url` to use an isolated local test server.

The guided export also passes the independent reference audit in its job
directory. The restarted main app repeated the complete unguided workflow in
`runs/parts-browser-a386256f/` (job `66dce6ccdacc48ecad8af3ffef09f667`). The final
app smoke check is `runs/parts-final-smoke.json`. The 24 guide/domain checks,
three geometry tests, three part API tests, six job-race tests, two density API
tests and the original density/rendering browser check pass in their stated
scopes. Plane preparation uses the pinned `networkx` dependency already present
in the tested environment; no global environment changes were made.
