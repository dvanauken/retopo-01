# Toilet workflow audit — completed test matrix

The final requirement-by-requirement reconciliation passes all twelve areas
below. `tests/toilet-final-audit/result.json` records 216 evidence-integrity and
coverage assertions, 22 qualified export records representing 21 distinct OBJ
meshes, and exact identity of the 247 runtime/app/asset files used by the latest
real-worker browser test. These are finite, scoped checks; their counts overlap
earlier suites and are not a claim that every possible guide network will solve.

The originally failing bowl, short paired, long paired and perturbed paired
requests now have independently qualified outputs. Unguided targets 150 and 600
produce 152 and 605 quads through native browser Generate and OBJ download in
129.26 and 279.18 seconds. Their actual downloaded bytes pass both independent
geometry and all-mixed-diagonal contact audits. The original white toilet is
unchanged. No geometric acceptance limit was relaxed for these results.

The small fallback dispatch patch was temporarily separated while another
session edited `curved_quad.py`. The user then authorized merging it. It is
integrated again, reproducing the exact tested dispatcher; every other-session
file and shared-file byte matches the recorded ownership snapshot. The earlier
`dispatch-separation/result.json` records that temporary state. The final
`result.json` is authoritative. The patch is retained in `patches/` for review.

## Requirements and final evidence

| Area | Required coverage | Evidence and scope |
| --- | --- | --- |
| Original source | Plain white model, source identity, similarity transform, every vertex, local conformity, topology | Seven original-source checks pass. The source OBJ remains `c2daa898…7053`; its four recorded source contacts are separate from generated-mesh qualification. |
| Guide geometry | Freehand, Polyline, Spline, Circle; open/closed; 5 CSS-pixel green snap; fitting/projection limits | Guide additions and the current 130-check toilet editor suite cover construction, the 5 px boundary at DPR 1/2, Circle and surface projection. Pure editor modules remain byte-identical to the tested versions. This is the declared guide-specific adaptation, not full thirteen-primitive Base 2D conformance. |
| Editing | Object/direct selection, endpoints, marquee, groups, point edits, rollback, delete/reverse, history | 130 current toilet editing checks plus 18 occlusion/marquee/repeated-use checks pass. The large editor suite labels its historical right-pane fixture as unqualified. Separate genuine generated-result tests cover editing and undo over an accepted toilet mesh. |
| Persistence | Native download/import, exact authored IDs/values, source binding, reload, legacy and invalid inputs | Native roundtrip/reload in the editor suite and 23 delayed-import/queued-error checks pass. Source changes, newer edits, stale file reads, legacy closure and atomic rejection are covered. |
| Solver | No/single/multiple guides, captured failures, densities, repeat/equivalent representations | Qualified cases cover unguided 150/600/1200/1799/1800, lid/Circle/bowl, short and long pairs, guide reversal/order, exact densification, cyclic start and small perturbations. Each retained output is linked to its exact producer and two independent audits. |
| Geometry acceptance | Exported quads, topology, shape, density, guide paths, bidirectional surface accuracy and contacts | Twenty-one distinct retained meshes pass paired independent geometry/contact audits. Connected guide-edge paths qualify, rather than just displayed guide overlays. Twenty-five owned-code controls and the numerical-scope proof cover the final fallback. Older rejected outputs remain rejected. |
| Job lifecycle | Admission, queue, running cancellation, repeated cancel, timeout, crash/restart, cleanup | Real HTTP/worker tests cover the races. Windows forced service/worker exits, file locks and timeout cleanup pass. Cancellation during actual second-layout fitting passes twelve checks. Service/process ownership modules still match their tested hashes. |
| API contract | Type/size/count boundaries, status consistency, accepted-only downloads | The 76-check HTTP suite passes with a named Circle positive control. The current server is byte-identical. Unfinished/cancelled/failed output files remain unavailable. |
| UI lifecycle | Pending acknowledgement, source/edit/density changes, stale results, prior accepted mesh, persistent errors | 52 cancellation-transport, 30 asynchronous UI, seven lost-submission, fourteen early-cancel and fifteen genuine generated-result checks pass in their recorded scopes. The complete request/editor event block is unchanged; subsequent rendering/error-dialog changes have current tests. |
| Workspace | Ribbon/nav/center/properties/dock, light/dark, compact widths, resizing, focus and navigation | A fresh 23-check shell run passes on current UI bytes in an isolated service. Eighteen current toilet rendering checks cover native theme/view/orbit controls and panel/ribbon size changes. |
| Runtime | Repeated use, responsiveness, bounded memory, process cleanup, console errors | Forty source switches retain one browser document and stay within the bounded heap check. Real sequential generation and cancellation tests pass; all 33 observed coarse-browser descendants exit. On-demand rendering stops idle draw calls. These are scoped observations, not universal leak guarantees. |
| Evidence | Hashes, actual input/output, reproducibility, failure retention, ownership | The final auditor verifies report assertions and actual OBJ hashes, links both independent audits for every qualified export, reconciles component changes, and confirms all 247 tested runtime files and 22 protected shared files. Historical negative/incomplete reports remain unchanged. |

## Practical limits

- The slow paired target-1799 browser solve takes 572.79 seconds against the
  600-second timeout. The tested case succeeds, but runtime is still too long
  for interactive iteration and can vary with machine load.
- The other session's optional guided-layout/ellipsoid work and one-guide
  35-degree policy are outside this qualification. The owned committed solver
  retains the 30-degree guide limit. Shared unguided behavior has its own exact
  runtime proof; older guided results are not relabeled as tests of that policy.
- Arbitrary thin sheets, new guide networks, all possible densities and other
  operating systems are not universally certified. Unsupported or unqualified
  results must still reject without replacing an accepted result.
- The two historical incomplete generated-UI observations remain incomplete;
  later successful tests cover their required workflows without inventing a
  cause for the unexplained historical cancellation.

## Reproduce the reconciliation

Run `python -X utf8 tests/reconcile_toilet_audit.py` in the recorded shared
workspace. It checks retained reports and meshes without rerunning expensive
solves. The exact shared optional files are required for its runtime-identity
assertions; a clean checkout of the owned baseline has a different declared
scope. `tests/verify_final_workspace_scope.py` uses the frozen service prepared
by `tests/prepare_isolated_boundary_service.py`; it never changes the live user
service pointer. Individual producer commands and snapshots remain with their
reports. The full historical index is `tests/toilet-exhaustive-audit/result.json`;
its earlier “open” summaries are superseded by this finite final reconciliation.

## Audit history (historical checkpoints, not current status)

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

A separate worker-only crash test reproduced an orphan Blender process while the
HTTP service remained alive. `tests/verify_toilet_worker_crash.py` suspends the
actual observed Blender child, kills only its actual toilet worker, and checks
structured failure, blocked publication, descendant exit and recovery admission.
The before-fix report fails cleanup. Calling the existing lifetime-job helper
inside the worker fixes this through a nested Windows job. All 11 crash checks
pass, followed by 6 service-crash, 7 timeout, 13 real file-lock, 53 unit and 76 API
checks (166 total). The fresh API Circle export matches the independently
qualified geometry. Reports are under each family's `nested-worker-job/` folder.
These reports retain the worker hash from before a concurrent, opt-in guided-
layout dispatch edit; they do not certify that separate solver route.
An additional 11-check worker-crash rerun passes on the current shared worker.
`worker-lifetime-shared-scope.json` records an AST comparison: the only numerical
route difference is the separately guarded, false-by-default dispatch, and the
toilet metadata leaves it disabled. This reconciles component scope without
claiming another full 166-check run or qualification of the new solver.

Path-fit diagnostics compare all 257 acceptance samples with the actual selected
edges and source normals. Most failing tangent samples have nearby source normals
that agree; a wrong-surface-layer explanation is not supported at those samples.
The authored guides measured against their own polyline edges meet the angle
limit, so the failures are not an inherently impossible corner metric. The
per-sample evidence and orthographic plots are in `tests/toilet-path-fit-diagnostics/`.

An earlier isolated experiment fitted 401 arc-spaced guide samples to connected output
edges, while validation remains the unchanged 257-sample metric. Bowl-only passes
the solver gates on retained genuine layout seed 2. The shorter combined input
passes both guide limits after two refinement passes, but fails full surface bounds:
source-to-output error exceeds 0.04156/0.04992 for the two quad diagonals against
the 0.04004 tolerance. The longer combined input still fails tangent alignment.
All candidates and the exact executed residual are retained under
`tests/toilet-sampled-paths/captured-seed2-401/`. None changes production fitting.
Its bowl OBJ passes the separate dense/reference/LP/BVH guide and surface audit
and all mixed-diagonal contacts under the `sampled-path-401` audit labels.

Adding source triangle-centroid support separately for both output diagonals
fails all 15 refinement attempts across the three captured inputs. Every attempt
has detected contacts; a passing sparse surface screen is not full acceptance.
The first raw-layout support assignments include 204/274 opposing-normal pairs
for diagonals 02/13, including 19/18 on a recurring group of overlapping faces.
These counts motivate a correspondence experiment; they do not prove the cause
or excuse the contacts. Exact data are in `tests/toilet-both-diagonal-support/`
and `tests/toilet-support-normal-diagnostics/`.
Omitting opposing-normal support pairs also fails all 15 attempts, with contacts
in every candidate. The final longer case still fails guide alignment. Thus this
filter alone does not resolve the correspondence or contact problem. The exact
residual and candidates are under `tests/toilet-oriented-support/`; no surface
threshold, contact rule or production solver was changed.
The normal-filter script initially collided with an older diagnostic filename.
Final review restored that original byte-for-byte. The executed new script is
retained beside its raw result as `executed-probe.py`, with the correction recorded
in `script-provenance.json`; the reusable script is now
`tests/probe_toilet_sampled_oriented_support.py`. This filename correction does
not change measured candidates or reinterpret their failures.

A nine-weight blend diagnostic tests both captured combined inputs between the
qualified bowl-only candidate and their fitted candidates. All 18 trials remain
unqualified. In the short case, following the lid guide and preserving the
surface are competing constraints. An initial harness-only triangle-list type
error is retained separately from the corrected completed run under
`tests/toilet-feasible-blend/`; it is not a geometry rejection.

Local witness repair qualifies the shorter combined case without changing any
limit. The initial worst observed surface error is 0.04992 versus tolerance
0.04004. Four accepted half steps reduce it to 0.03947 while preserving shape,
contacts and both guides; each rejected full step exceeds lid-guide distance.
Final complete surface bounds pass, as do independent audits of the actual OBJ.
`tests/toilet-witness-repair/short-seed2-local/repair-tradeoff.png` plots the
measured tradeoff. The p95 lid distance ends at 0.01581 versus limit 0.01602;
this narrow margin requires input-variation testing before a robustness claim.

`tests/probe_toilet_fresh_witness_pipeline.py --label <new-label>` reproduces the
short case from the original source and authored guides. It generates a fresh
Blender layout, runs sampled fitting, selects an eligible surface-failing
candidate from that run, repairs it and independently audits its export. The
`fresh-short-seed2` run completes in about 316 seconds including the independent
audits and reproduces the exact accepted experimental OBJ bytes. No previous
candidate is used as input. This remains separate from the production worker.

Before joint correction, the longer captured case remained unqualified. Path reselection produced the
same connected chains and tangent error. Its full surface check, previously
skipped after guide rejection, also fails: diagonal 02 source-to-output reaches
0.04031; diagonal 13 reaches 0.04570 forward and 0.04053 backward, versus the same
0.04004 limit. The exact witnesses are in `tests/toilet-long-surface-diagnostics/`.
Independent direction fits to fixed edge-owner groups reduce the diagnostic
tangent p95, but ignore shared-vertex and surface constraints and do not qualify
geometry. See `tests/toilet-path-reselection/`.

Read-only review of the separate guided-layout deployment confirms the bytes of
all 15 shared files and preserves its failed five-attempt toilet bowl regression.
Its ellipsoid controls do not qualify the toilet. The existing shared integration
is unchanged; evidence is retained in `tests/toilet-guided-route-review/`.

Testing arbitrary continuous guide coordinates cannot enumerate every possible
input. Coverage must therefore include documented finite control/state cases,
boundary partitions, deterministic generated families, geometric invariants and
independent output checks. This does not authorize claiming universal numerical
correctness, weakening acceptance limits, or omitting the reported failing input.
