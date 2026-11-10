# Handoff: retopo-1 low-count open parts and the island 6 rim

Written 2026-11-09 for the next agent (Fable 5.2). It covers the state left on
the night of 2026-10-28. Read it fully before changing solver code.

## 1. What this project is

retopo-1 is a local retopology app: an HTML canvas UI (ES modules, vendored
Three.js) over a Python solver process (`server.py` → `worker.py`).
Topology comes from a modified QuadriFlow child process,
`engine/guided-quadriflow/quadriflow.exe`. The NumPy/PyTorch side fits,
repairs and checks the result. The goal is to match ZBrush ZRemesher's behavior.
The rules come from native code recovered in the Ghidra workbench
`C:\dbva\code\ghidra-workbench`. The test asset is the SketchUp toilet, split
into 11 original parts. Islands are addressed as part ids `skp-N`, loaded with
`mesh_parts.load_part`.

Start the app with `.\start.cmd` (normally http://127.0.0.1:8741). Running
`start.cmd` again restarts this checkout's server. The user may already have it
open: keep their origin and browser storage.

## 2. How the user wants the work done

These preferences are firm. Each one came from a correction.

1. **Do the work, don't propose it.** For hard solver problems, investigate end
   to end: read workbench evidence, decompile or trace native code, run native
   ZBrush as a reference, implement, and verify in the real UI. Lead with
   results and evidence. Ask only about real product or policy decisions, never
   "which step should I start?". Native runs and Ghidra reading are authorized.
2. **No invented constants.** Before changing the solver, read the relevant
   recovery documents under the workbench's `targets/zbrush/understanding/**`
   and the `recovered_*.py` arithmetic. Then implement the native rule with its
   constants and evidence level. If no native rule exists, say so and label the
   constant as an engineering choice. Threshold patches drew the reaction
   "Are you creating hacks?".
3. **Tolerances are in faces.** Acceptance limits are measured in units of the
   requested face size h, and maxima stay at face scale (½–1 face). Never cap a
   limit by model size. The user's words: "The limit should be a single face…
   why can't the mesh reduce to the number of faces that we ask for. It can."
   Low counts must work.
4. **Report honestly.** Retain failed candidates as failures. Never present a
   diagnostic mesh as an accepted result. Say what is and is not claimed. The
   existing docs follow this style closely; keep it.
5. **Never delete `runs/` folders by time window.** The user generates jobs from
   the same UI while you work. Delete only job ids that your own scripts printed.
   List the deletion set before deleting. An earlier session deleted the user's
   job `e2a47eb8` and the island 6 source folder `runs/60e34fcd…` this way.
6. UI work follows `C:\dbva\code\web-component-II` for look and feel (see the
   user's global `CLAUDE.md`). The workbench has its own `AGENTS.md` and
   `DESIGN.md` for anything written there.

## 3. Current state of the repository

- Branch `main`. Last commit `76af2d7 WIP`. Git works now; a previous session
  reported a "dubious ownership" refusal. If it returns, use
  `git -c safe.directory=* …`.
- **Uncommitted** (the rim investigation; see section 4.1):
  - `GUIDED_LAYOUT.md`: new section "Exact screenshot rim investigation".
  - `engine/targets/zbrush/experiments/python/recovered_torus_integer_geometric_rows.py`,
    `recovered_unit_constraint_elimination.py` (modified),
    `recovered_integer_geometric_rows.py` (new).
  - `tests/test_native_integer_callback.py` and `tests/fixtures/native_integer/`.
  - `engine/guided-quadriflow/development/native-rim-verification.json`.
- Tests: run `python -X utf8 -m unittest discover -s tests -p "test_*.py"`. On
  2026-11-09 it reported 183 run with 1 error. The error is a Windows file-lock
  race in `test_server_startup` tearDown (`startup.log` still open), not a solver
  failure. It left `runs/startup test njeowui_` and `runs/startup test my8m2y14`
  behind. The fix belongs in the test's cleanup.
- Packaged engine: build `size-caps-16`, SHA-256 `e94fd633…c196` (details in
  `GUIDED_LAYOUT.md` → "Runtime and reproduction"). It needs MinGW DLLs from
  `C:/msys64/mingw64/bin` or `RETOPO_MINGW_RUNTIME`. Hashes are checked at run
  time. No experimental engine has been promoted.

## 4. Open issues, in priority order

### 4.1 The island 6 rim is jagged but accepted (active issue)

User-visible symptom: screenshot job `3029972da0174acd9845b6ec0df6e3ea`
(island 6, target 200, 188 quads). The pink crease rim zig-zags.

What was established:

- The rim is **not protected by any hard check**. None of the 283 pink crease
  edges, and none of their vertices, lies on the true open boundary. That
  boundary is an inner loop under the folded lip, and it passes (max 0.062 h,
  limit 0.1 h). The visible outer fold is covered only by the crease and
  whole-surface checks.
- **Why the jagged rim passes:** at witness source edge [1308, 1309] the nearest
  output edge is 0.422 h away. The crease check subtracts a band allowance
  around each crease, which brings the 95th-percentile error from 0.328 h down
  to 0.199 h (limit 0.25 h). The check accepts nearby unrelated edges; it never
  requires a connected row along the rim.
- **Native ZBrush reference** (exact source, keep creases, 30°, request 200):
  374 faces (364 quads, 10 triangles). Its rim error at the same witness is
  0.011 h, and the left rim has an ordered edge row. This is evidence of what
  good looks like at about twice the budget. It is not proof that 200 quads
  can be reached.
- **Native integer-solve corrections** (in the `recovered_*` scripts, from
  `0x28fe70` and mode 2 elimination `0x288f50`):
  - Mixed guide/seed separation candidates were wrongly rejected when the
    gap was 4.5 or more.
  - Soft gaps of at least 1.35 now keep their target instead of being clamped
    to 1.
  - Constant-only rows are skipped without using up a pivot.
  The new test reproduces ZBrush's captured integer step exactly for this part
  (129 residuals, 160 constraints, 125 dependencies, 21 nested variables,
  71 outer fixes). The test starts from captured upstream data, so it does not
  rebuild the whole remesher. 19 optional candidates are legitimately left
  unsatisfied. Locking every candidate independently is **not** the native
  method.
- **QuadriFlow lock experiment (not promoted):** it fixed two engine bugs.
  Flip contraction removed locked separation edges, and `FixValence` cycled on
  non-reciprocal adjacency (three faces sharing edge [104, 105]). Engine
  `9343e8a5…` runs fast, but every rim-locking run still rejects because of
  path-ownership merges and broken rows. It also fails a control that the
  frozen v3 engine passes. Material is in `runs/native-rim-investigation/qf-locks/`.

**Next milestone:** an app-owned parameter chart plus a combined solve that
keeps the rim identities as continuous rows through extraction. Concretely:
1. Export the app's continuous field just before `ComputeIndexMap`.
2. Build a cut/fan parameter chart, guide scalar groups, singular seeds and
   seam periods.
3. Feed the tested native integer callback from those instead of from
   captures.

Two pitfalls:
- QuadriFlow's `mO` holds local 3D lattice origins, not consistent UVs, so
  projecting `(V - O)` does not give a chart.
- The recovered closed-surface wrappers reject open edge-angle/seed cases, some
  branching guide groups, and the candidate sentinel case. These producers need
  qualified open-part versions.

Also consider whether the crease check should require an **ordered, connected
row** along admitted creases instead of nearest-edge distance after band
subtraction. That check is what let the screenshot through. Ground any new
limit in face units and native measurements.

### 4.2 Island 6 at 150 quads with the native 30° crease angle

200 → 188, 300 → 268 and 750 + guide → 839 all pass at 30°. At 150, the best
candidate clears the shape, crease and contact checks but fails the **0.5 h
surface-deviation** limit. It passes at 45°, which is available per part.
This may be a policy decision (4.5) rather than a solver change.

### 4.3 Island 6 at 150 with a guide; island 5

Both are unsolved. Island 5 is closed and failed before any of the low-count
work. Islands 2, 7 and 10 pass (291, 339 and 456 quads).

### 4.4 Native stages not yet ported

Listed largest expected effect first:
1. Five-radius valid-window selection by direction consistency.
2. The coupled least-squares sizing objective.
3. Source conditioning to the ≥ 3000-triangle budget before the field.
4. Guide embedding with integer registration.
5. The attachment surface walk.

### 4.5 Policy decisions waiting on the user

Ask about these; do not decide them silently:
- **Count band ±15 %.** Native island 6 with creases kept lands +17 % to +35 %.
- **Quad-only output.** Native emits some triangles at low counts.
- **Surface 0.5 h and boundary 0.1 h at ≤ 300 faces.** These alone fail the
  caps layouts at 150.
- **Shape checks.**

## 5. Verification for any solver change

- Unit tests (section 3).
- `tests/verify_registered_features.py` runs island 6 at 150/200/300,
  750 + the authored guide (`tests/fixtures/island6-authored-guide.json`),
  island 2 at 300, island 7 at 300 and island 10 at 500, from the part sources
  in `runs/parts/`.
- `tests/verify_registered_features_ui.py` drives the real UI. The user expects
  verification there too.
- Re-measure the screenshot rim witness for any rim work. Record the job ids you
  create so they can be cleaned up safely.

## 6. Where the evidence lives

| What | Where |
|---|---|
| Algorithm, runtime, rim investigation | `GUIDED_LAYOUT.md` |
| Errors-and-omissions audit against native rules (§8 = size caps) | `ghidra-workbench/work/retopo-lowcount/AUDIT.md` |
| Island 6 low-count study, native measurements ("Fourth round") | `ghidra-workbench/work/retopo-lowcount/FINDINGS.md` |
| Recovered native rules | `ghidra-workbench/targets/zbrush/understanding/**` |
| Recovered arithmetic (Python) | `engine/targets/zbrush/experiments/python/recovered_*.py` |
| Engine builds, compiler records | `ghidra-workbench/work/retopo-guided-layout/` (`build.py`, `build-records/`) |
| Rim measurements and provenance | `engine/guided-quadriflow/development/native-rim-verification.json` |
| Native captures, tracers, ZBrush runner | `runs/native-rim-investigation/native-captures/` (input `inputs/island6-original.obj`) |
| QuadriFlow lock experiment | `runs/native-rim-investigation/qf-locks/` (`fan-fix/`, `fan-fix-clean/`) |
| Integer callback fixtures | `tests/fixtures/native_integer/README.md` |
| Parts workflow, older handoffs | `PARTS_WORKFLOW.md`, `REVIEW_HANDOFF.md`, `TOILET_SOLVER.md` |

## 7. Gotchas

- `ghidra-workbench/work/retopo-lowcount/run_native_island6.py` still points at
  the deleted `runs/60e34fcd…/source.obj`. Use the copy under
  `runs/native-rim-investigation/native-captures/scripts/` with
  `inputs/island6-original.obj`, or load the part with `mesh_parts.load_part`.
  Never point scripts at a run folder.
- Native ZBrush runs must use fresh, owned batch processes. Do not touch a
  `ZBrush.exe` that the user is running.
- When a heredoc patch through `python - <<'EOF'` writes C `printf("...\n")`,
  the backslash is lost. Use raw strings or `chr(92)+'n'`.
- Do not modify sealed workbench records or Ghidra databases.
- `open_surface.construct` tries 2 caps layouts (`-size-caps-exact`, with the
  request corrected up to twice from actual counts), then 3 constrained,
  4 adaptive and 3 coarsened. `weld_pinched_quads` and `fill_triangle_holes`
  repair engine extraction artifacts before the fit.
