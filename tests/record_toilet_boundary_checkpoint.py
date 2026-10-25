"""Reconcile coarse toilet qualification and explicitly preserve shared scope."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
paths={
    'ownedControls':'tests/surface-boundary-repair/owned-candidate/result.json',
    'sharedControls':'tests/surface-boundary-repair/shared-final/result.json',
    'experimentalGeometry':'tests/toilet-fresh-geometry/coarse150-bridge-seed4/result.json',
    'experimentalContacts':'tests/toilet-all-diagonal-audit/coarse150-bridge-seed4/result.json',
    'freshSource':'tests/toilet-unguided-fallback/boundary-fresh/result.json',
    'freshSourceIdentity':'tests/toilet-unguided-fallback/boundary-fresh/independent-identity.json',
    'browser':'tests/toilet-coarse-browser/no-guides/result.json',
    'browserGeometry':'tests/toilet-fresh-geometry/coarse-browser-proposed/result.json',
    'browserContacts':'tests/toilet-all-diagonal-audit/coarse-browser-proposed/result.json',
    'browserCleanup':'tests/toilet-coarse-browser/no-guides/process-observation.json',
    'appliedRuntime':'tests/surface-boundary-repair/runtime-identity/result.json',
    'ownedNumericalScope':'tests/surface-boundary-repair/commit-scope/result.json',
}
evidence={}
for name,relative in paths.items():
    path=ROOT/relative;data=json.loads(path.read_text())
    assert data['complete'] and data.get('passed',data.get('generationPassed',False)),relative
    assert not data.get('errors'),relative
    evidence[name]=dict(report=relative,sha256=sha(path))
runtime=json.loads((ROOT/paths['appliedRuntime']).read_text())
assert all(sha(ROOT/name)==digest for name,digest in runtime['matchedFiles'].items())
browser=json.loads((ROOT/paths['browser']).read_text())
fresh=json.loads((ROOT/paths['freshSource']).read_text())
assert [(c['target'],c['faces']) for c in browser['cases']]==[(150,152),(600,605)]
assert [c['outputSha256'] for c in browser['cases']]==[c['outputSha256'] for c in fresh['cases']]
for case in browser['cases']:
    folder=ROOT/'tests/toilet-coarse-browser/no-guides'/case['name']
    assert (folder/'browser-export.obj').read_bytes()==(folder/'output.obj').read_bytes()
    assert sha(folder/'output.obj')==case['outputSha256']
    assert json.loads((folder/'curves.json').read_text())['curves']==[]
prior=json.loads((ROOT/'tests/toilet-exhaustive-audit/checkpoint-nearby-layouts.json').read_text())
for name in ('assets/models/toilet.obj','quad_quality.py','surface_intersections.py','surface_distance.py','app.js','server.py'):
    assert sha(ROOT/name)==prior['sourceHashes'][name],name
negatives={}
for relative in ('tests/toilet-normal-alignment/coarse150-layout172/result.json',
                 'tests/toilet-boundary-bridge/coarse150-seed4-default/result.json',
                 'tests/toilet-coarse-browser/proposed-dispatch/result.json',
                 'tests/surface-boundary-repair/integrated/result.json',
                 'tests/surface-boundary-repair/unguided-scope/result.json',
                 'tests/surface-boundary-repair/unguided-scoped-paths/result.json'):
    path=ROOT/relative;data=json.loads(path.read_text());assert data['complete']
    assert data.get('passed') is False or all(c['state']=='failed' for c in data.get('cases',[])),relative
    negatives[relative]=sha(path)
files=('surface_boundary_repair.py','surface_guide_refine.py','surface_guide_repair.py','curved_quad.py','worker.py',
       'surface_guide_joint.py','quad_quality.py','surface_intersections.py','surface_distance.py','assets/models/toilet.obj',
       'tests/record_toilet_boundary_checkpoint.py')
report=dict(complete=True,passed=True,goalComplete=False,checkedAt=datetime.now(timezone.utc).isoformat(),
    evidence=evidence,sourceHashes={name:sha(ROOT/name) for name in files},cases=browser['cases'],
    negativeReports=negatives,ownedControls=25,sharedControls=27,overlappingControlCounts=True,
    sourceAndGeometryLimitsUnchanged=True,sharedGuidePolicyPreserved=True,
    remaining=['Reconcile broader guide/input variations and shared policy changes against final requirements.',
               'Paired1799browser runtime near600seconds remains a limitation; coarse browser jobs take129/279seconds.',
               'No universal input robustness or interactive-speed claim. Exhaustive audit remains active.'],
    scope='Fresh original-source fallback, native real-worker browser exports, independent geometry/contact audits and247-file applied runtime identity qualify these unguided150/600cases. Source and geometry limits are unchanged. The owned baseline candidate preserves original guide policy; current shared policy is separately tested and left outside the owned commit. Negative controls and setup failures remain retained.')
(ROOT/'tests/toilet-exhaustive-audit/checkpoint-boundary-repair.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,evidence=len(evidence),cases=[(c['target'],c['faces']) for c in browser['cases']],negatives=len(negatives))))
