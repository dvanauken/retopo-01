"""Locate contact/topology defects before and after fitting retained layouts."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj, topology

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
args = parser.parse_args()
if not args.label.replace('-', '').isalnum():
    raise ValueError('Use a plain label')
OUT = ROOT / 'tests/toilet-layout-failures' / args.label
OUT.mkdir(parents=True, exist_ok=False)
(OUT / 'executed-probe.py').write_bytes(Path(__file__).read_bytes())
source, triangles = read_obj(ROOT / 'assets/models/toilet.obj')
triangles = np.asarray(triangles)
paths = []
for target in (150, 600):
    paths.extend([(f'raw-{target}', target, ROOT / f'tests/toilet-unguided-fallback/coarse-seed2/unguided-{target}/quadri-layout-2.json'),
                  (f'ratio34-{target}', target, ROOT / f'tests/toilet-objective-controls/coarse-ratio34/coarse-{target}/final-candidate.json')])
paths.extend([('raw-1799', 1799, ROOT / 'runs/664ee51b30de4125baacfc8b7708bfc4/quadri-layout-2.json'),
              ('fitted-1799', 1799, ROOT / 'runs/664ee51b30de4125baacfc8b7708bfc4/failed-sampled-guide-candidate.json')])
rows = []
for name, target, path in paths:
    packet = json.loads(path.read_text())
    vertices, faces = np.asarray(packet['vertices']), np.asarray(packet['faces'])
    stats, _, _ = topology(vertices, faces.tolist())
    quality = cq.quad_quality(vertices, faces, target)
    contacts = cq.surface_intersections(vertices, faces, both_quad_diagonals=True)
    surface = cq.validate_surface(source, triangles, vertices, faces, target, whole_surface=False)
    pairs = contacts['nonAdjacentIntersectingFacePairs'] + contacts['adjacentIntersectingFacePairs']
    locations = [dict(faces=[a, b], centers=vertices[faces[[a, b]]].mean(axis=1).tolist(),
                      bounds=[vertices[faces[[a, b]]].reshape(-1, 3).min(axis=0).tolist(),
                              vertices[faces[[a, b]]].reshape(-1, 3).max(axis=0).tolist()]) for a, b in pairs]
    row = dict(name=name, target=target, inputFile=str(path.relative_to(ROOT)), inputSha256=hashlib.sha256(path.read_bytes()).hexdigest(),
               topology=stats, quality=quality, intersections=contacts, sparseSurface=surface, contactLocations=locations)
    rows.append(row)
    print(name, 'unused', stats['unusedVertices'], 'Euler', stats['eulerCharacteristic'],
          'shape', quality['passed'], 'contactPairs', len(pairs), 'surfaceChecks', surface['checks'], flush=True)
    (OUT / (name + '.json')).write_bytes(path.read_bytes())
    (OUT / 'result.json').write_text(json.dumps(dict(complete=False, cases=rows), indent=2) + '\n')
(OUT / 'result.json').write_text(json.dumps(dict(complete=True, cases=rows,
    sourceHashes={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in ('assets/models/toilet.obj','curved_quad.py','surface_intersections.py','surface_distance.py','quad_quality.py','tests/inspect_toilet_layout_failures.py')},
    scope='Retained genuine layouts and fitted failures measured before/after fitting. Topology and all-diagonal contacts are checked; source-surface evaluation here is explicitly sparse. No candidate is qualified or exported by this diagnostic.'), indent=2) + '\n')
