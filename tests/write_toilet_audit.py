"""Index retained evidence without converting safe failures into solved meshes."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests/toilet-exhaustive-audit'; OUT.mkdir(exist_ok=True)
reports={
    'original-source':'tests/toilet-source/result.json',
    'api-boundaries-and-lifecycle':'tests/toilet-api/current/result.json',
    'browser-async-lifecycle':'tests/toilet-async-ui/request-context-complete/result.json',
    'toilet-editor':'tests/toilet-editing/current/result.json',
    'numeric-and-worker-units':'tests/toilet-unit-gates/current/result.json',
    'dense-ear-surface':'tests/toilet-dense-surface/result.json',
    'dense-fan-surface':'tests/toilet-dense-surface/fan-result.json',
    'adjacent-contacts':'tests/toilet-adjacent-contacts/result.json',
    'independent-contact-witnesses':'tests/toilet-adjacent-contacts/lp-witnesses.json',
    'whole-surface-and-contact-audit':'tests/toilet-acceptance-audit/result.json',
    'first-strict-six-case-matrix':'tests/toilet-strict-generation/result.json',
    'fresh-strict-generation':'tests/toilet-strict-generation/current/result.json',
    'live-server-publication':'tests/toilet-exhaustive-audit/live-server.json',
}
evidence={}
for name,relative in reports.items():
    path=ROOT/relative
    if not path.exists():
        evidence[name]=dict(report=relative,status='pending'); continue
    data=json.loads(path.read_text())
    item=dict(report=relative,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    for key in ('passed','sourceValidationPassed','allReportedPairsConfirmed','complete','generationPassed','safetyChecksPassed','tests','errors'):
        if key in data: item[key]=data[key]
    if 'checks' in data:
        item['checks']=len(data['checks']); item['passedChecks']=sum(bool(c['passed']) for c in data['checks'])
    if 'cases' in data:
        item['cases']=[{k:c[k] for k in ('name','state','passed','message') if k in c} for c in data['cases']]
    item['implementationHashMismatches']=[]
    for file,digest in data.get('sourceHashes',{}).items():
        actual=ROOT/file
        if not actual.exists() or hashlib.sha256(actual.read_bytes()).hexdigest()!=digest:
            item['implementationHashMismatches'].append(file)
    evidence[name]=item
report=dict(completionProven=False,generatedToiletQualified=False,
    updatedAt=datetime.now(timezone.utc).isoformat(),evidence=evidence,
    interpretation=[
        'Green lifecycle, editing or rejection checks do not qualify the generated geometry.',
        'The API and asynchronous browser suites predate the stronger geometric gates; their actual accepted jobs are historical, not newly qualified toilet results.',
        'Right-pane editing uses an explicitly unqualified historical rendering fixture; it does not simulate or claim successful generation.',
        'Sparse/dense sample audits and adaptive whole-triangle bounds have different scopes; both triangulation conventions are retained.',
        'The original source is unchanged. Its four known contacts are spatially separate from the newly detected bowl overlaps.',
    ],remaining=[
        'Captured two-guide networks and basic toilet solves must meet all geometric requirements.',
        'Guide reversal/cyclic reindexing/order and perturbation families require solver coverage.',
        'Toilet occlusion, marquee, group invalid-release and repeated navigation/stability cases need expanded coverage.',
        'Pending-reset, late successful-result/import races, worker timeout and sustained process/memory recovery remain open.',
        'Final implementation/evidence reconciliation and a qualified live generated result remain required.',
    ])
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(completionProven=False,reports=len(evidence),pending=[k for k,v in evidence.items() if v.get('status')=='pending'])))
