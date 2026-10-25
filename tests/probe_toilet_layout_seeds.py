"""Fresh alternative layout seeds against captured toilet guides; no publication.

Uses the current production fitter and all acceptance gates without changing
weights, authored curves, source geometry or production's seed selection.
"""
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
import trimesh
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'engine/targets/zbrush/clone'), str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj
parser = argparse.ArgumentParser()
parser.add_argument('--seeds', nargs='+', type=int, default=[2, 3])
parser.add_argument('--cases', nargs='+', default=['two-guides-short-1800', 'two-guides-long-1800', 'bowl-only-1800'])
parser.add_argument('--label', required=True)
args = parser.parse_args()
if not args.label.replace('-', '').isalnum() or any(s < 0 for s in args.seeds):
    raise ValueError('Use a plain label and nonnegative seeds')
OUT = ROOT/'tests/toilet-layout-seeds'/args.label
OUT.mkdir(parents=True, exist_ok=True)
source, triangles = read_obj(ROOT/'assets/models/toilet.obj')
source, triangles = np.asarray(source), np.asarray(triangles)
mesh = trimesh.Trimesh(source, triangles, process=False)
spacing = np.sqrt(mesh.area/1800)
input_path = OUT/'source.json'
input_path.write_text(json.dumps(dict(vertices=source.tolist(), faces=triangles.tolist())))
names = ['curved_quad.py', 'surface_distance.py', 'surface_intersections.py', 'quad_quality.py', 'scripts/quadriflow_mesh.py', 'assets/models/toilet.obj', 'tests/probe_toilet_layout_seeds.py']
hashes = {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
results, errors = [], []

def save(complete):
    (OUT/'result.json').write_text(json.dumps(dict(complete=complete, cases=results, errors=errors,
        sourceHashes=hashes, implementationUnchanged=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items()),
        generationPassed=complete and not errors and all(any(r['name']==name and r['qualified'] for r in results) for name in args.cases),
        scope='Fresh alternative QuadriFlow layouts, current production fitting and all mixed-diagonal contact/full-surface gates. Isolated experiment: no app publication, no relaxed limits, no changed source or authored guides.'), indent=2)+'\n')

try:
    for seed in args.seeds:
        raw = OUT/f'layout-{seed}.json'
        command = [str(cq.find_blender()), '--background', '--threads', '8', '--python', str(ROOT/'scripts/quadriflow_mesh.py'), '--', '--input', str(input_path), '--output', str(raw), '--target', '1800', '--seed', str(seed)]
        print('Building genuine layout seed', seed, flush=True)
        with (OUT/f'layout-{seed}.log').open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180, check=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        packet = json.loads(raw.read_text())
        assert packet['seed']==seed
        faces = np.asarray(packet['faces'], dtype=int)
        assert faces.ndim==2 and faces.shape[1]==4
        edges = cq._edges(faces)
        for name in args.cases:
            positions = np.asarray(packet['vertices'], dtype=float)
            curve_file = ROOT/'tests/toilet-stress'/name/'curves.json'
            curves = [np.asarray(c) for c in json.loads(curve_file.read_text())['curves']]
            paths, pin_rows, target_rows = [], [], []
            for curve in curves:
                path, pins, targets = cq._guide_path(positions, edges, curve, spacing)
                paths.append(path); pin_rows.extend(pins); target_rows.extend(targets)
            pins, targets = np.asarray(pin_rows, dtype=int), np.asarray(target_rows).reshape(-1, 3)
            for pin in set(pin_rows):
                shared = targets[pins==pin]
                assert np.max(np.linalg.norm(shared-shared[0],axis=1))<=spacing*.1, 'Competing guide pins'
            record = dict(name=name, seed=seed, command=command, layoutSha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                          curvesSha256=hashlib.sha256(curve_file.read_bytes()).hexdigest(), attempts=[], qualified=False)
            results.append(record)
            for iteration in range(5):
                start = time.monotonic()
                positions, refinement = cq._refine(mesh, positions, faces, edges, pins, targets, 1800)
                quality = cq.quad_quality(positions, faces, 1800)
                fit = cq._guide_fit(positions, paths, curves)
                contacts = cq.surface_intersections(positions, faces, both_quad_diagonals=True)
                guided = all(p['p95Distance']<=.2*spacing and p['p95TangentAngleDegrees']<=30 for p in fit)
                eligible = quality['passed'] and contacts['passed'] and guided
                surface = cq.validate_surface(source, triangles, positions, faces, 1800, whole_surface=eligible)
                qualified = bool(eligible and surface['passed'])
                record['attempts'].append(dict(iteration=iteration, refinement=refinement, quality=quality,
                    guideFit=fit, contacts=contacts, surface=surface, qualified=qualified, elapsedSeconds=time.monotonic()-start))
                record['qualified'] = qualified
                (OUT/f'{name}-seed-{seed}-pass-{iteration}.json').write_text(json.dumps(dict(vertices=positions.tolist(), faces=faces.tolist())))
                save(False)
                print(name, 'seed', seed, 'pass', iteration, 'quality', quality['passed'], 'contacts', contacts['passed'],
                      'guide', guided, 'surface', surface['passed'], 'qualified', qualified, 'seconds', round(time.monotonic()-start,1), flush=True)
                if qualified:
                    break
except Exception:
    errors.append(traceback.format_exc()); print(errors[-1], flush=True)
finally:
    save(True)
