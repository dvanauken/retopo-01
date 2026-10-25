# Exhaustive toilet workflow audit

The active request is to keep testing until the toilet workflow has been tested
exhaustively. Prior check counts are evidence, not completion criteria. An
unresolved case, unchecked requirement or weak test keeps this audit open.

## Current evidence and gaps

| Area | Required coverage | Current evidence / work remaining |
| --- | --- | --- |
| Original source | Original white GLB identity, similarity transform, all vertices, conformity repair, topology, presentation | All seven original-source checks pass again, including a fresh Draco decode and every vertex. Detected source contacts remain recorded separately from output qualification. |
| Guide geometry | Freehand, Polyline, Spline, Circle; open/closed, first-point snap, fitting and projection limits | Existing guide units/browser suites; extend toilet-specific geometry variation, reversal, cyclic reindexing, ordering, perturbation and limit boundaries. |
| Editing | Object/direct selection, endpoints, marquee, Shift groups, point edits, invalid multi-edit rollback, delete/reverse, history | 130 toilet editor checks pass at DPR 1/2 in both panes: point preview/commit/rollback, zoom, groups, history, closure, Circle and IO. Right pane uses a disclosed unqualified rendering fixture. Marquee, occlusion and invalid multi-edit coverage remain open. |
| Persistence | Native IO, exact authored values/IDs, source binding, reload, legacy input, malformed/budget-exceeding input | Exact two-type toilet roundtrip/reload passes, as do atomic foreign-source, duplicate-ID, unknown-schema, malformed-JSON and oversized-file rejections. Legacy and asynchronous import/source-change boundaries remain to audit. |
| Solver | No guides, single/multiple guides, all primitive families, supported densities, exact captured failures, repeated input and equivalent representations | `toilet-stress/result.json` has a required failure for the longer combined guide. Expand equivalence/perturbation tests; do not convert this failure to a pass merely because rejection is safe. |
| Geometry acceptance | Actual exported quads; all relevant topology, shape, target, guide, surface and intersection checks | Dense tests, independent contact witnesses, adaptive whole-surface bounds and adjacent-contact screening expose failures in all five historical meshes. Fresh generations and numerical/representation limits remain under audit. |
| Job lifecycle | Queue, admission limits, queued/running cancellation, repeat cancellation, late results, worker errors, timeout, recovery, no orphan processes | Actual queue/admission/cancellation/publication checks pass. Startup cancellation races pass. Timeout and sustained process/memory behavior remain open. |
| API contract | Valid boundaries, malformed/type/size limits, status/resource consistency, accepted-only result downloads | 76 real HTTP checks pass after fixing premature publication. New strict solver outcomes must be reconciled with successful-result paths. |
| UI lifecycle | Cancel before response, switching source while pending, edits/density changes while solving, stale completion, previous accepted result, error persistence | 17 deterministic genuine-response race checks pass. Reset during pending acknowledgement and additional stale-result/import cases remain open. |
| Workspace | Ribbon/nav/main/properties/dock, both themes, narrow layouts, split/overlay, orbit/zoom/fit, panel resizing, keyboard ownership | Existing shell suite passed. Cover interactions with the toilet and in-flight work, including repeated use. |
| Runtime | Sustained drawing/editing/generation, memory/process cleanup, responsiveness, console errors | Establish repeatable measurements rather than treating one successful interaction as a stability test. |
| Evidence | Current implementation hashes, actual input/output, actionable failure records, reproducible commands, live app verification | Existing suites retain evidence. Reconcile obsolete claims and produce a final requirement-by-requirement audit before completion. |

## Audit history

- Previous goal turn: **progress**. Committed `38dc14c` added 181 checks and found
  a remaining required solver regression; intersecting candidates are rejected.
- This continuation starts from the clean committed worktree. Completion is
  unproven. The longer combined guide still fails; density, API lifecycle,
  geometric equivalence and stronger surface/intersection coverage are open.
- Added real HTTP boundary and queue/publication coverage: 76 checks pass after
  blocking result downloads from running, cancelled and failed jobs. Unaccepted
  files were deliberately planted only in the isolated test server's job
  directories to reproduce the publication race.
- Added delayed genuine-response browser tests: 17 checks pass after fixing
  source switching before acknowledgement, external cancellation feedback and
  immutable attempt parameters. Three deterministic startup unit tests also pass
  after preserving cancellation across a worker-start exception.
- Dense surface testing covers 120,000 source points and all output vertices,
  centroids, edge midpoints and deterministic interior samples. All five unique
  previously accepted exports exceed the unchanged distance limit under ear
  triangulation; two fail the fan interpretation used by the renderer. Source and
  output triangulation conventions also differ: the renderer/fitter use a fan,
  while the prior validator uses projected ear clipping. Both interpretations
  have been tested; adaptive whole-triangle bounds now cover both quad diagonals.
- Shared-vertex face diagnostics found two interior overlaps in each of the
  shorter two-guide, bowl-only and unguided exports. Independent HiGHS linear
  programs confirm all six positive contacts. The strengthened production screen
  includes these pairs and permits only actual shared boundaries. Its 17 control
  tests include 240 generated cases compared to independent linear programs,
  each at three coordinate scales. Absence of a report remains subject to the
  stated floating-point tolerance and triangulation.
- Denser-support fitting experiments increased intersections; the oriented
  support experiment produced a self-crossing projected quad. Neither experiment
  was integrated or counted as a successful solve. The core fitting/acceptance
  work and the remaining matrix items above are still open.
- The first fresh six-case matrix under stricter acceptance generated no accepted
  toilet mesh. It also exposed a Windows progress-file sharing violation and
  an intermediate projected-quad exception that stopped remaining passes.
  Progress publication now retries and remains advisory; invalid triangulation
  now rejects that candidate while preserving subsequent refinement attempts.
  The affected shorter two-guide and bowl-only cases are rerun separately.
  Both reruns finish all attempts and reject for actual face intersections;
  neither fails from the progress-file race or projected-triangulation exception.
- All 33 numerical/lifecycle unit tests now pass, including timeout cleanup and
  cancellation snapshots under the worker lock. Three recovery tests failed
  before the fixes; the initial snapshot harness lacked a content-type header,
  which was corrected before reproducing the real unlocked snapshot against
  committed revision `38dc14c`.
- The expanded editor suite passes 130 checks. Its initial reload harness wrongly
  assumed the selected source auto-restored; the app intentionally starts on
  Hexagon. The corrected test reselects Toilet and proves exact persisted guide
  restoration. No application change was made to turn that harness error green.
- Both idle app servers (8741 and 8742) were restarted on the current code. Each
  has exactly one listener, cancels a real submitted toilet job, and returns 409
  for all three unaccepted result resources. This is lifecycle verification,
  not a successful geometry solve.

Testing arbitrary continuous guide coordinates cannot enumerate every possible
input. Coverage must therefore include documented finite control/state cases,
boundary partitions, deterministic generated families, geometric invariants and
independent output checks. This does not authorize claiming universal numerical
correctness, weakening acceptance limits, or omitting the reported failing input.
