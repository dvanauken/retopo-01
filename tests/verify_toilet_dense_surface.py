"""Dense, independent proximity audit of actual accepted toilet exports.

Includes every vertex, triangle centroid and unique triangle-edge midpoint,
plus deterministic interior samples. This is still sampling, not a Hausdorff
certificate. Results include coordinates of the worst discrepancies.
"""
import os
for variable in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj
from measure_polygon_geometry import triangulate

OUT = ROOT / 'tests/toilet-dense-surface'
OUT.mkdir(exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument('--triangulation', choices=['ear', 'fan'], default='ear')
args = parser.parse_args()
report_path = OUT / ('fan-result.json' if args.triangulation == 'fan' else 'result.json')


def samples(mesh):
    triangles = mesh.triangles
    rng = np.random.default_rng(20261025)
    bary = rng.dirichlet([1, 1, 1], (len(triangles), 2))
    interior = np.einsum('tij,tkj->tki', triangles.transpose(0, 2, 1), bary).reshape(-1, 3)
    points = np.r_[mesh.vertices, mesh.triangles_center, mesh.vertices[mesh.edges_unique].mean(axis=1), interior]
    return points


def distances(points, mesh, tolerance):
    errors, nearest = [], []
    for start in range(0, len(points), 2048):
        q, distance, _ = trimesh.proximity.closest_point(mesh, points[start:start + 2048])
        errors.extend(distance.tolist()); nearest.extend(q.tolist())
    errors = np.asarray(errors)
    worst = np.argsort(errors)[-10:][::-1]
    return dict(samples=len(points), maximum=float(errors.max()), p95=float(np.percentile(errors, 95)),
                overTolerance=int(np.count_nonzero(errors > tolerance)),
                worst=[dict(sampleIndex=int(i), point=points[i].tolist(), nearest=nearest[i], distance=float(errors[i])) for i in worst])


source_path = ROOT / 'assets/models/toilet.obj'
sv, sf = read_obj(source_path)
source = trimesh.Trimesh(sv, sf, process=False)
source_samples = samples(source)
cases = json.loads((ROOT / 'tests/toilet-stress/result.json').read_text())['cases']
records, seen = [], set()
started = time.monotonic()
for case in cases:
    if case['state'] != 'complete':
        continue
    obj = ROOT / 'tests/toilet-stress' / case['name'] / 'output.obj'
    digest = hashlib.sha256(obj.read_bytes()).hexdigest()
    if digest in seen:
        continue
    seen.add(digest)
    vertices, faces = read_obj(obj)
    tri = triangulate(vertices, faces) if args.triangulation == 'ear' else np.asarray([[f[0], f[i], f[i+1]] for f in faces for i in range(1, len(f)-1)])
    mesh = trimesh.Trimesh(vertices, tri, process=False)
    tolerance = float(.5 * np.sqrt(source.area / case['target']))
    forward = distances(source_samples, mesh, tolerance)
    backward = distances(samples(mesh), source, tolerance)
    record = dict(name=case['name'], target=case['target'], outputSha256=digest,
                  tolerance=float(tolerance), sourceToOutput=forward, outputToSource=backward,
                  passed=max(forward['maximum'], backward['maximum']) <= tolerance)
    records.append(record)
    print(json.dumps(dict(name=record['name'], passed=record['passed'], sourceMax=forward['maximum'], outputMax=backward['maximum'], tolerance=tolerance)), flush=True)
    report_path.write_text(json.dumps(dict(passed=all(c['passed'] for c in records), complete=False, cases=records), indent=2) + '\n')
report_path.write_text(json.dumps(dict(passed=all(c['passed'] for c in records), complete=True, cases=records, triangulation=args.triangulation,
    elapsedSeconds=time.monotonic() - started, sourceSha256=hashlib.sha256(source_path.read_bytes()).hexdigest(),
    verifierSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    scope='All vertices, all triangulated-face centroids, all unique edge midpoints and two deterministic interior samples per triangle in both directions. Exact nearest-triangle distance at each sample; not a continuous surface certificate.'), indent=2) + '\n')
sys.exit(0 if all(c['passed'] for c in records) else 1)
