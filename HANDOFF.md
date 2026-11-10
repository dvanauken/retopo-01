# Handoff: retopo-1 low-count open parts and the island 6 rim

Written 2026-11-09 for the next agent (Fable 5.2). It covers the state left on
the night of 2026-10-28. Read it fully before changing solver code.

**Update, 2026-11-09 evening:** the island 6 rim (section 4.1) is fixed for open
parts. Sections 3, 4.1, 4.2, 4.3, 5, 6 and 7 are updated for that work; the
rest is as first written.

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

- Branch `main`. Last commit `a7e28fe WIP` (2026-11-09 19:28). It holds the rim
  investigation of 2026-10-28: the `GUIDED_LAYOUT.md` section "Exact screenshot
  rim investigation", the three `recovered_*` scripts,
  `tests/test_native_integer_callback.py`, `tests/fixtures/native_integer/`,
  `native-rim-verification.json` and the first version of this file. Git works
  now; a previous session reported a "dubious ownership" refusal. If it
  returns, use `git -c safe.directory=* …`.
- **Uncommitted:** the crease-row fix of 2026-11-09 (section 4.1). The user
  asked that it not be committed by the agent.
  - `crease_rows.py` (new): representatives, chains, row finder, row measure.
  - `source_features.py`: the crease check reports rows and fails on
    `rowsMissing`.
  - `open_surface.py`: rows layouts, screening, row fitting.
  - `feature_refine.py`: `row_bands` argument.
  - `feature_quad.py`, `worker.py`: rows enforced for open parts, recorded
    for closed parts.
  - `tests/test_crease_rows.py`, `tests/fixtures/crease_rows/`.
  - `tests/test_server_startup.py`: cleanup retry (see Tests below).
  - `tests/audit_registered_features.py`: records the `crease_rows.py` hash.
  - `GUIDED_LAYOUT.md`: section "Crease rows". `HANDOFF.md`: this update.
  - `engine/guided-quadriflow/development/crease-rows-verification.json`.
- Tests: run `python -X utf8 -m unittest discover -s tests -p "test_*.py"`. It
  runs 197 tests (183 before, plus 14 in `test_crease_rows.py`) and all pass.
  The old error, a Windows file-lock race in `test_server_startup` tearDown
  (`startup.log` still open), is fixed in the test's cleanup: it now retries
  the folder removal for up to ten seconds. `runs/startup test njeowui_` and
  `runs/startup test my8m2y14` are left over from before that fix.
- Packaged engine: build `size-caps-16`, SHA-256 `e94fd633…c196` (details in
  `GUIDED_LAYOUT.md` → "Runtime and reproduction"). It needs MinGW DLLs from
  `C:/msys64/mingw64/bin` or `RETOPO_MINGW_RUNTIME`. Hashes are checked at run
  time. No experimental engine has been promoted, and the crease-row fix did
  not change either engine binary.

## 4. Open issues, in priority order

### 4.1 The island 6 rim was jagged but accepted (fixed for open parts, 2026-11-09)

User-visible symptom: screenshot job `3029972da0174acd9845b6ec0df6e3ea`
(island 6, target 200, 188 quads). The pink crease rim zig-zags.

**Status.** Island 6 at 200 now returns 207 quads with a continuous rim row,
and the crease check rejects the screenshot mesh. Full account, limits and
evidence: `GUIDED_LAYOUT.md` → "Crease rows". In short:

- **Cause found in the layout, not only the check.** QuadriFlow's `-sharp`
  hardens edges above a fixed 60° dihedral. The upper rim crease is 33° to 54°,
  so the engine never treated it as a feature; only its sharper partner a
  quarter face below got rows.
- **Check.** `crease_rows.py` picks one representative crease per band of
  parallel creases (the one bordering the wider sheet) and requires one
  connected, forward-ordered output edge path for each representative chain of
  two faces or more. Distance is measured from the path to the band, without
  the scalar band allowance. Limits reuse existing numbers: 0.25 h at the 95th
  percentile, 0.5 h maximum, 1 h in the last face of an open end, 30° direction.
- **Generator.** The representative chains go to the unmodified engine as
  embedded guide edges; the fit holds each row on its crease and fits its band
  through that row only. Layouts are screened before fitting and seeds are
  tried in order.
- **Witness edge [1308, 1309]:** 0.422 h before, 0.004 h after, 0.011 h native.

What is still open here:

- **Closed parts are not enforced.** `feature_quad.py` has no row fitting, so
  its crease check records rows without failing on them. Island 7's current
  339-quad output would fail one of five chains (source vertices 159 to 380).
  Port the row fitting there, then drop `enforce_rows=False`.
- **Seed search.** Island 6 at 200 is accepted at seed 13 after 44 seconds;
  750 + guide at seed 22 in the second pass after 150. Which seed wins changes
  with small input changes (an earlier soft-guide encoding gave seed 25 and 218
  quads at 200). The hinge lugs, about one face tall, use most of the 5 %
  budgets of the older checks, so few seeds pass. A layout that handles the
  lugs would make this robust.
- **Soft-guide encoding.** Soft crease guides are written a millionth of the
  model extent off the surface so `-embedded-guides` does not harden them. A
  dedicated engine flag for an explicit hard-edge list would be cleaner; it
  needs a new engine build.
- **Self-approaching chains.** The row finder assumes a chain does not pass
  within a face of itself. Island 4's outline at 300 is one 94 h chain with a
  hairpin and never gets a path. Splitting chains at corners of 30° or more
  would address it and would not change island 6 (its chains have none).
- **Island 4 at 300 never returns**, before or after this work: an endless loop
  in the unchanged post-processing of its first size-caps layout
  (`open_surface.construct`, between reading the layout and the fit). Separate
  defect; found while checking other open parts for collateral damage. That
  check found no part that used to generate and now fails (table at the end of
  `GUIDED_LAYOUT.md` → "Crease rows").
- **The parameter chart and combined solve below were not built.** The rim did
  not need them. They remain the route to native-style two-row rims.

What the investigation of 2026-10-28 established (unchanged):

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

**Milestone not taken:** an app-owned parameter chart plus a combined solve that
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

The ordered, connected row this section used to ask for is now in the check
(see Status above).

### 4.2 Island 6 at 150 quads with the native 30° crease angle

With crease rows, 200 → 207, 300 → 331 and 750 + guide → 751 all pass at 30°.
150 is still rejected, now after 377 seconds of search: its best candidate
clears the shape, crease (rows included), contact and guide checks and fails
the **0.5 h surface-deviation** limit, as before. The 45° result has not been
re-run against the row check. This may still be a policy decision (4.5)
rather than a solver change.

### 4.3 Island 6 at 150 with a guide; island 5

Both are unsolved. Island 5 is closed and failed before any of the low-count
work. Islands 2, 7 and 10 pass (291, 339 and 545 quads). Island 2 has no
admitted creases and island 7 takes the closed-part route, so both outputs are
byte-identical to before; island 10 now carries six crease rows.

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
- `tests/test_crease_rows.py` holds the rim regression: the screenshot mesh
  must fail on its rim row and the native mesh must pass. Keep both.
- The matrix compares code hashes before and after its run. Do not edit a root
  `.py` file while it runs, or it reports `codeStable False` and exits 1.
- Expected matrix result: 6 of 7. Island 6 at 150 is the known rejection, so the
  script exits 1 even when nothing regressed. Read the `RESULT` lines.

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
| Crease-row check and generator | `crease_rows.py`, `open_surface.py` (`row_plan`), `GUIDED_LAYOUT.md` → "Crease rows" |
| Crease-row results, job ids, hashes | `engine/guided-quadriflow/development/crease-rows-verification.json` |
| Crease-row matrix and UI evidence (git-ignored) | `tests/registered-features/rimfix-rows-3/`, `tests/registered-features/rimfix-ui-200b/` |
| Rim regression fixtures | `tests/fixtures/crease_rows/README.md` |
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
  repair engine extraction artifacts before the fit. When a part has creases
  that need rows, two passes over 32 seeds of rows layouts come first
  (`ROW_STYLES`), and every layout is screened for row paths before fitting.
- Rows layouts are deterministic: the engine always runs with four threads and
  the fit with one, and eight seeds laid out together give the same files as
  one at a time (checked by output hash).
- The row check accepts a row anywhere across its band. If a result's rim row
  sits on the lower rim crease, the check is working as written; the generator
  aims at the representative (upper) crease.
