"""Screen non-adjacent polygon crossings using indexed triangle intersection.

Shared-vertex pairs are excluded. This supplements, rather than replaces,
topology and shape checks; it is not a certificate for all adjacent contacts.
"""
import numpy as np
from rtree.index import Index, Property


def triangle_intersects(a, b, eps=1e-9):
    na, nb = np.cross(a[1] - a[0], a[2] - a[0]), np.cross(b[1] - b[0], b[2] - b[0])
    la, lb = np.linalg.norm(na), np.linalg.norm(nb)
    if min(la, lb) < eps * eps:
        return False  # Degeneracy is checked separately by the quality gate.
    na /= la; nb /= lb
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


def measure(vertices, faces):
    v = np.asarray(vertices, dtype=float)
    polygons = [v[f] for f in faces]
    bounds = [np.r_[p.min(axis=0), p.max(axis=0)] for p in polygons]
    tree = Index(((i, b, None) for i, b in enumerate(bounds)), properties=Property(dimension=3))
    ownership = [set(f) for f in faces]
    triangles = [[p[[0, i, i + 1]] for i in range(1, len(p) - 1)] for p in polygons]
    pairs = []
    for a, bound in enumerate(bounds):
        for b in tree.intersection(bound):
            if b <= a or ownership[a].intersection(ownership[b]):
                continue
            if any(triangle_intersects(x, y) for x in triangles[a] for y in triangles[b]):
                pairs.append([a, b])
    tree.close()
    return dict(passed=not pairs, nonAdjacentIntersectingFacePairs=sorted(pairs),
                scope='Indexed polygon bounds and double-precision triangle intersection, fan triangulation, 1e-9 tolerance. Shared-vertex face pairs excluded; not a complete adjacent-contact certificate.')
