"""Adaptive upper bounds on directed distance between triangle surfaces.

Distance to one convex target triangle is a convex function. Its maximum over a
source triangle is therefore bounded by the largest corner distance to that same
target triangle. Subdivision tightens that bound without assuming that sparse
samples represent the entire surface. Unresolved budgets reject explicitly.
"""
import numpy as np
import trimesh


def _nearest(mesh, points):
    distances, owners = [], []
    for start in range(0, len(points), 2048):
        _, distance, owner = trimesh.proximity.closest_point(mesh, points[start:start + 2048])
        distances.append(distance); owners.append(owner)
    return np.concatenate(distances), np.concatenate(owners)


def directed_bound(triangles, target, tolerance, *, max_depth=10, max_triangles=1000000):
    pending = np.asarray(triangles, dtype=float)
    if not len(pending) or not len(target.faces) or not np.isfinite(pending).all() or tolerance <= 0:
        raise ValueError('Surface bounds require finite nonempty triangles and a positive tolerance.')
    maximum_upper, sampled_max, tested, deepest = 0., 0., 0, 0
    numerical_margin = 64 * np.finfo(float).eps * max(1., np.abs(pending).max(), np.abs(target.vertices).max())
    witness = None
    for depth in range(max_depth + 1):
        deepest = depth
        if tested + len(pending) > max_triangles:
            reason = 'Adaptive triangle budget exhausted'; break
        tested += len(pending)
        centers = pending.mean(axis=1)
        center_distance, owner = _nearest(target, centers)
        worst = int(np.argmax(center_distance))
        if center_distance[worst] > sampled_max:
            sampled_max = float(center_distance[worst]); witness = centers[worst].tolist()
        if sampled_max > tolerance:
            reason = 'A surface point exceeds the distance tolerance'; break
        # Use a single target triangle for each source triangle's three corners.
        candidate = np.repeat(target.triangles[owner], 3, axis=0)
        corners = pending.reshape(-1, 3)
        near = trimesh.triangles.closest_point(candidate, corners)
        upper = np.linalg.norm(corners - near, axis=1).reshape(-1, 3).max(axis=1) + numerical_margin
        resolved = upper <= tolerance
        if np.any(resolved):
            maximum_upper = max(maximum_upper, float(upper[resolved].max()))
        unresolved = pending[~resolved]
        if not len(unresolved):
            return dict(passed=True, status='bounded', maximumUpperBound=maximum_upper, sampledMax=sampled_max,
                        testedTriangles=tested, subdivisionDepth=deepest, unresolvedTriangles=0, witness=witness)
        # Original vertices and subdivision corners also supply failure
        # witnesses; a centroid-only failure search would miss sharp tips.
        points = unresolved.reshape(-1, 3)
        corner_distance, _ = _nearest(target, points)
        worst = int(np.argmax(corner_distance))
        if corner_distance[worst] > sampled_max:
            sampled_max = float(corner_distance[worst]); witness = points[worst].tolist()
        if sampled_max > tolerance:
            reason = 'A surface point exceeds the distance tolerance'; break
        if depth == max_depth:
            reason = 'Adaptive subdivision depth exhausted'; break
        a, b, c = unresolved[:, 0], unresolved[:, 1], unresolved[:, 2]
        ab, bc, ca = (a + b) * .5, (b + c) * .5, (c + a) * .5
        pending = np.concatenate([np.stack(t, axis=1) for t in ((a, ab, ca), (ab, b, bc), (ca, bc, c), (ab, bc, ca))])
    return dict(passed=False, status='exceeded' if sampled_max > tolerance else 'unresolved', reason=reason,
                maximumUpperBound=None, sampledMax=sampled_max, testedTriangles=tested, subdivisionDepth=deepest,
                unresolvedTriangles=len(pending), witness=witness)


def measure(source, output, tolerance, **limits):
    forward = directed_bound(source.triangles, output, tolerance, **limits)
    backward = directed_bound(output.triangles, source, tolerance, **limits)
    return dict(passed=forward['passed'] and backward['passed'], tolerance=float(tolerance),
                sourceToOutput=forward, outputToSource=backward,
                scope='Adaptive triangle subdivision with convex point-to-triangle upper bounds in both directions. Double precision with a roundoff margin; unresolved depth/work budgets reject. Does not check topology or intersections.')
