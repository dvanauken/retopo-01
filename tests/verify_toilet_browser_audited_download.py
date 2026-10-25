"""Link the native browser download to audits of that exact exported mesh."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--audit-label', required=True)
args = parser.parse_args()
if any(not value.replace('-', '').isalnum() for value in (args.label, args.audit_label)):
    raise ValueError('Use plain labels')
folder = ROOT / 'tests/toilet-fallback-browser' / args.label
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
matrix = json.loads((folder / 'result.json').read_text())
assert matrix['complete'] and matrix['passed'] and matrix['implementationUnchanged']
records = []
for case in matrix['cases']:
    actual = folder / case['name']
    digest = sha(actual / 'browser-export.obj')
    assert digest == sha(actual / 'output.obj') == case['outputSha256']
    audits = {}
    for family in ('toilet-fresh-geometry', 'toilet-all-diagonal-audit'):
        path = ROOT / 'tests' / family / args.audit_label / 'result.json'
        report = json.loads(path.read_text())
        assert report['complete'] and report['passed']
        matching = [c for c in report['cases'] if c['name'] == case['name'] and c['outputSha256'] == digest]
        assert len(matching) == 1 and matching[0]['passed']
        audits[family] = dict(report=str(path.relative_to(ROOT)), sha256=sha(path))
    records.append(dict(name=case['name'], passed=True, outputSha256=digest, audits=audits))
report = dict(complete=True, passed=True, cases=records,
              scope='Native downloaded bytes equal the worker OBJ independently re-read and audited for this browser run. No equality with a different service input or mesh is assumed.')
with (folder / 'independent-download.json').open('x') as output:
    output.write(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
