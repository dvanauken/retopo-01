"""Retain evidence that cancellation interrupted a distinct second layout."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests/toilet-fallback-cancel/nearby-layouts'
report = json.loads((OUT / 'result.json').read_text())
assert report['complete'] and report['passed'] and report['requestedStage'] == 'nearby'
job = ROOT / 'runs' / report['job']['id']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((job / 'nearby-layout-attempts.json').read_text())
assert manifest['requestedTarget'] == 1799
assert [(a['layoutTarget'], a['accepted']) for a in manifest['attempts']] == [(1799, False)]
old = job / 'sampled-layout-1799/quadri-layout-2.json'
new = job / 'quadri-layout-2.json'
old_data, new_data = json.loads(old.read_text()), json.loads(new.read_text())
assert sha(old) != sha(new)
assert len(new_data['faces']) == 1845
assert new_data['faces'] != old_data['faces'] or new_data['vertices'] != old_data['vertices']
files = {}
for source, name in ((old, 'first-rejected-layout.json'), (new, 'second-interrupted-layout.json')):
    destination = OUT / name
    shutil.copyfile(source, destination)
    assert sha(destination) == sha(source)
    files[name] = sha(destination)
proof = dict(complete=True, passed=True, generationPassed=False, job=report['job']['id'],
             requestedTarget=1799, firstFaces=len(old_data['faces']), secondFaces=len(new_data['faces']),
             copiedFiles=files, sourceHashes={'tests/capture_toilet_cancelled_retry.py': sha(Path(__file__))},
             cancellationReportSha256=sha(OUT / 'result.json'),
             scope='The first layout is archived as rejected and a distinct1845quad second layout exists when sampled-stage cancellation occurs. This distinguishes the retry from a stale first-attempt stage string. Both are raw experimental artifacts; no finished mesh is qualified or published by the cancelled job.')
(OUT / 'second-layout-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps(dict(passed=True, firstFaces=proof['firstFaces'], secondFaces=proof['secondFaces'])))
