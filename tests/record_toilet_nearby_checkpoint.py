"""Reconcile bounded layout retry evidence without claiming all densities work."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
paths = {
    'retryControls': 'tests/surface-layout-retries/nearby-layouts/result.json',
    'service': 'tests/toilet-paired-variants/nearby-layouts/result.json',
    'geometry': 'tests/toilet-fresh-geometry/paired1799-integrated/result.json',
    'contacts': 'tests/toilet-all-diagonal-audit/paired1799-integrated/result.json',
    'serviceCleanup': 'tests/toilet-paired-variants/nearby-layouts/process-cleanup.json',
    'serviceArchives': 'tests/toilet-paired-variants/nearby-layouts/layout-artifacts.json',
    'browser': 'tests/toilet-fallback-browser/nearby-layouts/result.json',
    'browserIdentity': 'tests/toilet-fallback-browser/nearby-layouts/independent-identity.json',
    'browserCleanup': 'tests/toilet-fallback-browser/nearby-layouts/runtime-cleanup.json',
    'browserArchives': 'tests/toilet-fallback-browser/nearby-layouts/layout-artifacts.json',
    'imports': 'tests/toilet-import-races/queued-errors/result.json',
    'cancelDuringRetry': 'tests/toilet-fallback-cancel/nearby-layouts/result.json',
    'cancelledLayoutProof': 'tests/toilet-fallback-cancel/nearby-layouts/second-layout-proof.json',
    'liveApp': 'tests/toilet-exhaustive-audit/live-nearby-readonly.json',
}
records = {}
for name, relative in paths.items():
    path = ROOT / relative
    data = json.loads(path.read_text())
    assert data['complete'] and data.get('passed', data.get('generationPassed', False)), relative
    assert not data.get('errors'), relative
    for filename, digest in data.get('sourceHashes', {}).items():
        assert sha(ROOT / filename) == digest, filename
    records[name] = dict(report=relative, sha256=sha(path))

service = json.loads((ROOT / paths['service']).read_text())
browser = json.loads((ROOT / paths['browser']).read_text())
case = service['cases'][0]
assert service['safetyChecksPassed'] and browser['implementationUnchanged']
assert case['target'] == 1799 and case['faces'] == 1845
assert browser['cases'][0]['outputSha256'] == case['outputSha256']
for kind in ('serviceArchives', 'browserArchives'):
    attempts = json.loads((ROOT / paths[kind]).read_text())['cases'][0]['attempts']
    assert [(a['layoutTarget'], a['accepted']) for a in attempts] == [(1799, False), (1800, True)]
    assert all(a['requestedTarget'] == 1799 for a in attempts)

experiments = []
for label in ('paired1799-neighbor', 'coarse600-neighbor'):
    proofs = {}
    for family in ('toilet-fresh-geometry', 'toilet-all-diagonal-audit'):
        path = ROOT / 'tests' / family / label / 'result.json'
        data = json.loads(path.read_text())
        assert data['complete'] and data['passed']
        proofs[family] = dict(report=str(path.relative_to(ROOT)), sha256=sha(path))
    experiments.append(dict(label=label, productionResult=False, proofs=proofs))

negatives = []
for relative in (
    'tests/toilet-target-neighborhood/coarse150-upper-neighbors/result.json',
    'tests/toilet-target-neighborhood/coarse150-layout170/result.json',
    'tests/toilet-target-neighborhood/coarse150-layout172/result.json',
    'tests/toilet-objective-controls/coarse150-layout172-ratio34/result.json',
):
    path = ROOT / relative
    data = json.loads(path.read_text())
    assert data['complete'] and not data.get('errors')
    assert all(c['state'] == 'failed' for c in data['cases'])
    negatives.append(dict(report=relative, sha256=sha(path), qualified=False))
path = ROOT / 'tests/toilet-unsubdivide/coarse150-from605/rejection.json'
data = json.loads(path.read_text())
assert data['passed'] and not data['generationPassed']
negatives.append(dict(report=str(path.relative_to(ROOT)), sha256=sha(path), qualified=False))

prior = json.loads((ROOT / 'tests/toilet-exhaustive-audit/checkpoint-surface-only.json').read_text())
for name in ('app.js', 'server.py', 'curved_quad.py', 'worker.py', 'surface_guide_refine.py', 'surface_guide_joint.py',
             'surface_distance.py', 'surface_intersections.py', 'quad_quality.py', 'assets/models/toilet.obj'):
    assert sha(ROOT / name) == prior['sourceHashes'][name], name
protected = json.loads((ROOT / 'runs/surface-only-checkin.json').read_text())['protectedWorktreeHashes']
assert all(sha(ROOT / name) == digest for name, digest in protected.items())

files = ['app.js', 'server.py', 'worker.py', 'curved_quad.py', 'surface_guide_refine.py', 'surface_guide_joint.py',
         'surface_guide_repair.py', 'surface_distance.py', 'surface_intersections.py', 'quad_quality.py',
         'assets/models/toilet.obj', 'tests/record_toilet_nearby_checkpoint.py']
report = dict(complete=True, passed=True, goalComplete=False, checkedAt=datetime.now(timezone.utc).isoformat(),
              sourceHashes={name: sha(ROOT / name) for name in files}, evidence=records,
              outputSha256=case['outputSha256'], faces=case['faces'], requestedTarget=1799,
              serviceSeconds=case['elapsedSeconds'], browserSeconds=browser['cases'][0]['elapsedSeconds'],
              qualifiedExperiments=experiments, rejectedExperiments=negatives,
              protectedSharedWorktreeHashes=protected,
              remaining=['Target150 remains unqualified.',
                         'No-guide600 has a qualified isolated candidate; shared unguided dispatch patch is separate pending coordination.',
                         'Browser runtime572.79seconds is close to the600second service timeout.',
                         'Broader robustness and final requirements reconciliation remain open.'],
              scope='Exact applied bounded retry code, actual1799worker/browser exports, independent geometry/contact qualification, cancellation during the second layout and observed cleanup. Source, numerical fitters, gate limits, shared dispatch and app unchanged. Experimental600 qualification is separate from production acceptance.')
path = ROOT / 'tests/toilet-exhaustive-audit/checkpoint-nearby-layouts.json'
path.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, faces=case['faces'], evidence=len(records), qualifiedExperiments=len(experiments), negatives=len(negatives))))
