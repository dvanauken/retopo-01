"""Reconcile finite toilet requirements against exact retained test evidence.

This does not rerun the solver or turn failed experiments into passes. It checks
report outcomes, component identity, actual OBJ hashes and paired independent
audits. Historical reports keep their original implementation scope.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests/toilet-final-audit'
OUT.mkdir(exist_ok=True)
GIT = ['git', '-c', 'safe.directory=C:/dbva/code/retopo-1']
sha = lambda value: hashlib.sha256(value).hexdigest()
load = lambda name: json.loads((ROOT / name).read_text())

# Each row names the actual evidence for one finite requirement area. Counts
# overlap; they must not be added to imply one giant run on a single revision.
GROUPS = {
    'original-source': ['tests/toilet-source/result.json'],
    'guide-geometry': ['tests/guide-additions/result.json', 'tests/toilet-editing/demand-dialog-fixed/result.json'],
    'editing': ['tests/toilet-editing/demand-dialog-fixed/result.json', 'tests/toilet-selection-stability/demand-render/result.json'],
    'persistence': ['tests/toilet-editing/demand-dialog-fixed/result.json', 'tests/toilet-import-races/queued-errors/result.json'],
    'solver': ['tests/toilet-sampled-worker/integrated-fallback/result.json', 'tests/toilet-sampled-worker/joint-integrated/result.json', 'tests/toilet-paired-variants/surface-only/result.json', 'tests/toilet-paired-variants/nearby-layouts/result.json', 'tests/toilet-coarse-browser/no-guides/result.json'],
    'geometry-acceptance': ['tests/surface-boundary-repair/owned-candidate/result.json', 'tests/surface-boundary-repair/commit-scope/result.json', 'tests/toilet-unit-gates/nested-worker-job/result.json'],
    'job-lifecycle': ['tests/toilet-server-restart/nested-worker-job/result.json', 'tests/toilet-worker-crash/shared-dispatch-worker-job/result.json', 'tests/toilet-process-timeout/nested-worker-job/result.json', 'tests/toilet-file-locks/nested-worker-job/result.json', 'tests/toilet-fallback-cancel/nearby-layouts/result.json'],
    'api-contract': ['tests/toilet-api/ownership-io/result.json'],
    'ui-lifecycle': ['tests/toilet-cancel-transport/ownership-io/result.json', 'tests/toilet-async-ui/ownership-io/result.json', 'tests/toilet-submission-transport/ownership-io/result.json', 'tests/toilet-early-submission/ownership-io/result.json', 'tests/toilet-generated-ui/ownership-io-diagnostics/result.json', 'tests/toilet-fallback-browser/surface-only-demand/result.json'],
    'workspace': ['tests/toilet-final-audit/workspace/result.json', 'tests/toilet-final-audit/workspace/scope.json', 'tests/toilet-render-idle/demand-layout-final/result.json'],
    'runtime': ['tests/toilet-selection-stability/demand-render/result.json', 'tests/toilet-fallback-browser/joint-integrated/runtime-cleanup.json', 'tests/toilet-fallback-browser/surface-only-demand/runtime-cleanup.json', 'tests/toilet-fallback-browser/nearby-layouts/runtime-cleanup.json', 'tests/toilet-coarse-browser/no-guides/process-observation.json'],
    'evidence': ['tests/toilet-exhaustive-audit/checkpoint-boundary-repair.json', 'tests/surface-boundary-repair/runtime-identity/result.json', 'tests/toilet-final-audit/dispatch-separation/result.json'],
}

# Select positive cases explicitly inside mixed historical reports. In
# particular, the old perturbed Circle is NOT qualified by its fan-only audit.
GEOMETRY = [
    ('unguided-warpage', 'before-new-gate', None),
    ('guided-warpage', 'before-new-gate', None),
    ('representation-variants', 'before-new-gate', ['circle-reversed', 'circle-cyclic-start']),
    ('remaining-variants', 'before-new-gate', ['unguided-1200', 'unguided-1799']),
    ('all-diagonal-generations', 'fresh-new-gate', None),
    ('integrated-fallback', 'integrated-fallback', None),
    ('paired-order-and-direction', 'paired-order-and-direction', None),
    ('paired-sampling-and-density', 'paired-sampling-and-density', None),
    ('joint-integrated', 'joint-integrated', None),
    ('surface-only', 'surface-only', None),
    ('surface-only-browser', 'surface-only-browser', None),
    ('paired1799-integrated', 'paired1799-integrated', None),
    ('coarse-browser-proposed', 'coarse-browser-proposed', None),
]

checks = []
def check(value, name):
    checks.append(dict(passed=bool(value), name=name))
    if not value:
        raise AssertionError(name)

evidence = {}
for area, paths in GROUPS.items():
    for path in paths:
        if path in evidence:
            continue
        data = load(path)
        success = data.get('passed', data.get('generationPassed', data.get('sourceValidationPassed', False)))
        check(success and data.get('complete', True), 'Completed passing evidence: ' + path)
        check(all(c['passed'] for c in data.get('checks', [])), 'All listed assertions pass: ' + path)
        evidence[path] = dict(sha256=sha((ROOT/path).read_bytes()), checks=len(data.get('checks', [])),
            tests=data.get('tests'), componentHashDifferences=[name for name, digest in data.get('sourceHashes', {}).items()
                if not (ROOT/name).is_file() or sha((ROOT/name).read_bytes()) != digest])

qualified = []
for geometry_label, contact_label, names in GEOMETRY:
    geometry_path = f'tests/toilet-fresh-geometry/{geometry_label}/result.json'
    contact_path = f'tests/toilet-all-diagonal-audit/{contact_label}/result.json'
    geometry, contact = load(geometry_path), load(contact_path)
    check(geometry['complete'] and contact['complete'], 'Independent audits completed: ' + geometry_label)
    cases = [c for c in geometry['cases'] if names is None or c['name'] in names]
    check(bool(cases) and (names is None or {c['name'] for c in cases} == set(names)), 'Named geometry coverage: ' + geometry_label)
    for case in cases:
        matched = [c for c in contact['cases'] if c['outputSha256'] == case['outputSha256'] and c['passed']]
        check(case['passed'] and bool(matched), 'Geometry and all-diagonal contacts qualify: ' + case['name'])
        mesh = ROOT / case['outputFile']
        check(sha(mesh.read_bytes()) == case['outputSha256'], 'Audited OBJ bytes retained: ' + case['name'])
        check(case['shape']['passed'] and case['shape']['quadOnly'], 'Actual quad shape qualifies: ' + case['name'])
        for guide in case['guideFits']:
            check(guide['passed'] and guide['pathValid'], 'Connected guide path qualifies: ' + case['name'])
        qualified.append(dict(name=case['name'], target=case['target'], faces=case['shape']['faces'],
            outputFile=case['outputFile'], outputSha256=case['outputSha256'], guideCount=len(case['guideFits']),
            geometryReport=geometry_path, geometryReportSha256=sha((ROOT/geometry_path).read_bytes()),
            contactReport=contact_path, contactReportSha256=sha((ROOT/contact_path).read_bytes()),
            scope='This exact generated/exported mesh. Producer implementations remain identified in the linked reports.'))

# Current editor assertions cover every editor module, HTML and app integration.
editor = load('tests/toilet-editing/demand-dialog-fixed/result.json')
check(all(sha((ROOT/name).read_bytes()) == digest for name, digest in editor['sourceHashes'].items()),
      'Current app and every editor module match the 130-check toilet suite')
check(sha((ROOT/'assets/models/toilet.obj').read_bytes()) == 'c2daa898fe3361bf3f971e83d6a274eda2126be8ecca2f652c23f446c9867053',
      'Original toilet source unchanged')

# The post-lifecycle app change is rendering/error-dialog work. Compare the
# entire intervening request/editor event block, not a hand-picked few tokens.
older_app = subprocess.check_output(GIT + ['show', 'c8e5b83:app.js'], cwd=ROOT).decode().replace('\r\n','\n')
current_app = (ROOT/'app.js').read_text()
begin, end = 'function setAttempt(', "window.addEventListener('keyup'"
block = lambda s: s[s.index(begin):s.index(end)]
check(block(older_app) == block(current_app), 'Request ownership, generation, cancellation and editor event block unchanged since lifecycle suites')
api = load('tests/toilet-api/ownership-io/result.json')
check(sha((ROOT/'server.py').read_bytes()) == api['sourceHashes']['server.py'], 'Current server matches 76-check API suite')
restart = load('tests/toilet-server-restart/nested-worker-job/result.json')
check(sha((ROOT/'process_ownership.py').read_bytes()) == restart['sourceHashes']['process_ownership.py'], 'Current process ownership matches forced-exit/timeout tests')

snapshot = load('tests/toilet-coarse-browser/no-guides/frozen-service-snapshot.json')
runtime_names = [name for name in snapshot['files'] if name != 'unguided-dispatch.patch']
check(all(sha((ROOT/name).read_bytes()) == snapshot['files'][name] for name in runtime_names),
      'All 247 runtime/app/assets match the real-worker coarse browser run after authorized patch integration')
separation = load('tests/toilet-final-audit/dispatch-separation/result.json')
check(sha((ROOT/'curved_quad.py').read_bytes()) == separation['sharedBeforeSha256'], 'Reintegrated dispatcher exactly matches validated code')
protected = load('tests/toilet-final-audit/ownership-snapshot.json')
for name in protected['unownedFiles']:
    check(sha((ROOT/name).read_bytes()) == protected['worktreeHashesBefore'][name], 'Other-session file preserved: ' + name)
for name in protected['partialFiles']:
    check(sha((ROOT/name).read_bytes()) == protected['worktreeHashesBefore'][name], 'Shared file restored/preserved exactly: ' + name)

report = dict(complete=True, passed=True, requirementsCovered=list(GROUPS), groups=GROUPS,
    checkedAt=datetime.now(timezone.utc).isoformat(), testedCommittedBaseline='23a8818cf7cdccd04b98f8944df0dc9cfce87cb8',
    checks=checks, evidence=evidence, qualifiedExports=qualified,
    uniqueQualifiedMeshes=len({c['outputSha256'] for c in qualified}), runtimeFilesMatched=len(runtime_names),
    dispatchIntegrated=True, dispatchAuthorization='User subsequently authorized merging the patch; exact tested bytes restored.',
    sourceHashes={name:sha((ROOT/name).read_bytes()) for name in ['app.js','index.html','index.css','server.py','worker.py','curved_quad.py','surface_guide_refine.py','surface_guide_repair.py','surface_guide_joint.py','surface_boundary_repair.py','surface_distance.py','surface_intersections.py','quad_quality.py','tests/reconcile_toilet_audit.py']},
    limitations=[
        'Finite test matrix, not a proof for every possible guide network, density or machine.',
        'Slow paired browser case: 572.79 seconds against a 600-second timeout. Performance remains a product limitation.',
        'Historical rejection, incomplete observer and failed experiment reports remain unchanged; they do not qualify their meshes.',
        'Other-session optional guided-layout/ellipsoid and one-35-degree guide policy are excluded from this solver certification. Owned baseline keeps all guide limits at 30 degrees; shared unguided behavior is separately qualified.',
        'Right-pane editor stress fixture is historical/unqualified; genuine accepted-pane editing is separately covered by generated-ui tests.',
        'Bounded memory/process observations do not establish universal leak freedom or crash recovery on other operating systems.',
        'Guide-specific 2D adaptation covers Freehand/Polyline/Spline/Circle; it is not full thirteen-primitive Base 2D conformance.',
    ],
    scope='Final finite requirements reconciliation. Independent retained geometry audits plus component-scoped UI/lifecycle tests and current runtime identity. No blanket claim that all historical suites executed together on the latest shared worktree.')
(OUT/'result.json').write_text(json.dumps(report, indent=2)+'\n', newline='\n')
print(json.dumps(dict(passed=True, areas=len(GROUPS), checks=len(checks), qualifiedExports=len(qualified), uniqueQualifiedMeshes=report['uniqueQualifiedMeshes'], runtimeFilesMatched=len(runtime_names))))
