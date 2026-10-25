"""Independent Blender BVH screen for non-adjacent intersecting polygons.

Run with Blender --background --python this_file -- <output.json> <OBJ paths>.
This excludes shared-vertex pairs and is not a complete intersection certificate.
"""
from pathlib import Path
import json
import sys
import numpy as np
from mathutils.bvhtree import BVHTree


def triangle_intersects(a, b, eps=1e-9):
    na, nb = np.cross(a[1] - a[0], a[2] - a[0]), np.cross(b[1] - b[0], b[2] - b[0])
    na /= np.linalg.norm(na); nb /= np.linalg.norm(nb)
    da, db = (a - b[0]) @ nb, (b - a[0]) @ na
    if any(np.all(d > eps) or np.all(d < -eps) for d in (da, db)):
        return False
    def inside(p, t, normal):
        return all(np.dot(np.cross(t[(i + 1) % 3] - t[i], p - t[i]), normal) >= -eps for i in range(3))
    for first, other, normal in ((a, b, nb), (b, a, na)):
        for i in range(3):
            p, q = first[i], first[(i + 1) % 3]
            start, change = np.dot(p - other[0], normal), np.dot(q - p, normal)
            if abs(start) <= eps and inside(p, other, normal):
                return True
            if abs(change) > eps:
                t = -start / change
                if -eps <= t <= 1 + eps and inside(p + t * (q - p), other, normal):
                    return True
    if np.linalg.norm(np.cross(na, nb)) < eps and np.max(np.abs(da)) < eps:
        axis = np.argmax(np.abs(na)); aa, bb = np.delete(a, axis, axis=1), np.delete(b, axis, axis=1)
        def orient(p, q, r):
            x, y = q - p, r - p
            return x[0] * y[1] - x[1] * y[0]
        for i in range(3):
            for j in range(3):
                p, q, r, s = aa[i], aa[(i + 1) % 3], bb[j], bb[(j + 1) % 3]
                if orient(p, q, r) * orient(p, q, s) < -eps and orient(r, s, p) * orient(r, s, q) < -eps:
                    return True
    return False


def overlaps(vertices, faces):
    tree = BVHTree.FromPolygons(vertices, faces, all_triangles=False, epsilon=0.0)
    candidates = sorted({(a, b) for a, b in tree.overlap(tree)
                         if a < b and not set(faces[a]).intersection(faces[b])})
    v = np.asarray(vertices, dtype=float)
    def triangles(face):
        return [v[[face[0], face[i], face[i + 1]]] for i in range(1, len(face) - 1)]
    return [pair for pair in candidates if any(triangle_intersects(a, b) for a in triangles(faces[pair[0]]) for b in triangles(faces[pair[1]]))]


crossing = [[-1, -1, 0], [1, -1, 0], [0, 1, 0], [0, 0, -1], [0, 0, 1], [.5, 0, 0]]
faces = [[0, 1, 2], [3, 4, 5]]
assert overlaps(crossing, faces) == [(0, 1)], 'Detector must find known crossing triangles'
separated = crossing[:3] + [[x + 3, y, z] for x, y, z in crossing[3:]]
assert not overlaps(separated, faces), 'Detector must reject disjoint triangles'
box_only = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [.8, .8, -1], [.8, .8, 1], [1.5, 1.5, 0]]
assert not overlaps(box_only, faces), 'Overlapping bounding boxes alone are not an intersection'
args = sys.argv[sys.argv.index('--') + 1:]
results = []
for filename in args[1:]:
    vertices, polygons = [], []
    for line in Path(filename).read_text().splitlines():
        fields = line.split()
        if fields and fields[0] == 'v':
            vertices.append([float(x) for x in fields[1:4]])
        elif fields and fields[0] == 'f':
            polygons.append([int(x.split('/')[0]) - 1 for x in fields[1:]])
    pairs = overlaps(vertices, polygons)
    results.append(dict(file=filename, polygons=len(polygons), nonAdjacentOverlapPairs=pairs, passed=not pairs))
    print(filename, 'non-adjacent overlapping polygon pairs:', len(pairs), flush=True)
Path(args[0]).write_text(json.dumps(dict(passed=all(r['passed'] for r in results),
    detectorControlsPassed=True, results=results,
    scope='Blender BVH candidates followed by double-precision triangle intersection tests (1e-9 tolerance), fan triangulation. Shared-vertex polygon pairs excluded. Not a complete test of adjacent folds, coplanar contacts or every self-intersection.'), indent=2) + '\n')
