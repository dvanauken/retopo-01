"""Test restoring the handle between two equal boundary loops of a raw layout.

This is an isolated connectivity experiment. Capping the loops would change
Euler characteristic; a quad bridge can restore closure while preserving it.
No result is accepted without the ordinary complete geometric checks.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
import surface_guide_repair as repair
from retopo import read_obj, write_obj
from measure_geometry import topology

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
args = parser.parse_args()
if not args.label.replace('-', '').isalnum():
    raise ValueError('Use a plain label')
OUT = ROOT / 'tests/toilet-boundary-bridge' / args.label
OUT.mkdir(parents=True, exist_ok=False)
(OUT / 'executed-probe.py').write_bytes(Path(__file__).read_bytes())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
hashes = {p: sha(ROOT / p) for p in ('assets/models/toilet.obj','curved_quad.py','surface_guide_refine.py','surface_guide_repair.py',
                                   'surface_intersections.py','surface_distance.py','quad_quality.py','tests/probe_toilet_boundary_bridge.py')}
definition = (ROOT / 'surface_guide_refine.py').read_text()
assert definition.count('np.maximum(ratio - 3.5, 0) * 10') == 1
definition = definition.replace('np.maximum(ratio - 3.5, 0) * 10','np.maximum(ratio - 3.4, 0) * 10')
module_path = OUT / 'executed-fitter.py'
module_path.write_text(definition, newline='\n')
spec = importlib.util.spec_from_file_location('boundary_bridge_fitter', module_path)
fitter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fitter
spec.loader.exec_module(fitter)
repair.fitter = fitter
vertices, triangles = read_obj(ROOT / 'assets/models/toilet.obj')
source = trimesh.Trimesh(vertices, triangles, process=False)
source_topology, _, _ = topology(np.asarray(vertices), np.asarray(triangles).tolist())
layout = ROOT / 'tests/toilet-unguided-fallback/coarse-seed2/unguided-150/quadri-layout-2.json'
raw = json.loads(layout.read_text())
(OUT / 'layout.json').write_bytes(layout.read_bytes())
positions, original_faces = np.asarray(raw['vertices']), np.asarray(raw['faces'])
incidence = defaultdict(list)
for face in original_faces:
    for a, b in zip(face, np.roll(face, -1)):
        incidence[tuple(sorted((int(a),int(b))))].append((int(a),int(b)))
boundary = [items[0] for items in incidence.values() if len(items) == 1]
outgoing = dict(boundary)
assert len(outgoing) == len(boundary) and len({b for a,b in boundary}) == len(boundary)
pending = set(outgoing)
loops = []
while pending:
    first = min(pending)
    loop, current = [], first
    while current not in loop:
        loop.append(current)
        pending.remove(current)
        current = outgoing[current]
    assert current == first
    loops.append(loop)
assert len(loops) == 2 and len(loops[0]) == len(loops[1])
loop_data = [dict(vertices=loop, coordinates=positions[loop].tolist(), center=positions[loop].mean(axis=0).tolist()) for loop in loops]
cases, errors = [], []
started = time.monotonic()


def save(complete):
    (OUT / 'result.json').write_text(json.dumps(dict(complete=complete, productionResult=False, cases=cases, errors=errors,
        boundaryLoops=loop_data, layoutSha256=sha(layout), sourceHashes=hashes,
        implementationUnchanged=all(sha(ROOT / p) == h for p,h in hashes.items()), elapsedSeconds=time.monotonic()-started,
        scope='All cyclic correspondences between the two directed equal-length boundary loops of this retained raw layout. Each bridge reverses existing boundary edge directions and preserves Euler characteristic. Fitting aims for edge ratio3.4 but acceptance remains3.5 and every ordinary gate applies. No production connectivity change.'), indent=2) + '\n')


try:
    a, b = loops
    n = len(a)
    for shift in range(n):
        name = f'bridge-{shift}'
        folder = OUT / name
        folder.mkdir()
        additions = [[a[(i+1)%n], a[i], b[(shift-i)%n], b[(shift-i-1)%n]] for i in range(n)]
        faces = np.r_[original_faces, np.asarray(additions)]
        p = positions.copy()
        stats, _, _ = topology(p, faces.tolist())
        assert stats['boundaryEdges'] == stats['nonmanifoldEdges'] == 0
        assert stats['eulerCharacteristic'] == source_topology['eulerCharacteristic']
        (folder / 'input.json').write_text(json.dumps(dict(vertices=p.tolist(), faces=faces.tolist())))
        (folder / 'curves.json').write_text(json.dumps(dict(coordinateFrame='source',curves=[])))
        (folder / 'settings.json').write_text(json.dumps(dict(meshId='toilet',target=150)))
        edges = cq._edges(faces)
        guides = fitter.prepare(p, edges, [], np.sqrt(source.area/150))
        case = dict(name=name,target=150,job=None,state='running',producerKind='isolated-boundary-bridge',addedFaces=additions,
                    initialTopology=stats,attempts=[])
        cases.append(case)

        def record(assessment, **details):
            case['attempts'].append(dict(assessment,**details))
            print(name, details.get('phase'), 'qualified',assessment['qualified'],'shape',assessment['quality']['passed'],
                  'contacts',assessment['intersections']['passed'],'surface',assessment['surface']['passed'],flush=True)
            save(False)

        for iteration in range(5):
            p, refinement = fitter.refine(source,p,faces,edges,guides,150)
            current = repair._assess(source,p,faces,guides,150)
            (folder / f'candidate-{iteration}.json').write_text(json.dumps(dict(vertices=p.tolist(),faces=faces.tolist())))
            record(current,phase='global',iteration=iteration,refinement=refinement)
            if current['qualified']:
                break
        if current['eligibleForRepair'] and not current['qualified']:
            p,current=repair._repair(source,p,faces,edges,guides,150,current,record,folder)
        case['state']='complete' if current['qualified'] else 'failed'
        (folder / 'final-candidate.json').write_text(json.dumps(dict(vertices=p.tolist(),faces=faces.tolist())))
        if current['qualified']:
            write_obj(folder/'output.obj',p,faces.tolist())
            case['outputSha256']=sha(folder/'output.obj')
            (folder/'mesh.json').write_text(json.dumps(dict(vertices=p.tolist(),faces=faces.tolist(),guidePaths=[])))
            (folder/'report.json').write_text(json.dumps(dict(producerKind=case['producerKind'],outputSha256=case['outputSha256'],
                 sourceSha256=hashes['assets/models/toilet.obj'],assessment=current)))
        save(False)
except Exception:
    errors.append(traceback.format_exc())
    if cases and cases[-1]['state']=='running':cases[-1]['state']='probe-error'
    print(errors[-1],flush=True)
finally:
    save(True)
raise SystemExit(1 if errors else 0)
