"""Reassess retained toilet exports with stronger whole-surface/contact checks.

This audits historical outputs. It is not a new solve and does not overwrite the
historical solver reports. A failed mesh stays a failed mesh in this report.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
from pathlib import Path
import hashlib
import json
import sys
import time
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj
from surface_distance import measure as distance
from surface_intersections import measure as contacts

source_path = ROOT/'assets/models/toilet.obj'
v, f = read_obj(source_path)
source = trimesh.Trimesh(v, f, process=False)
out = ROOT/'tests/toilet-acceptance-audit'
out.mkdir(exist_ok=True)
cases, seen = [], set()
started = time.monotonic()
for old in json.loads((ROOT/'tests/toilet-stress/result.json').read_text())['cases']:
    if old['state'] != 'complete':
        continue
    path = ROOT/'tests/toilet-stress'/old['name']/'output.obj'
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest in seen:
        continue
    seen.add(digest)
    v, f = read_obj(path); f = np.asarray(f)
    threshold = .5 * np.sqrt(source.area/old['target'])
    t = time.monotonic()
    crossing = contacts(v, f)
    diagonals = {}
    for name, a, b in (('02', [0,1,2], [0,2,3]), ('13', [0,1,3], [1,2,3])):
        mesh = trimesh.Trimesh(v, np.r_[f[:,a], f[:,b]], process=False)
        diagonals[name] = distance(source, mesh, threshold)
    case = dict(name=old['name'], outputSha256=digest, contacts=crossing, surfaceDiagonals=diagonals,
                passed=crossing['passed'] and all(d['passed'] for d in diagonals.values()), elapsedSeconds=time.monotonic()-t)
    cases.append(case)
    print(old['name'], 'contacts', crossing['passed'], 'diagonals', {k:d['passed'] for k,d in diagonals.items()}, 'seconds', round(case['elapsedSeconds'],1), flush=True)
    (out/'result.json').write_text(json.dumps(dict(complete=False, passed=False, cases=cases), indent=2)+'\n')
report = dict(complete=True, passed=all(c['passed'] for c in cases), cases=cases, elapsedSeconds=time.monotonic()-started,
              sourceHashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                            ('assets/models/toilet.obj', 'surface_distance.py', 'surface_intersections.py', 'tests/verify_toilet_acceptance.py')},
              scope='Historical exported quad meshes; both quad diagonals independently require whole-triangle distance bounds. All polygon pairs include adjacent contacts except legitimate shared boundary. No fitting is performed.')
(out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
raise SystemExit(0 if report['passed'] else 1)
