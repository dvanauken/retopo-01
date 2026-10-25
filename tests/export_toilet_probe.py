"""Export a passing isolated experiment for the ordinary independent OBJ audit.

This does not create a worker result, admit a job, or publish anything to the app.
The matrix explicitly identifies the experiment as the producer.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'engine/targets/zbrush/clone'), str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj

parser = argparse.ArgumentParser()
parser.add_argument('--probe', type=Path, required=True)
parser.add_argument('--producer-kind', choices=['isolated-tangent-probe', 'isolated-sampled-path-probe', 'isolated-both-diagonal-support-probe'], default='isolated-tangent-probe')
args = parser.parse_args()
probe = json.loads(args.probe.read_text())
folder = args.probe.parent
assert probe['complete'] and not probe['errors'] and probe['implementationUnchanged']
for file, digest in probe['sourceHashes'].items():
    assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest() == digest, file
layout = json.loads((folder/'layout.json').read_text())
source, triangles = read_obj(ROOT/'assets/models/toilet.obj')
spacing = np.sqrt(trimesh.Trimesh(source, triangles, process=False).area/1800)
edges = cq._edges(np.asarray(layout['faces']))
cases = []
for case in probe['cases']:
    if not case['qualified']:
        continue
    attempt = next(a for a in case['attempts'] if a['qualified'])
    candidate = folder/f"{case['name']}-{attempt['iteration']}.json"
    mesh = json.loads(candidate.read_text())
    output = folder/case['name']
    output.mkdir(exist_ok=True)
    curve_file = ROOT/'tests/toilet-stress'/case['name']/'curves.json'
    assert hashlib.sha256(curve_file.read_bytes()).hexdigest() == case['curvesSha256']
    curves = json.loads(curve_file.read_text())['curves']
    paths = [cq._guide_path(np.asarray(layout['vertices']), edges, np.asarray(curve), spacing)[0] for curve in curves]
    mesh['guidePaths'] = paths
    obj = '\n'.join(['# ' + args.producer_kind + '; no production worker job'] +
                    ['v ' + ' '.join(format(x, '.17g') for x in vertex) for vertex in mesh['vertices']] +
                    ['f ' + ' '.join(str(i+1) for i in face) for face in mesh['faces']]) + '\n'
    (output/'output.obj').write_text(obj, newline='\n')
    (output/'mesh.json').write_text(json.dumps(mesh) + '\n')
    (output/'curves.json').write_bytes(curve_file.read_bytes())
    (output/'settings.json').write_text(json.dumps(dict(meshId='toilet', target=1800)) + '\n')
    report = dict(producerKind=args.producer_kind, outputSha256=hashlib.sha256((output/'output.obj').read_bytes()).hexdigest(),
                  probeFile=str(args.probe), probeSha256=hashlib.sha256(args.probe.read_bytes()).hexdigest(),
                  candidateSha256=hashlib.sha256(candidate.read_bytes()).hexdigest(), attempt=attempt)
    (output/'report.json').write_text(json.dumps(report, indent=2) + '\n')
    cases.append(dict(name=case['name'], state='complete', job=None, producerKind=args.producer_kind))
assert cases, 'No passing experimental candidate to export'
(folder/'export-matrix.json').write_text(json.dumps(dict(cases=cases, productionResult=False,
    scope='Completed isolated experiment, exported for independent validation. No service job or production result.'), indent=2) + '\n')
print(json.dumps(dict(exports=len(cases), matrix=str(folder/'export-matrix.json'))), flush=True)
