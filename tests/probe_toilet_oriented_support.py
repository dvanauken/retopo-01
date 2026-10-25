"""Fit experiment: prevent thin surfaces from binding to the opposite side.

Uses retained layout geometry to compare fitting strategies; this is not fresh
production evidence. The bounded centroid-neighbor search is experimental.
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
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'engine/targets/zbrush/clone'), str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
from measure_geometry import read_obj
from surface_intersections import measure as intersections


def oriented_closest(mesh, points, normals, neighbor_count=96):
    tree = cKDTree(mesh.triangles_center)
    nearest, distances, ids = [], [], []
    for start in range(0, len(points), 512):
        p, n = points[start:start+512], normals[start:start+512]
        _, candidates = tree.query(p, k=min(neighbor_count, len(mesh.faces)))
        triangles = mesh.triangles[candidates]
        q = trimesh.triangles.closest_point(triangles.reshape(-1, 3, 3), np.repeat(p, candidates.shape[1], axis=0)).reshape(len(p), -1, 3)
        ds = np.linalg.norm(q-p[:, None, :], axis=2)
        compatible = (mesh.face_normals[candidates]*n[:, None, :]).sum(axis=2) > .15
        compatible[np.linalg.norm(n, axis=1) < 1e-10] = True
        selected = np.where(compatible, ds, np.inf).argmin(axis=1)
        rows = np.arange(len(p)); best, distance, owners = q[rows, selected], ds[rows, selected], candidates[rows, selected]
        missing = ~compatible.any(axis=1)
        if np.any(missing):
            if candidates.shape[1] == len(mesh.faces):
                raise ValueError('Experimental oriented search has no matching candidate')
            best[missing], distance[missing], owners[missing] = oriented_closest(mesh, p[missing], n[missing], neighbor_count*4)
        nearest.extend(best); distances.extend(distance); ids.extend(owners)
    return np.asarray(nearest), np.asarray(distances), np.asarray(ids)


OUT = ROOT/'runs/oriented-support-probe'
OUT.mkdir(exist_ok=True)
sv, sf = read_obj(ROOT/'assets/models/toilet.obj'); sf = np.asarray(sf)
source = trimesh.Trimesh(sv, sf, process=False)
source_points = np.r_[source.vertices, source.triangles_center, source.vertices[source.edges_unique].mean(axis=1)]
source_normals = np.r_[source.vertex_normals, source.face_normals, source.vertex_normals[source.edges_unique].mean(axis=1)]
source_normals /= np.maximum(1e-15, np.linalg.norm(source_normals, axis=1))[:, None]
definition = inspect.getsource(cq._refine)
definition = definition.replace('trimesh.proximity.closest_point(source_mesh, positions)', 'oriented_closest(source_mesh, positions, reference_normals)')
definition = definition.replace('trimesh.proximity.closest_point(out_surface, source_mesh.vertices)', 'oriented_closest(out_surface, source_points, source_normals)')
definition = definition.replace('support_target = source_mesh.vertices[selected]', 'support_target = source_points[selected]')
cases = json.loads((ROOT/'tests/toilet-stress/result.json').read_text())['cases']
records = []
for name in ('unguided-1800', 'two-guides-short-1800', 'two-guides-long-1800'):
    case = next(c for c in cases if c['name'] == name)
    raw = json.loads((ROOT/'runs'/case['job']/'quadri-layout-0.json').read_text())
    p, faces = np.asarray(raw['vertices']), np.asarray(raw['faces'])
    reference_normals = trimesh.Trimesh(p, np.r_[faces[:, [0, 1, 2]], faces[:, [0, 2, 3]]], process=False).vertex_normals
    namespace = dict(vars(cq), oriented_closest=oriented_closest, reference_normals=reference_normals, source_points=source_points, source_normals=source_normals)
    exec(definition, namespace)
    curves = [np.asarray(c) for c in json.loads((ROOT/'tests/toilet-stress'/name/'curves.json').read_text())['curves']]
    spacing = np.sqrt(source.area / 1800); edges = cq._edges(faces); paths, pins, targets = [], [], []
    for c in curves:
        path, pi, ta = cq._guide_path(p, edges, c, spacing); paths.append(path); pins.extend(pi); targets.extend(ta)
    started = time.monotonic()
    for iteration in range(5):
        p, ref = namespace['_refine'](source, p, faces, edges, np.asarray(pins, dtype=int), np.asarray(targets).reshape(-1, 3), 1800)
        quality = cq.quad_quality(p, faces, 1800); surface = cq.validate_surface(sv, sf, p, faces, 1800)
        fit = cq._guide_fit(p, paths, curves); crossing = intersections(p, faces)
        record = dict(name=name, iteration=iteration, refinement=ref, quality=quality, surface=surface, fit=fit,
                      intersections=crossing, elapsedSeconds=time.monotonic()-started)
        records.append(record)
        print(name, iteration, 'shape', quality['passed'], 'surface', surface['passed'],
              'fit', [(round(x['p95Distance'], 5), round(x['p95TangentAngleDegrees'], 1)) for x in fit],
              'crossings', len(crossing['nonAdjacentIntersectingFacePairs']), 'seconds', round(record['elapsedSeconds'], 1), flush=True)
        (OUT/f'{name}-{iteration}.json').write_text(json.dumps(dict(vertices=p.tolist(), faces=faces.tolist(), **record)))
        (OUT/'result.json').write_text(json.dumps(dict(complete=False, cases=records), indent=2)+'\n')
        if quality['passed'] and surface['passed'] and crossing['passed'] and all(x['p95Distance'] <= .2*spacing and x['p95TangentAngleDegrees'] <= 30 for x in fit):
            break
(OUT/'result.json').write_text(json.dumps(dict(complete=True, cases=records), indent=2)+'\n')
