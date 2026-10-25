"""Experiment with denser source support on retained fresh QuadriFlow layouts.

This is a fitting experiment, not a fresh end-to-end solve or product fallback.
It does not alter source assets or acceptance limits. Successful experiments must
be integrated and verified through real fresh workers before being claimed fixed.
"""
import os
for variable in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
from pathlib import Path
import inspect
import json
import sys
import time
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'engine/targets/zbrush/clone'), str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj
from surface_intersections import measure as intersections

OUT = ROOT / 'runs/dense-support-probe'
OUT.mkdir(exist_ok=True)
source_v, source_f = read_obj(ROOT/'assets/models/toilet.obj')
source_f = np.asarray(source_f)
source = trimesh.Trimesh(source_v, source_f, process=False)
surface_samples = np.r_[source.vertices, source.triangles_center, source.vertices[source.edges_unique].mean(axis=1)]
spacing = np.sqrt(source.area / 1800)
definition = inspect.getsource(cq._refine)
definition = definition.replace("out_tri = np.r_[faces[:, [0, 1, 2]], faces[:, [0, 2, 3]]]", "out_tri = triangulate(positions, faces.tolist())")
definition = definition.replace('source_mesh.vertices', 'surface_samples')
namespace = dict(vars(cq), surface_samples=surface_samples)
exec(definition, namespace)
cases = json.loads((ROOT/'tests/toilet-stress/result.json').read_text())['cases']
records = []
for name in ('unguided-1800', 'two-guides-short-1800', 'two-guides-long-1800'):
    case = next(c for c in cases if c['name'] == name)
    raw = json.loads((ROOT/'runs'/case['job']/'quadri-layout-0.json').read_text())
    positions, faces = np.asarray(raw['vertices']), np.asarray(raw['faces'])
    curves = [np.asarray(c) for c in json.loads((ROOT/'tests/toilet-stress'/name/'curves.json').read_text())['curves']]
    edges = cq._edges(faces); paths, pin_rows, target_rows = [], [], []
    for curve in curves:
        path, pins, targets = cq._guide_path(positions, edges, curve, spacing)
        paths.append(path); pin_rows.extend(pins); target_rows.extend(targets)
    started = time.monotonic()
    for iteration in range(5):
        positions, refinement = namespace['_refine'](source, positions, faces, edges, np.asarray(pin_rows, dtype=int), np.asarray(target_rows).reshape(-1, 3), 1800)
        quality = cq.quad_quality(positions, faces, 1800)
        surface = cq.validate_surface(source_v, source_f, positions, faces, 1800)
        fit = cq._guide_fit(positions, paths, curves)
        crossing = intersections(positions, faces)
        record = dict(name=name, iteration=iteration, refinement=refinement, quality=quality, surface=surface,
                      fit=fit, intersections=crossing, elapsedSeconds=time.monotonic()-started)
        records.append(record)
        print(name, iteration, 'shape', quality['passed'], 'surface', surface['passed'],
              'fit', [(round(p['p95Distance'], 5), round(p['p95TangentAngleDegrees'], 1)) for p in fit],
              'crossings', len(crossing['nonAdjacentIntersectingFacePairs']), 'seconds', round(record['elapsedSeconds'], 1), flush=True)
        (OUT/f'{name}-{iteration}.json').write_text(json.dumps(dict(vertices=positions.tolist(), faces=faces.tolist(), **record)))
        if quality['passed'] and surface['passed'] and crossing['passed'] and all(p['p95Distance'] <= .2*spacing and p['p95TangentAngleDegrees'] <= 30 for p in fit):
            break
(OUT/'result.json').write_text(json.dumps(dict(sourceSupportSamples=len(surface_samples), cases=records), indent=2)+'\n')
