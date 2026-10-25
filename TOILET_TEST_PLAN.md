# Exhaustive toilet workflow audit

The active request is to keep testing until the toilet workflow has been tested
exhaustively. Prior check counts are evidence, not completion criteria. An
unresolved case, unchecked requirement or weak test keeps this audit open.

The latest continuation adds ownership before the initial submission: the browser
creates a request identity, and the service deduplicates delivery and remembers
early cancellation. Cancel/Reset can now stop work even if the first admission
response is lost or delivery has not reached the service. Real forced-exit tests
also found orphan workers; a Windows process job now owns the service and future
worker/Blender descendants. Exact negative and corrected reports are retained.

The genuine generated-result browser run then exposed a progress-file sharing
violation, which broke polling and cancelled its second Circle solve. Twelve
earlier workflow checks passed, including a fresh accepted Circle/export and
preservation of that result after a real rejected replacement. That interrupted
run is not a complete pass. Progress reads now tolerate transient I/O failure;
diagnostic writes cannot prevent cancellation. All 53 unit checks and 13 actual
Windows file-lock/HTTP/process checks pass. The final integrated rerun passes
76 API, 52 cancellation, 30 asynchronous UI, 7 lost-submission, 14 early-cancel
and 8 restart-UI checks. All 15 genuine generated-result browser checks also pass
on the final app/server code, with two fresh Circle solves. Its OBJ exactly
matches the independently qualified Circle. The earlier unexplained client
cancellation is retained separately; a later pass does not establish its cause.

Production fitting, source assets, recovered engine and acceptance thresholds
remain unchanged. An isolated tangent-plus-sliding-pin experiment on seed 2 now
passes all production gates for the bowl-only case after four passes (guide p95
distance 0.01033, tangent mismatch 29.70 degrees). Independent export validation
and all mixed-diagonal checks also pass. It is not integrated. Both captured
combined-guide inputs still fail guide alignment in all ten passes, and some
shorter-case passes also fail surface checks. Integration regression coverage
and resolution of these failures remain required. Production bowl,
combined-guide and coarse-density failures therefore remain unresolved.

A second isolated experiment raises the tangent weight from 8 to 12. Its bowl
candidate also passes independent export and all mixed-diagonal checks, with
p95 distance 0.00901 and tangent mismatch 27.77 degrees. Both combined-guide
inputs still fail in all ten passes. Increasing that weight alone therefore
does not resolve the captured networks; neither experiment is in production.

## Current evidence and gaps

| Area | Required coverage | Current evidence / work remaining |
| --- | --- | --- |
| Original source | Original white GLB identity, similarity transform, all vertices, conformity repair, topology, presentation | All seven original-source checks pass again, including a fresh Draco decode and every vertex. Detected source contacts remain recorded separately from output qualification. |
| Guide geometry | Freehand, Polyline, Spline, Circle; open/closed, first-point snap, fitting and projection limits | Existing guide units/browser suites; extend toilet-specific geometry variation, reversal, cyclic reindexing, ordering, perturbation and limit boundaries. |
| Editing | Object/direct selection, endpoints, marquee, Shift groups, point edits, invalid multi-edit rollback, delete/reverse, history | 130 toilet editor checks pass at DPR 1/2 in both panes; that right-pane fixture is historical and unqualified. Another 18 checks cover actual underside occlusion, both marquee directions, partial containment, invalid group rollback, hidden overlay, keyboard ownership and repeated navigation. Fifteen genuine generated-result workflow checks also pass; see the hash-scoped reports. |
| Persistence | Native IO, exact authored values/IDs, source binding, reload, legacy input, malformed/budget-exceeding input | Native roundtrip/reload and atomic invalid imports pass. Fifteen additional delayed-file checks pass for source changes, edits during loading, out-of-order completion, stale invalid JSON, unfinished construction and legacy open/closed curves. |
| Solver | No guides, single/multiple guides, all primitive families, supported densities, exact captured failures, repeated input and equivalent representations | `toilet-stress/result.json` has a required failure for the longer combined guide. Expand equivalence/perturbation tests; do not convert this failure to a pass merely because rejection is safe. |
| Geometry acceptance | Actual exported quads; all relevant topology, shape, target, guide, surface and intersection checks | All five historical meshes remain unqualified. With the warpage correction, fresh unguided, lid-guide and Circle exports pass both production bounds and independent dense/LP/BVH/reference audits. Complex inputs and representation/density families remain under audit. |
| Job lifecycle | Queue, admission limits, queued/running cancellation, repeat cancellation, late results, worker errors, timeout, recovery, no orphan processes | Queue/admission/cancellation/publication and worker-start races pass. Seven actual worker/Blender timeout-cleanup checks pass. The deterministic initial-response snapshot race is fixed. Broader sustained process behavior remains open. |
| API contract | Valid boundaries, malformed/type/size limits, status/resource consistency, accepted-only result downloads | 76 current HTTP checks pass with a named Circle positive control. The original bowl recovery run still records a generation failure; it was not replaced by that control. |
| UI lifecycle | Cancel before response, switching source while pending, edits/density changes while solving, stale completion, previous accepted result, error persistence | Reset before acknowledgement reproduced an orphan worker; Reset now confirms cancellation of browser request identities before reloading, including submissions whose acknowledgement has not arrived. Seventeen checks pass for Reset and earlier races, plus seven for two pending acknowledgements. Fifteen actual successful-result/prior-result checks pass. Another 52 transport checks and 30 current asynchronous checks cover retry ownership and Reset. |
| Workspace | Ribbon/nav/main/properties/dock, both themes, narrow layouts, split/overlay, orbit/zoom/fit, panel resizing, keyboard ownership | Existing shell suite passed. Cover interactions with the toilet and in-flight work, including repeated use. |
| Runtime | Sustained drawing/editing/generation, memory/process cleanup, responsiveness, console errors | Forty source switches plus native camera actions retain exact guides and pass a bounded JavaScript heap/document-count check without console errors. This is not a GPU-memory or universal leak certificate. Multi-generation/process recovery remains to reconcile. |
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
- This continuation found and fixed Reset discarding a pending acknowledgement
  while its worker continued. The pre-fix failed report and corrected one- and
  two-pending-request reports are retained in `tests/toilet-async-ui/`.
- Uniform target spacing, lower pin weights, dense surface supports and
  preconditioned layouts were explored in isolated fitting experiments. They
  did not solve the required guide cases and were not integrated. Only the quad
  warpage residual was integrated. Its analytic controls pass, and all 36
  numerical/lifecycle tests pass with this change.
- Three fresh accepted meshes now pass independent exported-OBJ audits: 1,923
  unguided quads and 1,782 quads each for the lid-guide and Circle inputs. Every
  audit checks both triangulations with 120,000 source samples, independently
  solves shared-vertex triangle-interior contact feasibility problems, checks
  separate Blender BVH pairs, and verifies the unchanged reference/topology/
  quality limits and actual guide-edge paths. The tolerances and finite scopes
  are recorded; this does not qualify arbitrary toilet guides.
- The selection test's first run did not actually orbit to the underside because
  Space correctly belonged to a focused toolbar button. That harness error is
  retained. The corrected run focuses the canvas and verifies actual underside
  hit coordinates before testing occlusion. No app code changed for this result.
- Fifteen genuine successful-result browser checks pass: edits during delayed
  result delivery remain intact, native OBJ bytes match the accepted worker,
  right-pane direct editing projects to the original source, Undo is exact,
  a rejected replacement preserves the prior accepted mesh, and a late successful
  response cannot overwrite another source. No preview fixture is used here.
- Seven actual process-cleanup checks pass after a controlled timeout event is
  injected only once the real toilet worker has launched Blender. Both processes
  exit, the failure/exit record is retained and no mesh is published. This tests
  the production timeout branch with real processes, not ten wall-clock minutes.
- The fresh complex-input matrix finishes all attempts: the shorter two-guide
  and bowl-only cases still fail contact checks, while the closest longer-guide
  attempt fails quad quality. All three remain unsolved. Their seventeen safe
  failure checks pass; those checks are not counted as solved geometry.
- The consolidated current browser request/reset suite passes all 29 checks;
  the guide-domain suite passes all 21 tests. Circle repetition, reversal,
  cyclic starting-point change and insertion of collinear intermediate samples
  have each produced accepted fresh results. The remaining variation/density
  cases and independent supplemental contact/export audits are still running.
- The stronger Jacobian-residual experiment improves shape but fails guide fit
  or contacts on every required complex input. It is retained under
  `tests/toilet-warpage-probe/jacobian-120/` and is not in production code.
- The delayed POST-acknowledgement test reproduced a dictionary-size exception
  while the worker inserted a field. The response snapshot and timeout error
  update now use the job lock. All 37 unit checks pass after this fix; the current
  29-case browser race suite and 76-check API suite also pass with an explicitly
  labeled Circle positive control. The default bowl recovery test still fails
  generation and is retained separately; the control does not replace it.
- Local process startup stalled during the reversed-lid run, which reached the
  actual 600-second worker timeout. Its raw log stopped at layout construction.
  After execution recovered and that job was definitively terminal, a new
  reversed-lid job completed successfully. Neither an observation timeout nor
  the earlier lack of tool output was treated as a terminal worker result.
- Unguided targets 150 and 600 fail geometry acceptance; 1,200 and 1,799 succeed
  and pass independent surface/path/contact audits under both uniform diagonals.
- The alternate-diagonal audit found two independently confirmed shared-face
  overlaps in the slightly perturbed Circle export. Its earlier fan-only audit
  passes but does not qualify it under the new requirement. Contact acceptance
  now enumerates all triangle pairings from both diagonals, including mixed
  choices on neighboring quads. An analytic control proves that both uniform
  choices can pass while a mixed choice intersects. All 41 numerical/lifecycle
  controls pass. Fresh Circle, reversed-lid and perturbed-Circle generations
  under the corrected gate all pass independent exported-surface/path checks
  and the all-mixed-diagonal audit. The perturbed input now reaches a different
  valid candidate after its earlier overlapping candidate is rejected.

The current transport regression reproduces the original bug with real toilet
workers: interrupting Cancel left the worker running while the UI said cancelled;
retrying Reset discarded the workspace without stopping it. The negative report
is retained in `tests/toilet-cancel-transport/before-fix/`. The final seven-scenario
suite covers failed Cancel/Reset, lost cancellation responses, stale admission
acknowledgements, Reset during cancellation, source changes, and polling plus
cancellation failure. It checks actual server states and observed worker exits.
The final 30-check async suite also proves cancelled timers stop updating.

Additional seed diagnostics show raw layouts 2/3 have no detected mixed-diagonal
contacts before fitting. Bowl target assignment moves vertices by p95 0.231/0.223
units despite nearest-guide distances of p95 0.053 (target edge length 0.080).
This motivates investigating target spacing and curve-constrained movement;
it does not prove a replacement fitting algorithm. Five sliding-pin passes on
seed 2 remain unqualified. Exact layouts, candidates, executed residual and
original curve hashes are retained, and production still uses seeds 0/1.

Initial-acknowledgement loss and service restart are now exercised separately from
cancellation-response loss. The lost-admission test aborts a genuine response
after a real worker exists; the early-delivery tests hold the POST before any
bytes reach the service. All 7 lost-response, 14 early-cancel/Reset, 8 real browser
restart and 6 native crash checks pass at their recorded implementation hashes.
Windows crash cleanup is tested with an actual Blender descendant. Request
deduplication/tombstones are in-memory for one service lifetime; non-Windows hard
exit cleanup is not claimed.

The first lost-response observer incorrectly counted the server's own console
host as an orphan worker. The correction and original report remain under
`tests/toilet-submission-transport/`; the initial bug independently failed real
server-state assertions and was not an observer-only failure. Preliminary
parallel transport/async/API/crash runs also timed out during observed CPU
contention. Sequential completed reruns remain separate; observation failure is
not a failed geometry measurement. The user confirmed that an earlier output
stall occurred while Windows was asleep or locked.

The subsequent real progress sharing violation is retained in
`tests/toilet-generated-ui/request-ownership/server.log`. Four targeted controls
then reproduced progress-read failure, cancellation diagnostic writes preventing
running/queued cleanup, and a 4,001-digit integer coordinate raising OverflowError.
The fixed 53-test suite passes. Thirteen real Windows exclusive-file-handle checks
also pass against the HTTP service and actual toilet worker/Blender tree; no
mocked success or cached geometry is used.

Testing arbitrary continuous guide coordinates cannot enumerate every possible
input. Coverage must therefore include documented finite control/state cases,
boundary partitions, deterministic generated families, geometric invariants and
independent output checks. This does not authorize claiming universal numerical
correctness, weakening acceptance limits, or omitting the reported failing input.
