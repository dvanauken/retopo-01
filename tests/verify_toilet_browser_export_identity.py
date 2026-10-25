"""Link actual browser downloads to independently audited identical geometry."""
import argparse
import hashlib
import json
from pathlib import Path
import traceback

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
args = parser.parse_args()
if not args.label.replace('-', '').isalnum():
    raise ValueError('Use a plain label')
folder = ROOT / 'tests/toilet-fallback-browser' / args.label
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
mapping = {
    'short-1799': ('tests/toilet-paired-variants/nearby-layouts/short-1799', 'paired1799-integrated', 'paired1799-integrated'),
    'short-small-perturbation': ('tests/toilet-paired-variants/surface-only/short-small-perturbation', 'surface-only', 'surface-only'),
    'two-guides-long-1800': ('tests/toilet-sampled-worker/joint-integrated/two-guides-long-1800', 'joint-integrated', 'joint-integrated'),
    'two-guides-short-1800': ('tests/toilet-sampled-worker/integrated-fallback/two-guides-short-1800', 'integrated-fallback', 'integrated-fallback'),
    'browser-lid-circle': ('tests/toilet-variants/all-diagonal/circle-repeat', 'all-diagonal-generations', 'fresh-new-gate'),
}
records, errors = [], []
try:
    matrix = json.loads((folder / 'result.json').read_text())
    assert matrix['complete'] and matrix['passed']
    for case in matrix['cases']:
        name = case['name']
        relative, surface_label, contact_label = mapping[name]
        actual, reference = folder / name, ROOT / relative
        digest = sha(actual / 'output.obj')
        assert digest == sha(reference / 'output.obj')
        assert (actual / 'browser-export.obj').read_bytes() == (actual / 'output.obj').read_bytes()
        assert json.loads((actual / 'curves.json').read_text())['curves'] == json.loads((reference / 'curves.json').read_text())['curves']
        packet = json.loads((actual / 'mesh.json').read_text())
        expected = json.loads((reference / 'mesh.json').read_text())
        assert packet['vertices'] == expected['vertices'] and packet['faces'] == expected['faces']
        paths = lambda mesh: [{k: p[k] for k in ('vertices', 'closed', 'curve')} for p in mesh['guidePaths']]
        assert paths(packet) == paths(expected)
        audits = {}
        for family, label in (('toilet-fresh-geometry', surface_label), ('toilet-all-diagonal-audit', contact_label)):
            path = ROOT / 'tests' / family / label / 'result.json'
            report = json.loads(path.read_text())
            assert report['complete'] and any(c['outputSha256'] == digest and c['passed'] for c in report['cases'])
            audits[family] = dict(report=str(path.relative_to(ROOT)), sha256=sha(path))
        assert all(packet[key]['passed'] for key in ('surfaceValidation', 'intersectionValidation', 'quality'))
        records.append(dict(name=name, passed=True, outputSha256=digest, referenceExport=str((reference / 'output.obj').relative_to(ROOT)),
                            sameAuthoredCurves=True, sameConnectedPaths=True, samePositionsAndFaces=True, audits=audits))
except Exception:
    errors.append(traceback.format_exc())
report = dict(complete=True, passed=not errors, cases=records, errors=errors,
              scope='Fresh browser downloads are byte-identical to independent qualified exports, with identical source curves and connected path indices. This links existing independent measurements to the same geometry; it does not claim a redundant numerical rerun.')
(folder / 'independent-identity.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=not errors, cases=len(records), errors=errors)))
raise SystemExit(1 if errors else 0)
