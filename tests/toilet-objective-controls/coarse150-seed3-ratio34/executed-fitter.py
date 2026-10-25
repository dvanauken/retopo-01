"""Sampled guide fitting with optional local source-surface support.

This module takes geometry, authored curves and a requested density explicitly.
It produces a candidate; the caller must still apply all acceptance gates.
"""
from dataclasses import dataclass
import numpy as np
import trimesh
from scipy.optimize import least_squares
from scipy.sparse import lil_matrix
import curved_quad as cq


@dataclass
class GuideConstraints:
    curves: list
    paths: list
    pins: np.ndarray
    targets: np.ndarray
    pin_groups: list


def prepare(positions, edges, curves, spacing):
    curves = [np.asarray(curve, dtype=float) for curve in curves]
    paths, pin_rows, target_rows, groups = [], [], [], []
    for curve in curves:
        path, pins, targets = cq._guide_path(positions, edges, curve, spacing)
        paths.append(path)
        groups.append((curve, len(pin_rows), len(pin_rows) + len(pins)))
        pin_rows.extend(pins)
        target_rows.extend(targets)
    pins = np.asarray(pin_rows, dtype=int)
    targets = np.asarray(target_rows, dtype=float).reshape(-1, 3)
    for pin in set(pin_rows):
        shared = targets[pins == pin]
        if np.max(np.linalg.norm(shared - shared[0], axis=1)) > spacing * .1:
            raise ValueError('Two guides compete for the same output vertices. Increase density or separate their paths.')
    return GuideConstraints(curves, paths, pins, targets, groups)


def _sample_targets(positions, guides):
    edges, points, tangents, weights = [], [], [], []
    for path, curve in zip(guides.paths, guides.curves):
        path_edges = np.array(list(zip(path['vertices'][:-1], path['vertices'][1:])), dtype=int)
        samples = cq._sample(curve, 401)
        tangent = np.roll(samples, -1, axis=0) - np.roll(samples, 1, axis=0)
        tangent[0] = samples[1] - samples[0]
        tangent[-1] = samples[-1] - samples[-2]
        if path['closed']:
            tangent[0] = tangent[-1] = samples[1] - samples[-2]
        tangent /= np.maximum(1e-12, np.linalg.norm(tangent, axis=1))[:, None]
        a = positions[path_edges[:, 0]]
        delta = positions[path_edges[:, 1]] - a
        t = np.clip(((samples[:, None, :] - a) * delta).sum(axis=2) / np.maximum(1e-18, (delta * delta).sum(axis=1)), 0, 1)
        error = samples[:, None, :] - a - t[:, :, None] * delta
        selected = (error * error).sum(axis=2).argmin(axis=1)
        edges.extend(path_edges[selected])
        points.extend(samples)
        tangents.extend(tangent)
        weights.extend([np.sqrt(len(path_edges) / len(samples))] * len(samples))
    return (np.asarray(edges, dtype=int).reshape(-1, 2), np.asarray(points).reshape(-1, 3),
            np.asarray(tangents).reshape(-1, 3), np.asarray(weights))


def refine(source_mesh, positions, faces, edges, guides, target, *, patch_vertices=None, witness_source=None,
           tangent_tail_weight=0., surface_constraints=None, constraint_weight=8.):
    """Return a fitted candidate without altering the input arrays or gates."""
    positions, faces, edges = np.asarray(positions), np.asarray(faces), np.asarray(edges)
    spacing = np.sqrt(source_mesh.area / target)
    pins, targets = guides.pins, guides.targets
    sample_edges, sample_points, sample_tangents, sample_weights = _sample_targets(positions, guides)
    surface_constraints = surface_constraints or []
    memory_tri = np.asarray([item['vertices'] for item in surface_constraints], dtype=int).reshape(-1, 3)
    memory_bary = np.asarray([item['barycentric'] for item in surface_constraints]).reshape(-1, 3)
    memory_target = np.asarray([item['target'] for item in surface_constraints]).reshape(-1, 3)
    jacobian, cosine = cq._corners(positions, faces)
    bad = (jacobian.min(axis=1) < .7) | (np.abs(cosine).max(axis=1) > .75)
    bad |= np.abs(cq._warpage(positions, faces)) > spacing * .05
    vertex_anchor, vertex_error, vertex_triangles = trimesh.proximity.closest_point(source_mesh, positions)
    active = set(faces[bad].ravel()) | set(pins) | set(np.flatnonzero(vertex_error > spacing * .25))
    if patch_vertices is None:
        out_tri = np.r_[faces[:, [0, 1, 2]], faces[:, [0, 2, 3]]]
        out_surface = trimesh.Trimesh(positions, out_tri, process=False)
        near, error, owners = trimesh.proximity.closest_point(out_surface, source_mesh.vertices)
        selected = error > spacing * .25
        support = out_tri[owners[selected]]
        barycentric = trimesh.triangles.points_to_barycentric(positions[support], near[selected])
        support_target = source_mesh.vertices[selected]
        active.update(support.ravel())
        for _ in range(2):
            active.update(faces[np.any(np.isin(faces, list(active)), axis=1)].ravel())
    else:
        active = set(patch_vertices)
        witnesses = np.empty((0, 3)) if witness_source is None else np.asarray(witness_source).reshape(-1, 3)
        source_samples = np.r_[source_mesh.vertices, source_mesh.triangles_center, witnesses]
        supports, barycentrics, support_targets = [], [], []
        for first, second in (([0, 1, 2], [0, 2, 3]), ([0, 1, 3], [1, 2, 3])):
            out_tri = np.r_[faces[:, first], faces[:, second]]
            out_surface = trimesh.Trimesh(positions, out_tri, process=False)
            near, error, owners = trimesh.proximity.closest_point(out_surface, source_samples)
            selected = (error > spacing * .25) & np.any(np.isin(out_tri[owners], list(active)), axis=1)
            owned = out_tri[owners[selected]]
            supports.append(owned)
            barycentrics.append(trimesh.triangles.points_to_barycentric(positions[owned], near[selected]))
            support_targets.append(source_samples[selected])
        support = np.concatenate(supports)
        barycentric = np.concatenate(barycentrics)
        support_target = np.concatenate(support_targets)
    ids = np.array(sorted(active), dtype=int)
    if not len(ids):
        return positions, {'vertices': 0, 'evaluations': 0}
    lookup = np.full(len(positions), -1, dtype=int)
    lookup[ids] = np.arange(len(ids))
    local_faces = faces[np.any(np.isin(faces, ids), axis=1)]
    local_edges = edges[np.any(np.isin(edges, ids), axis=1)]
    anchor = vertex_anchor[ids]
    normal = source_mesh.face_normals[vertex_triangles[ids]]
    groups = [(len(local_faces) * 4, local_faces)] * 3 + [(len(local_faces), local_faces)]
    groups += [(len(local_faces), local_faces)]
    groups += [(len(local_edges), local_edges)] * 2
    groups += [(len(ids), ids[:, None]), (len(ids) * 3, ids[:, None]), (len(pins) * 3, pins[:, None]), (len(support) * 3, support),
               (len(ids), ids[:, None]), (len(support), support)]
    groups += [(len(sample_edges) * 3, sample_edges)] * 2
    groups += [(len(memory_tri) * 3, memory_tri), (len(memory_tri), memory_tri)]
    sparsity = lil_matrix((sum(size for size, _ in groups), len(ids) * 3), dtype=int)
    offset = 0
    for size, owners in groups:
        repeat = size // len(owners) if len(owners) else 0
        for i, vertices in enumerate(owners):
            for vertex in vertices:
                k = lookup[vertex]
                if k >= 0:
                    sparsity[offset + i * repeat:offset + (i + 1) * repeat, k * 3:k * 3 + 3] = 1
        offset += size

    def pin_residual(points):
        nearest = []
        for curve, begin, end in guides.pin_groups:
            _, parameters = cq._nearest_curve(points[begin:end], curve)
            arc = cq._arc(curve)
            projected = np.array([np.interp(parameters, arc, curve[:, i]) for i in range(3)]).T
            if np.linalg.norm(curve[0] - curve[-1]) >= 1e-8:
                projected[0], projected[-1] = curve[0], curve[-1]
            nearest.extend(projected)
        nearest = np.asarray(nearest).reshape(-1, 3)
        return ((points - nearest) * 80 + (points - targets) * 4).ravel() / spacing

    def sampled_path_residual(points):
        a = points[sample_edges[:, 0]]
        delta = points[sample_edges[:, 1]] - a
        denominator = np.maximum(1e-18, (delta * delta).sum(axis=1))
        t = np.clip(((sample_points - a) * delta).sum(axis=1) / denominator, 0, 1)
        near = a + t[:, None] * delta
        unit = delta / np.sqrt(denominator)[:, None]
        if tangent_tail_weight:
            cross = np.cross(unit, sample_tangents)
            sine = np.linalg.norm(cross, axis=1)
            factor = 12 + tangent_tail_weight * np.maximum(sine - np.sin(np.radians(25)), 0) / np.maximum(sine, 1e-12)
            return np.r_[((near - sample_points) / spacing * 32.0 * sample_weights[:, None]).ravel(),
                         (cross * factor[:, None] * sample_weights[:, None]).ravel()]
        return np.r_[((near - sample_points) / spacing * 32.0 * sample_weights[:, None]).ravel(),
                     (np.cross(unit, sample_tangents) * 12 * sample_weights[:, None]).ravel()]

    def memory_residual(points):
        delta = (points[memory_tri] * memory_bary[:, :, None]).sum(axis=1) - memory_target
        return np.r_[(delta / spacing * constraint_weight).ravel(),
                     np.maximum(np.linalg.norm(delta, axis=1) / spacing - .4, 0) * 40]

    def residual(x):
        q = positions.copy()
        q[ids] = x.reshape(-1, 3)
        jacobian, cosine = cq._corners(q, local_faces)
        length = np.linalg.norm(q[local_edges[:, 1]] - q[local_edges[:, 0]], axis=1)
        delta = q[ids] - anchor
        fl = np.linalg.norm(np.roll(q[local_faces], -1, axis=1) - q[local_faces], axis=2)
        ratio = fl.max(axis=1) / np.maximum(1e-10, fl.min(axis=1))
        surface_delta = (q[support] * barycentric[:, :, None]).sum(axis=1) - support_target
        return np.r_[np.maximum(.7 - jacobian, 0).ravel() * 60,
                     np.maximum(np.abs(cosine) - .7, 0).ravel(), cosine.ravel() * .1,
                     np.maximum(ratio - 3.4, 0) * 10, cq._warpage(q, local_faces) / spacing * 8,
                     np.maximum(.4 - length / spacing, 0) * 5,
                     np.maximum(length / spacing - 1.7, 0), (delta * normal).sum(axis=1) / spacing * 6,
                     delta.ravel() / spacing * 2, pin_residual(q[pins]),
                     surface_delta.ravel() / spacing * 4,
                     np.maximum(np.linalg.norm(delta, axis=1) / spacing - .35, 0) * 40,
                     np.maximum(np.linalg.norm(surface_delta, axis=1) / spacing - .35, 0) * 40,
                     sampled_path_residual(q), memory_residual(q)]
    result = least_squares(residual, positions[ids].ravel(), jac_sparsity=sparsity.tocsr(), max_nfev=150, ftol=1e-6, xtol=1e-5)
    output = positions.copy()
    output[ids] = result.x.reshape(-1, 3)
    return output, {'vertices': len(ids), 'evaluations': result.nfev, 'sourceSupportPoints': len(support)}
