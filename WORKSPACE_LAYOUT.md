# Ribbon workspace shell

The layout follows the user's Home Builder VI, Stair Builder II, Geo Route and CSG
applications. Their North / West / Center / East / South organization is used here
without adding a UI framework or a frontend build step.

| Region | Contents |
| --- | --- |
| North | Title/connection strip and task ribbon: File, Home, Draw, View, Retopology |
| West | Source-model selector, attribution, guide list and example networks |
| Center | Source/result split or overlay viewport and passive interaction chrome |
| East | Selection details, Circle radius, construction options, density/solver settings and display properties |
| South | Measurements / History / Log dock, operation status and input hints |

The palette is light by default: blue primary actions, white/gray neutral surfaces,
gold tab and panel accents, and flat SVG icons. A faint ribbon gradient and small
shadows establish depth without adding shadows to every control/panel. The dark
theme remains selectable. Introduction of this shell applies the user's new light
preference once; guide storage is untouched.

The ribbon collapses to its tab strip. View exposes Navigator, Properties and
Bottom dock visibility controls, plus Vertices (F10), Edges and Ghosted display
toggles. Properties duplicates these display options and exposes ghost opacity
(10–70%, default 28%). Drawing options include separate guide-point and source-vertex
snaps. These preferences use `retopo-1:viewer`, independently of guide history. Separators support pointer resizing, keyboard
arrows in 10 px steps, and double-click reset. Layout preferences are bounded and
stored separately from source-bound guide documents. Compact widths use side
drawers that open explicitly while the viewport takes the available width.

`src/view/WorkspaceShell.js` owns presentation state, resizing, tabs and bounded
operation-log display. It does not mutate guide geometry or history. Accepted
application state drives the contextual inspector and history dock. Circle radius
changes use the same revision-validating Command boundary as pointer edits.

Ribbon and panel/dock controls belong to the application focus scope. Pointer-free
construction survives focus transfers and resizing; an owned drag cancels before
splitter resizing. Handles reproject against current panel dimensions. Native
editable fields retain keyboard ownership. Shell changes create no document undo.

Run:

```powershell
python -X utf8 tests/verify_workspace_shell.py
python -X utf8 tests/verify_guide_editor.py
python -X utf8 tests/verify_guide_additions.py
```

Evidence covers actual region placement, palette, SVG tools, unfinished
construction, collapse/resizing, numeric Circle editing, history/log contents,
layout and guide restoration, both themes, 900 px layout and compact drawers.
Screenshots and assertions are in `tests/workspace-shell/`.

The calculation progress panel leaves the Canvas available for camera navigation.
Its Cancel button remains interactive. This changes presentation only; the server
continues to own calculation and cancellation. See [VIEWER_CONTROLS.md](VIEWER_CONTROLS.md)
for camera gestures, worker scope and the retained verification records.
