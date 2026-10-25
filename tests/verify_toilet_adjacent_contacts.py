"""Audit the shared-vertex face pairs excluded by the production screen.

Shrinking triangles slightly into their interiors removes legitimate shared
edges/vertices. A detected intersection is still an intersection of the original
triangles. Non-detection is not a complete contact certificate (the removed strip
can hide very small intersections). This is supplemental diagnostic evidence.
"""
from pathlib import Path
import json
import sys
import hashlib
import numpy as np
from rtree.index import Index, Property

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj
from surface_intersections import triangle_intersects


def shrink(triangle):
    return triangle.mean(axis=0) + (triangle-triangle.mean(axis=0)) * .9999


def overlap(a, b):
    return triangle_intersects(shrink(a), shrink(b), eps=1e-12)


# Both controls share the same edge. Only the folded pair has overlapping area.
a = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
assert not overlap(a, np.array([[1, 0, 0], [0, 0, 0], [0, -1, 0]], dtype=float))
assert overlap(a, np.array([[1, 0, 0], [0, 0, 0], [.2, .3, 0]], dtype=float))
assert overlap(a, np.array([[0, 0, 0], [.8, .1, 0], [.1, .8, 0]], dtype=float))

records, seen = [], set()
for case in json.loads((ROOT/'tests/toilet-stress/result.json').read_text())['cases']:
    if case['state'] != 'complete':
        continue
    path = ROOT/'tests/toilet-stress'/case['name']/'output.obj'
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest in seen:
        continue
    seen.add(digest)
    v, faces = read_obj(path)
    polygons = [v[f] for f in faces]
    bounds = [np.r_[p.min(axis=0), p.max(axis=0)] for p in polygons]
    tree = Index(((i,b,None) for i,b in enumerate(bounds)), properties=Property(dimension=3))
    vertices = [set(f) for f in faces]
    pairs, tested = [], 0
    for i, bound in enumerate(bounds):
        p = polygons[i]
        for j in tree.intersection(bound):
            if j <= i or not vertices[i].intersection(vertices[j]):
                continue
            tested += 1; q = polygons[j]
            if any(overlap(p[[0,a,a+1]], q[[0,b,b+1]]) for a in range(1,len(p)-1) for b in range(1,len(q)-1)):
                pairs.append([i,j])
    tree.close()
    record = dict(name=case['name'], outputSha256=digest, adjacentPairsTested=tested, intersectingInteriorPairs=pairs, passed=not pairs)
    records.append(record)
    print(case['name'], 'tested', tested, 'interior intersections', len(pairs), flush=True)
out = ROOT/'tests/toilet-adjacent-contacts'
out.mkdir(exist_ok=True)
(out/'result.json').write_text(json.dumps(dict(passed=all(c['passed'] for c in records), detectorControlsPassed=True,
    cases=records, verifierSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    scope='Supplemental shared-vertex polygon-pair screen using triangle interiors shrunk by 0.01%, fan triangulation and 1e-12 tolerance. Reports positive intersection evidence; it does not prove absence of crossings in the removed boundary strip.'), indent=2)+'\n')
sys.exit(0 if all(c['passed'] for c in records) else 1)
