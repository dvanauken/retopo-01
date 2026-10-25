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
    'fresh-geometry':['tangent-bowl-seed2','sampled-path-401'],
    'all-diagonal-audit':['tangent-bowl-seed2','sampled-path-401'],
    'sampled-paths':['captured-seed2-401'],
    'both-diagonal-support':['captured-seed2-401'],
    'oriented-support':['captured-seed2-401'],
}.items():
    for label in labels:
        reports[family+'-'+label]='tests/toilet-'+family+'/'+label+'/result.json'
reports['path-fit-diagnostics']='tests/toilet-path-fit-diagnostics/result.json'
reports['authored-self-alignment']='tests/toilet-path-fit-diagnostics/self-alignment.json'
reports['support-normal-diagnostics']='tests/toilet-support-normal-diagnostics/result.json'
reports['worker-lifetime-shared-scope']='tests/toilet-exhaustive-audit/worker-lifetime-shared-scope.json'
reports['live-worker-lifetime-readonly']='tests/toilet-exhaustive-audit/live-worker-lifetime.json'
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
        item['cases']=[{k:c[k] for k in ('name','state','passed','qualified','message') if k in c} for c in data['cases']]
    item['implementationHashMismatches']=[]
    provenance=path.parent/'script-provenance.json'
    if provenance.exists():
        note=json.loads(provenance.read_text())
        snapshot=ROOT/note['executedScript']
        assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==note['executedSha256']
        item['retainedHistoricalSource']=dict(provenance=str(provenance.relative_to(ROOT)),snapshot=note['executedScript'],sha256=note['executedSha256'])
    for file,digest in data.get('sourceHashes',{}).items():
        actual=ROOT/file
        if not actual.exists() or hashlib.sha256(actual.read_bytes()).hexdigest()!=digest:
            item['implementationHashMismatches'].append(file)
    evidence[name]=item
contact_proofs={}
for relative in ('tests/toilet-all-diagonal-audit/before-new-gate/result.json',
                 'tests/toilet-all-diagonal-audit/fresh-new-gate/result.json'):
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
                 'tests/toilet-fresh-geometry/all-diagonal-generations/result.json'):
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
for label in ('tangent-bowl-seed2','tangent-captured-seed2-weight12','sampled-path-401','both-diagonal-support-401'):
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
        'Browser-generated request identities extend ownership to lost initial admission responses and cancellation before delivery. Exact-hash reports retain negative reproductions, corrected observers, completed sequential reruns and interrupted observations separately.',
        'Windows forced-exit tests use an actual toilet worker and Blender child; a service process job now owns their lifetime. Deduplication and early-cancellation records are per service lifetime. Non-Windows forced-exit cleanup is not claimed.',
        'Worker-only forced exit reproduced a live orphan Blender while the service survived. A nested worker lifetime job fixes it. The nested-worker-job suites pass 166 scoped checks on their recorded hashes, before a concurrent opt-in guided-layout dispatch edit. Experimental fitting remains isolated from production.',
        'The request-ownership generated-UI run passed 12 checks before a genuine progress-file sharing violation cancelled its second Circle solve. The ownership-io attempt subsequently cancelled without a server traceback and is retained as incomplete. All 15 ownership-io-diagnostics workflow checks pass on final app/server code with two genuine fresh Circle solves; this does not establish the cause of the earlier unexplained interruption.',
        'The c8e5b83 request-ownership checkpoint retains 274 scoped checks including 15 genuine generated-result browser checks. Exact hashes and component scopes are retained; later worker-lifetime tests are a distinct checkpoint, not an additive claim about a single final revision.',
        'The isolated tangent/sliding-pin bowl experiment passes existing production gates, but is not integrated. Independent experimental export reports are separate from actual service-generated mesh qualification.',
        'The distributed 401-sample objective retains the unchanged 257-sample acceptance metric. Bowl-only passes solver gates; the shorter combined case reaches guide limits but fails whole-surface bounds, and the longer case still fails tangent alignment. Separate both-diagonal source-support experiments preserve all acceptance limits.',
        'Both-diagonal vertex/centroid support and its opposing-normal-filter variant each fail all 15 captured-case attempts with contacts. These completed negative experiments do not change production fitting or excuse any failed acceptance gate.',
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
        'Finite reversal/cyclic-start/densification/order/perturbation/density cases have been exercised; several failures and remaining generation acceptance outcomes still require resolution.',
        'Fresh all-diagonal Circle/reversed-lid/perturbed-Circle generations and independent export audits pass; the broader failing guide/density cases remain unresolved.',
        'Lost initial acknowledgement, before-delivery Cancel/Reset, real service restart and locked progress/cancellation files have dedicated coverage. Reconcile each final suite against its exact implementation hash.',
        'Actual worker/Blender timeout cleanup and generated-result browser workflow now pass; broader sustained process/memory recovery needs final reconciliation.',
        'Final implementation/evidence reconciliation and authorized check-in remain required. Shared guided-layout edits are preserved separately; live-server reports identify their historical checkpoint and are not claims about subsequently changed files.',
    ])
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
print(json.dumps(dict(completionProven=False,reports=len(evidence),pending=[k for k,v in evidence.items() if v.get('status')=='pending'],
                      incompleteWorkflows=[k for k,v in evidence.items() if v.get('complete') is False])))
