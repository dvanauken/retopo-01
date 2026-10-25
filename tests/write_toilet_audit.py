"""Index retained evidence without converting safe failures into solved meshes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests/toilet-exhaustive-audit'; OUT.mkdir(exist_ok=True)
reports={
    'original-source':'tests/toilet-source/result.json',
    'cancel-transport-before-fix':'tests/toilet-cancel-transport/before-fix/result.json',
    'cancel-transport-initial-fix':'tests/toilet-cancel-transport/fixed/result.json',
    'cancel-transport-expanded':'tests/toilet-cancel-transport/extended/result.json',
    'cancel-feedback-regression':'tests/toilet-cancel-transport/final-feedback/result.json',
    'cancel-transport-final':'tests/toilet-cancel-transport/final/result.json',
    'cancel-timer-before-fix':'tests/toilet-async-ui/cancellation-timer-before-fix/result.json',
    'async-cancellation-final':'tests/toilet-async-ui/cancellation-final/result.json',
    'successful-ui-after-ownership-fix':'tests/toilet-generated-ui/cancellation-ownership/result.json',
    'fresh-extra-layout-seeds':'tests/toilet-layout-seeds/fresh-seeds-2-3/result.json',
    'sliding-pin-experiment':'tests/toilet-sliding-pins/bowl-seed-2/result.json',
    'api-boundaries-and-lifecycle':'tests/toilet-api/current/result.json',
    'browser-async-lifecycle':'tests/toilet-async-ui/request-context-complete/result.json',
    'toilet-editor':'tests/toilet-editing/current/result.json',
    'numeric-and-worker-units':'tests/toilet-unit-gates/current/result.json',
    'warpage-and-worker-units':'tests/toilet-unit-gates/warpage/result.json',
    'reset-regression-before-fix':'tests/toilet-async-ui/reset-before-fix/result.json',
    'reset-and-async-fixed':'tests/toilet-async-ui/reset-fixed/result.json',
    'consolidated-async-races':'tests/toilet-async-ui/warpage-final/result.json',
    'admission-race-before-fix':'tests/toilet-unit-gates/admission-before-fix/result.json',
    'admission-race-fixed':'tests/toilet-unit-gates/admission-fixed/result.json',
    'all-diagonal-and-lifecycle-units':'tests/toilet-unit-gates/all-diagonal-contacts/result.json',
    'api-current-bowl-regression':'tests/toilet-api/warpage-before-admission/result.json',
    'api-fixed-circle-control':'tests/toilet-api/admission-fixed-circle-control/result.json',
    'browser-after-admission-fix':'tests/toilet-async-ui/admission-fixed/result.json',
    'reset-two-pending':'tests/toilet-async-ui/reset-multiple/result.json',
    'delayed-imports':'tests/toilet-import-races/result.json',
    'occlusion-marquee-repeat-use':'tests/toilet-selection-stability/current/result.json',
    'fresh-warpage-guided':'tests/toilet-strict-generation/warpage-guided/result.json',
    'fresh-warpage-complex':'tests/toilet-strict-generation/warpage-complex/result.json',
    'independent-fresh-unguided':'tests/toilet-fresh-geometry/unguided-warpage/result.json',
    'independent-fresh-guided':'tests/toilet-fresh-geometry/guided-warpage/result.json',
    'fresh-generated-ui':'tests/toilet-generated-ui/current/result.json',
    'actual-worker-timeout-cleanup':'tests/toilet-process-timeout/result.json',
    'guide-representations-and-density':'tests/toilet-variants/current/result.json',
    'independent-representation-exports':'tests/toilet-fresh-geometry/representation-variants/result.json',
    'alternate-diagonal-contacts':'tests/toilet-diagonal-contacts/qualified-base/result.json',
    'remaining-independent-variants':'tests/toilet-fresh-geometry/remaining-variants/result.json',
    'alternate-diagonal-variant-failures':'tests/toilet-diagonal-contacts/variants/result.json',
    'mixed-diagonal-retained-export-audit':'tests/toilet-all-diagonal-audit/before-new-gate/result.json',
    'recovered-lid-reversal':'tests/toilet-variants/recovered-lid/result.json',
    'fresh-all-diagonal-generations':'tests/toilet-variants/all-diagonal/result.json',
    'independent-all-diagonal-generations':'tests/toilet-fresh-geometry/all-diagonal-generations/result.json',
    'mixed-diagonal-fresh-export-audit':'tests/toilet-all-diagonal-audit/fresh-new-gate/result.json',
    'dense-ear-surface':'tests/toilet-dense-surface/result.json',
    'dense-fan-surface':'tests/toilet-dense-surface/fan-result.json',
    'adjacent-contacts':'tests/toilet-adjacent-contacts/result.json',
    'independent-contact-witnesses':'tests/toilet-adjacent-contacts/lp-witnesses.json',
    'whole-surface-and-contact-audit':'tests/toilet-acceptance-audit/result.json',
    'first-strict-six-case-matrix':'tests/toilet-strict-generation/result.json',
    'fresh-strict-generation':'tests/toilet-strict-generation/current/result.json',
    'live-server-publication':'tests/toilet-exhaustive-audit/live-server.json',
}
for family, labels in {
    'submission-transport':['before-fix','request-id-fixed','ownership-fixed','ownership-final','ownership-io'],
    'early-submission':['request-identity','ownership-final','ownership-io'],
    'server-restart':['before-fix','recovered-before-fix','ownership-fixed','nested-worker-job'],
    'worker-crash':['before-fix','nested-worker-job','shared-dispatch-worker-job'],
    'process-timeout':['nested-worker-job'],
    'restart-ui':['ownership-final','ownership-io'],
    'cancel-transport':['submission-identity','ownership-final','ownership-io'],
    'async-ui':['submission-identity','ownership-final','ownership-io'],
    'api':['submission-identity','ownership-final','ownership-io','nested-worker-job'],
    'unit-gates':['submission-identity','ownership-final','io-fault-before-fix','io-fault-fixed','nested-worker-job'],
    'generated-ui':['request-ownership','ownership-io','ownership-io-diagnostics'],
    'file-locks':['io-fault-fixed','nested-worker-job'],
    'tangent-pins':['bowl-seed-2-weight-8','combined-seed-2-weight-8','captured-seed-2-weight-12'],
    'fresh-geometry':['tangent-bowl-seed2','sampled-path-401','witness-short-seed2','fresh-short-seed2-export','integrated-fallback','long-constraint-memory','fresh-long-direct-tail80-export','paired-order-and-direction','paired-sampling-and-density','joint-integrated'],
    'all-diagonal-audit':['tangent-bowl-seed2','sampled-path-401','witness-short-seed2','fresh-short-seed2-export','integrated-fallback','long-constraint-memory','fresh-long-direct-tail80-export','paired-order-and-direction','paired-sampling-and-density','joint-integrated'],
    'sampled-paths':['captured-seed2-401','fresh-short-seed2-fit','fresh-long-direct-memory-fit','fresh-long-direct-tail80-fit'],
    'both-diagonal-support':['captured-seed2-401'],
    'oriented-support':['captured-seed2-401'],
    'feasible-blend':['captured-seed2','captured-seed2-arrays'],
    'witness-repair':['short-seed2-local','fresh-short-seed2-repair'],
    'fresh-witness':['fresh-short-seed2'],
    'joint-repair':['long-seed2-protected'],
    'tangent-tail':['long-protected-tail40'],
    'constraint-memory':['long-protected-memory8','fresh-long-direct-memory-repair','fresh-long-direct-tail80-repair'],
    'fresh-memory':['fresh-long-direct-memory','fresh-long-direct-tail80'],
    'paired-variants':['order-and-direction','sampling-and-density','joint-integrated'],
    'unguided-fallback':['coarse-seed2'],
    'sampled-worker':['integrated-fallback','joint-integrated'],
    'fallback-browser':['integrated-fallback','joint-integrated'],
    'fallback-cancel':['integrated-fallback','worker-owned','joint-integrated'],
}.items():
    for label in labels:
        reports[family+'-'+label]='tests/toilet-'+family+'/'+label+'/result.json'
reports['path-fit-diagnostics']='tests/toilet-path-fit-diagnostics/result.json'
reports['authored-self-alignment']='tests/toilet-path-fit-diagnostics/self-alignment.json'
reports['support-normal-diagnostics']='tests/toilet-support-normal-diagnostics/result.json'
reports['worker-lifetime-shared-scope']='tests/toilet-exhaustive-audit/worker-lifetime-shared-scope.json'
reports['live-worker-lifetime-readonly']='tests/toilet-exhaustive-audit/live-worker-lifetime.json'
reports['explicit-fitter-parity']='tests/surface-guide-refine/explicit-module/result.json'
reports['integrated-fitter-inputs']='tests/surface-guide-refine/integrated-inputs/result.json'
reports['sampled-repair-unit-gates']='tests/surface-guide-refine/unit-gates/result.json'
reports['sampled-production-scope']='tests/toilet-exhaustive-audit/sampled-production-scope.json'
reports['browser-export-identity']='tests/toilet-fallback-browser/integrated-fallback/independent-identity.json'
reports['joint-fitter-parity']='tests/surface-guide-joint/detached-candidate/result.json'
reports['joint-fitter-default-parity']='tests/surface-guide-refine/detached-joint-defaults/result.json'
reports['joint-integrated-code']='tests/surface-guide-joint/integrated-code/result.json'
reports['live-joint-readonly']='tests/toilet-exhaustive-audit/live-joint-readonly.json'
reports['joint-browser-export-identity']='tests/toilet-fallback-browser/joint-integrated/independent-identity.json'
reports['joint-browser-runtime-cleanup']='tests/toilet-fallback-browser/joint-integrated/runtime-cleanup.json'
reports['joint-variant-process-cleanup']='tests/toilet-paired-variants/joint-integrated/process-cleanup.json'
for family, labels in {
    'objective-controls':['coarse-ratio34','perturb-distance64-tail0','perturb-distance64-tail0-serialized','coarse150-seed3-ratio34','coarse600-seed3-ratio34','short1799-seed3','short1799-seed5'],
    'layout-failures':['coarse-and-adjacent-density','coarse-and-adjacent-density-arrays'],
    'layout-inventory':['alternative-seeds-345'],
    'boundary-bridge':['coarse150-seed2','coarse150-seed2-lists'],
    'fresh-geometry':['perturb-distance64-tail0','surface-only','surface-only-browser'],
    'all-diagonal-audit':['perturb-distance64-tail0','surface-only','surface-only-browser'],
    'paired-variants':['surface-only'],
    'fallback-browser':['surface-only','surface-only-demand'],
    'render-idle':['demand-render','demand-dialog-fixed','demand-layout-final'],
    'editing':['demand-render','demand-dialog-fixed'],
    'selection-stability':['demand-render'],
}.items():
    for label in labels:
        reports[family+'-'+label]='tests/toilet-'+family+'/'+label+'/result.json'
for label in ('surface-only-long-control','surface-only-perturbed','surface-only-integrated'):
    reports[label]='tests/surface-guide-joint/'+label+'/result.json'
reports['surface-only-default-parity']='tests/surface-guide-refine/surface-only-defaults/result.json'
reports['surface-only-variant-cleanup']='tests/toilet-paired-variants/surface-only/process-cleanup.json'
reports['surface-only-browser-timeout-cleanup']='tests/toilet-fallback-browser/surface-only/runtime-cleanup.json'
reports['surface-only-browser-timeout-diagnostics']='tests/toilet-fallback-browser/surface-only/failure-diagnostics.json'
reports['surface-only-live-readonly']='tests/toilet-exhaustive-audit/live-surface-only-readonly.json'
reports['surface-only-browser-input-comparison']='tests/toilet-fallback-browser/surface-only-demand/service-comparison.json'
reports['surface-only-browser-nonidentical-export']='tests/toilet-fallback-browser/surface-only-demand/independent-identity.json'
reports['surface-only-browser-audited-download']='tests/toilet-fallback-browser/surface-only-demand/independent-download.json'
reports['surface-only-browser-cleanup']='tests/toilet-fallback-browser/surface-only-demand/runtime-cleanup.json'
reports['surface-only-checkpoint']='tests/toilet-exhaustive-audit/checkpoint-surface-only.json'
for family in ('path-reselection','long-surface-diagnostics','guided-route-review'):
    reports[family]='tests/toilet-'+family+'/result.json'
for family in ('fresh-geometry','all-diagonal-audit'):
    relative='tests/toilet-'+family+'/tangent-captured-seed2-weight12/result.json'
    if (ROOT/relative).exists():reports[family+'-tangent-captured-seed2-weight12']=relative
evidence={}
for name,relative in reports.items():
    path=ROOT/relative
    if not path.exists():
        evidence[name]=dict(report=relative,status='pending'); continue
    data=json.loads(path.read_text())
    item=dict(report=relative,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if isinstance(data,list):
        item.update(records=len(data),scope='Retained diagnostic records; no aggregate pass claim.')
        evidence[name]=item
        continue
    for key in ('passed','sourceValidationPassed','allReportedPairsConfirmed','complete','generationPassed','safetyChecksPassed','tests','errors'):
        if key in data: item[key]=data[key]
    if 'checks' in data:
        item['checks']=len(data['checks']); item['passedChecks']=sum(bool(c['passed']) for c in data['checks'])
    if 'cases' in data:
        item['cases']=[{k:c[k] for k in ('name','selection','iteration','state','passed','qualified','guideGatePassed','message') if k in c} for c in data['cases']]
    item['implementationHashMismatches']=[]
    provenance=path.parent/'script-provenance.json'
    if provenance.exists():
        note=json.loads(provenance.read_text())
        # A sibling cleanup/download report did not execute the generation
        # script. Attach that provenance only to reports that hash the script.
        if note['originalPath'] in data.get('sourceHashes',{}):
            snapshot=ROOT/note['executedScript']
            assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==note['executedSha256']
            assert data['sourceHashes'][note['originalPath']]==note['executedSha256']
            item['retainedHistoricalSource']=dict(provenance=str(provenance.relative_to(ROOT)),snapshot=note['executedScript'],sha256=note['executedSha256'])
    for file,digest in data.get('sourceHashes',{}).items():
        actual=ROOT/file
        if not actual.exists() or hashlib.sha256(actual.read_bytes()).hexdigest()!=digest:
            item['implementationHashMismatches'].append(file)
    evidence[name]=item
contact_proofs={}
for relative in ('tests/toilet-all-diagonal-audit/before-new-gate/result.json',
                 'tests/toilet-all-diagonal-audit/fresh-new-gate/result.json',
                 'tests/toilet-all-diagonal-audit/integrated-fallback/result.json',
                 'tests/toilet-all-diagonal-audit/paired-order-and-direction/result.json',
                 'tests/toilet-all-diagonal-audit/paired-sampling-and-density/result.json',
                 'tests/toilet-all-diagonal-audit/joint-integrated/result.json',
                 'tests/toilet-all-diagonal-audit/surface-only/result.json',
                 'tests/toilet-all-diagonal-audit/surface-only-browser/result.json'):
    path=ROOT/relative
    if path.exists():
        data=json.loads(path.read_text())
        for case in data.get('cases',[]):
            contact_proofs[case['outputSha256']]=dict(passed=case['passed'],report=relative)
qualified=[]; provisional=[]; disqualified=[]
current_source_hash=hashlib.sha256((ROOT/'assets/models/toilet.obj').read_bytes()).hexdigest()
for relative in ('tests/toilet-fresh-geometry/unguided-warpage/result.json',
                 'tests/toilet-fresh-geometry/guided-warpage/result.json',
                 'tests/toilet-fresh-geometry/representation-variants/result.json',
                 'tests/toilet-fresh-geometry/remaining-variants/result.json',
                 'tests/toilet-fresh-geometry/all-diagonal-generations/result.json',
                 'tests/toilet-fresh-geometry/integrated-fallback/result.json',
                 'tests/toilet-fresh-geometry/paired-order-and-direction/result.json',
                 'tests/toilet-fresh-geometry/paired-sampling-and-density/result.json',
                 'tests/toilet-fresh-geometry/joint-integrated/result.json',
                 'tests/toilet-fresh-geometry/surface-only/result.json',
                 'tests/toilet-fresh-geometry/surface-only-browser/result.json'):
    path=ROOT/relative
    if path.exists():
        data=json.loads(path.read_text())
        for case in data.get('cases',[]):
            item=dict(name=case['name'],report=relative,job=case['job'],outputSha256=case['outputSha256'],faces=case['shape']['faces'])
            proof=contact_proofs.get(case['outputSha256']); output=ROOT/case['outputFile']
            intact=output.exists() and hashlib.sha256(output.read_bytes()).hexdigest()==case['outputSha256'] and case['sourceSha256']==current_source_hash
            if not case.get('passed') or not intact or (proof and not proof['passed']):
                disqualified.append(dict(item,reason='Independent geometry failure, changed export, or failed all-diagonal contact audit.',contactProof=proof))
            elif proof:
                qualified.append(dict(item,contactProof=proof))
            else: provisional.append(dict(item,reason='All mixed-diagonal contact pairings have not yet been verified.'))
experimental=[]
for label in ('tangent-bowl-seed2','tangent-captured-seed2-weight12','sampled-path-401','both-diagonal-support-401','witness-short-seed2','fresh-short-seed2-export','long-constraint-memory','fresh-long-direct-tail80-export','perturb-distance64-tail0'):
    independent=ROOT/'tests/toilet-fresh-geometry'/label/'result.json'
    contacts=ROOT/'tests/toilet-all-diagonal-audit'/label/'result.json'
    if not independent.exists() or not contacts.exists():continue
    surface_report=json.loads(independent.read_text());contact_report=json.loads(contacts.read_text())
    if not surface_report.get('complete') or not contact_report.get('complete'):continue
    for case in surface_report.get('cases',[]):
        proof=next((p for p in contact_report.get('cases',[]) if p['outputSha256']==case['outputSha256'] and p['passed']),None)
        if case['passed'] and proof and case['sourceSha256']==current_source_hash and hashlib.sha256((ROOT/case['outputFile']).read_bytes()).hexdigest()==case['outputSha256']:
            experimental.append(dict(name=case['name'],outputSha256=case['outputSha256'],producerKind=case['producerKind'],
                productionResult=False,independentReport=str(independent.relative_to(ROOT)),contactReport=str(contacts.relative_to(ROOT))))
report=dict(completionProven=False,generatedToiletQualified=False,qualifiedSpecificCases=qualified,qualifiedExperimentalCases=experimental,
    provisionalSpecificCases=provisional,disqualifiedSpecificCases=disqualified,
    updatedAt=datetime.now(timezone.utc).isoformat(),evidence=evidence,
    interpretation=[
        'The final surface-only-demand browser run passes7checks and generates1845quads in480.15seconds. All10 sampled processes exit. The browser preserves every authored input point and adds one projected sample where an imported polyline segment exceeds0.04; its mesh therefore differs from the service-only export. The exact-identity comparison correctly fails and remains recorded. Independent fresh-geometry and all-mixed-diagonal audits of the actual browser OBJ both pass under surface-only-browser; the native download equals that independently audited OBJ. Final layout-aware rendering coverage passes18checks, including navigator/dock resizing and ribbon collapse without a window resize.',
        'The first adaptive browser run surface-only timed out during local repair. Its idle software renderer sampled about10logicalCPUs. On-demand rendering now stops when idle and repaints scene/guide/camera/display/size changes and damping. Fourteen rendering,130 editing and18 selection/repeated-use checks pass on final app bytes. The faster UI exposed duplicate error-dialog reopening during focus restoration; consuming the queued incident before showModal fixes it. Exact negative and corrected reports remain separate. Full generation retry uses surface-only-demand.',
        'The additional paired1799seed5 experiment has no contacts but remains unqualified on guide/surface requirements after three joint passes. It is not a production dispatch change or a successful generation.',
        'Adaptive surface repair now qualifies the captured perturbed paired guides through a fresh actual worker:1845quads in462.75seconds. Independent exported-geometry and all-mixed-diagonal audits pass under surface-only. When guide gates already pass, joint fitting uses distance weight64 and no extra tangent-tail penalty; otherwise the earlier80/32 settings remain. Sixty numerical checks reproduce the expected candidates and13 acceptance controls pass on the exact applied modules. Browser coverage is reported separately.',
        'Coarse targets150/600 and paired1799 remain unsolved. Alternative layout seeds and stronger edge-ratio objectives still create face contacts. Bridging all three cyclic correspondences between the raw150 layout boundary loops restores closed Euler0 connectivity but fails contacts in every fitted candidate. These are rejected experimental candidates; production connectivity and acceptance limits are unchanged. Preliminary harness type/serialization errors are retained separately from geometry failures.',
        'The sampled-path fitter is now a bounded production fallback after the original guided attempts fail. Fresh HTTP/worker bowl-only and short combined requests both produce1845quads; their actual exported OBJs pass the independent and all-diagonal audits. The source asset and acceptance thresholds are unchanged. Exact executed code and retained historical reports are distinguished below.',
        'The earlier joint repair stalled at31.938degrees. Remembering rejected surface witnesses as barycentric triangle constraints subsequently qualifies the longer guide. A fresh source pipeline with tangent tail weight80 needs two joint steps and passes both independent audits. The explicit production modules reproduce that candidate exactly; service/browser qualification is recorded separately.',
        'The integrated real-service long-guide request produces1845quads in309.8seconds. Its actual worker OBJ passes the independent surface/path/reference/LP/BVH audit and allmixeddiagonal contact audit. Browser/runtime and cancellation are separate observations; no threshold or source mesh changed.',
        'The fresh long/Circle browser run passes13checks; downloads/curves/paths match independently qualified exports. The long job takes493.6seconds with software-renderer contention. All10 sampled test processes exit, and actual joint-stage cancellation passes11checks.',
        'At the earlier b63828f checkpoint, the perturbed paired-guide request timed out at600seconds during joint pass7. That exact negative report remains; the later adaptive worker pass above supersedes this specific perturbation failure. Target1799 still rejects contacts after265seconds. Rejection/input-preservation and process-cleanup checks pass.',
        'Paired-guide reversal, order, densification and closed-start rotation produce accepted meshes. Small source-projected perturbation fails surface accuracy, and paired target1799 fails contacts before joint integration. These are unsolved generations, even though rejection and input-preservation checks pass. Coarse unguided seed2 targets150/600 also fail shape limits; that experimental route is not enabled for unguided production requests.',
        'The initial sampled-stage cancellation observer incorrectly included the live service console among worker-owned processes. Its failed result is retained with exact executed source and timestamps. The worker-owned rerun identifies the exact job worker and its descendants; no production cancellation code changed for this observer correction.',
        'Browser-generated request identities extend ownership to lost initial admission responses and cancellation before delivery. Exact-hash reports retain negative reproductions, corrected observers, completed sequential reruns and interrupted observations separately.',
        'Windows forced-exit tests use an actual toilet worker and Blender child; a service process job now owns their lifetime. Deduplication and early-cancellation records are per service lifetime. Non-Windows forced-exit cleanup is not claimed.',
        'Worker-only forced exit reproduced a live orphan Blender while the service survived. A nested worker lifetime job fixes it. The nested-worker-job suites pass 166 scoped checks on their recorded hashes, before the separately preserved opt-in guided-layout dispatch edit and later sampled-fit integration.',
        'The request-ownership generated-UI run passed 12 checks before a genuine progress-file sharing violation cancelled its second Circle solve. The ownership-io attempt subsequently cancelled without a server traceback and is retained as incomplete. All 15 ownership-io-diagnostics workflow checks pass on final app/server code with two genuine fresh Circle solves; this does not establish the cause of the earlier unexplained interruption.',
        'The c8e5b83 request-ownership checkpoint retains 274 scoped checks including 15 genuine generated-result browser checks. Exact hashes and component scopes are retained; later worker-lifetime tests are a distinct checkpoint, not an additive claim about a single final revision.',
        'The isolated tangent/sliding-pin bowl experiment passes existing production gates, but is not integrated. Independent experimental export reports are separate from actual service-generated mesh qualification.',
        'The distributed 401-sample objective retains the unchanged 257-sample acceptance metric. Bowl-only passes solver gates; the shorter combined case reaches guide limits but fails whole-surface bounds, and the longer case still fails tangent alignment. Separate both-diagonal source-support experiments preserve all acceptance limits.',
        'Both-diagonal vertex/centroid support and its opposing-normal-filter variant each fail all 15 captured-case attempts with contacts. These completed negative experiments do not change production fitting or excuse any failed acceptance gate.',
        'The earlier local witness experiment and fresh-source pipeline qualify the short combined input under every unchanged gate. The subsequent integrated worker reproduces its exact positions and faces with a different OBJ header. Its narrow guide-distance margin still requires input-variation work.',
        'All 18 coarse blend trials remain unqualified. A preliminary blend harness type error is retained separately. Long-guide path reselection is unchanged; its full surface bounds also fail, so tangent improvement alone will not qualify that candidate.',
        'Extra genuine layout seeds 2/3 fail all six captured complex-guide cases. Sliding pins on seed 2 fail guide alignment in every pass. These isolated experiments are not in production and do not qualify geometry.',
        'Green lifecycle, editing or rejection checks do not qualify the generated geometry.',
        'Earlier API/browser reports retain their original implementation hashes. Current post-admission-fix suites separately verify 76 HTTP and 29 browser checks with a named Circle positive control; the original bowl-generation failure remains recorded.',
        'Right-pane editing uses an explicitly unqualified historical rendering fixture; it does not simulate or claim successful generation.',
        'Specific-case qualification requires both the independent surface/path audit and the all-mixed-diagonal contact audit on an unchanged export. A prior fan-only pass cannot qualify the failed perturbed Circle.',
        'New generated-result UI tests use genuine completed worker responses and actual exports, separately from the historical editor fixture.',
        'Sparse/dense sample audits and adaptive whole-triangle bounds have different scopes; both triangulation conventions are retained.',
        'The original source is unchanged. Its four known contacts are spatially separate from the newly detected bowl overlaps.',
    ],remaining=[
        'Captured two-guide networks and basic toilet solves must meet all geometric requirements.',
        'Bowl-only, short paired, long paired and captured perturbed paired cases at1800 now have independently qualified production results. The long case passes actual browser/export and cancellation coverage. The native perturbed browser variant also passes independent export audits. Target1799 and coarse targets still fail; broader robustness and final reconciliation remain required.',
        'Finite reversal/cyclic-start/densification/order/perturbation/density cases have been exercised; several failures and remaining generation acceptance outcomes still require resolution.',
        'Fresh all-diagonal Circle/reversed-lid/perturbed-Circle generations and independent export audits pass; the broader failing guide/density cases remain unresolved.',
        'Lost initial acknowledgement, before-delivery Cancel/Reset, real service restart and locked progress/cancellation files have dedicated coverage. Reconcile each final suite against its exact implementation hash.',
        'Actual worker/Blender timeout cleanup and generated-result browser workflow now pass; broader sustained process/memory recovery needs final reconciliation.',
        'Final implementation/evidence reconciliation and authorized check-in remain required. Shared guided-layout edits are preserved separately; live-server reports identify their historical checkpoint and are not claims about subsequently changed files.',
    ])
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
print(json.dumps(dict(completionProven=False,reports=len(evidence),pending=[k for k,v in evidence.items() if v.get('status')=='pending'],
                      incompleteWorkflows=[k for k,v in evidence.items() if v.get('complete') is False])))
