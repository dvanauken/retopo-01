"""Inventory fresh alternative layouts before numerical guide/surface fitting."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj, topology
from process_ownership import protect_service_tree

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--targets', nargs='+', type=int, default=[150, 600, 1799])
parser.add_argument('--seeds', nargs='+', type=int, default=[3, 4, 5])
args = parser.parse_args()
if not args.label.replace('-', '').isalnum() or any(t < 150 or t > 1800 for t in args.targets) or any(s < 0 or s > 100 for s in args.seeds):
    raise ValueError('Invalid inventory controls')
protect_service_tree()
OUT = ROOT / 'tests/toilet-layout-inventory' / args.label
OUT.mkdir(parents=True, exist_ok=False)
(OUT / 'executed-probe.py').write_bytes(Path(__file__).read_bytes())
source, triangles = read_obj(ROOT / 'assets/models/toilet.obj')
source_stats, _, _ = topology(source, triangles)
input_path = OUT / 'source.json'
input_path.write_text(json.dumps(dict(vertices=source.tolist(), faces=triangles)))
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
files = ['assets/models/toilet.obj', 'curved_quad.py', 'quad_quality.py', 'surface_intersections.py',
         'scripts/quadriflow_mesh.py', 'tests/probe_toilet_layout_inventory.py']
hashes = {path: sha(ROOT / path) for path in files}
cases, errors = [], []
started = time.monotonic()


def save(complete):
    (OUT / 'result.json').write_text(json.dumps(dict(complete=complete, cases=cases, errors=errors, sourceHashes=hashes,
        implementationUnchanged=all(sha(ROOT / p) == h for p, h in hashes.items()), elapsedSeconds=time.monotonic() - started,
        scope='Fresh original-source Blender layouts at requested target counts/seeds. Connectivity, count, shape and all-diagonal contacts are measured before fitting. Passing this preliminary screen does not establish surface/guide accuracy or qualify a final mesh.'), indent=2) + '\n')


try:
    for target in args.targets:
        for seed in args.seeds:
            name = f'target-{target}-seed-{seed}'
            output = OUT / (name + '.json')
            begin = time.monotonic()
            command = [str(cq.find_blender()), '--background', '--threads', '8', '--python', str(ROOT / 'scripts/quadriflow_mesh.py'),
                       '--', '--input', str(input_path), '--output', str(output), '--target', str(target), '--seed', str(seed)]
            with (OUT / (name + '.log')).open('w') as log:
                process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180,
                                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if process.returncode or not output.is_file():
                raise RuntimeError(name + ' did not generate a layout')
            packet = json.loads(output.read_text())
            vertices, faces = np.asarray(packet['vertices']), np.asarray(packet['faces'])
            stats, _, _ = topology(vertices, faces.tolist())
            quality = cq.quad_quality(vertices, faces, target)
            contacts = cq.surface_intersections(vertices, faces, both_quad_diagonals=True)
            connectivity = (stats['boundaryEdges'] == stats['nonmanifoldEdges'] == stats['repeatedIndexFaces'] == 0
                            and stats['faceConnectedComponents'] == source_stats['faceConnectedComponents']
                            and stats['eulerCharacteristic'] == source_stats['eulerCharacteristic'])
            row = dict(name=name, target=target, seed=seed, layoutFile=str(output.relative_to(ROOT)), layoutSha256=sha(output),
                       topology=stats, quality=quality, contacts=contacts, connectivityScreenPassed=connectivity,
                       countScreenPassed=abs(len(faces) - target) <= .15 * target,
                       elapsedSeconds=time.monotonic() - begin, blenderVersion=packet['blenderVersion'])
            cases.append(row)
            print(name, 'faces', len(faces), 'boundary', stats['boundaryEdges'], 'shape', quality['passed'],
                  'contacts', contacts['passed'], 'connectivity', connectivity, flush=True)
            save(False)
except Exception:
    errors.append(traceback.format_exc())
    print(errors[-1], flush=True)
finally:
    save(True)
raise SystemExit(1 if errors else 0)
