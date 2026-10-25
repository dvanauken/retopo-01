"""Retain the actual worker's separate layout attempts alongside its result."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--matrix', type=Path, required=True)
args = parser.parse_args()
matrix = args.matrix.resolve()
matrix.relative_to(ROOT / 'tests')
data = json.loads(matrix.read_text())
assert data['complete']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
records = []
for case in data['cases']:
    job_id = case['job']
    assert len(job_id) == 32 and all(c in '0123456789abcdef' for c in job_id)
    source = ROOT / 'runs' / job_id
    destination = matrix.parent / case['name']
    destination.resolve().relative_to(matrix.parent)
    history_file = source / 'nearby-layout-attempts.json'
    packet = json.loads(history_file.read_text())
    settings = json.loads((destination / 'settings.json').read_text())
    assert packet['requestedTarget'] == settings['target']
    assert case.get('target', settings['target']) == settings['target']
    shutil.copyfile(history_file, destination / history_file.name)
    files = {}
    for attempt in packet['attempts']:
        archive = source / attempt['artifactDirectory']
        archive.resolve().relative_to(source)
        copied = destination / archive.name
        shutil.copytree(archive, copied)
        for path in archive.rglob('*'):
            if path.is_file():
                relative = path.relative_to(source)
                assert sha(path) == sha(destination / relative)
                files[str(relative)] = sha(path)
    records.append(dict(name=case['name'], job=job_id, attempts=packet['attempts'], copiedFiles=files))
report = dict(complete=True, passed=True, cases=records,
              scope='Byte-identical copies of the finished worker layout archives and attempt manifest. Includes failed starting layouts and the accepted retry. This is provenance capture, not a geometry qualification test.')
(matrix.parent / 'layout-artifacts.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, cases=len(records), files=sum(len(r['copiedFiles']) for r in records))))
