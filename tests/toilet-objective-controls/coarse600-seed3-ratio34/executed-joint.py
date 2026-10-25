"""Joint guide/surface correction using remembered rejected surface witnesses.

Candidates must preserve every already-passing guide and directional surface
gate. Remembered barycentric points improve fitting; they never replace the
ordinary full-surface, contact, topology or shape acceptance checks.
"""
import numpy as np
import trimesh

import curved_quad as cq
import surface_guide_refine as fitter


def assess(source_mesh, positions, faces, guides, target, protected=None):
    spacing = np.sqrt(source_mesh.area / target)
    quality = cq.quad_quality(positions, faces, target)
    fit = cq._guide_fit(positions, guides.paths, guides.curves)
    passed = dict(quality=bool(quality['passed']))
    ratios = {}
    for index, path in enumerate(fit):
        ratios[f'guide{index}Distance'] = path['p95Distance'] / (.2 * spacing)
        ratios[f'guide{index}Angle'] = path['p95TangentAngleDegrees'] / 30
    passed.update({key: bool(value <= 1) for key, value in ratios.items()})
    protected = protected or {}
    broken = [key for key in passed if protected.get(key) and not passed[key]]
    contacts = dict(passed=None, checked=False, reason='Shape or a protected guide gate rejected before contact checking.')
    surface = dict(passed=None, checked=False, wholeSurfaceDiagonals={})
    bounds = {}
    eligible = False
    if quality['passed'] and not broken:
        contacts = dict(cq.surface_intersections(positions, faces, both_quad_diagonals=True), checked=True)
        if contacts['passed']:
            surface = cq.validate_surface(np.asarray(source_mesh.vertices), np.asarray(source_mesh.faces), positions, faces, target)
            surface['checked'] = True
            topology_ok = all(value for key, value in surface['checks'].items() if key not in ('sampledSurface', 'wholeSurface'))
            if topology_ok:
                bounds = surface['wholeSurfaceDiagonals'].copy()
                if not bounds:
                    for diagonal, a, b in (('02', [0, 1, 2], [0, 2, 3]), ('13', [0, 1, 3], [1, 2, 3])):
                        mesh = trimesh.Trimesh(positions, np.r_[faces[:, a], faces[:, b]], process=False)
                        bounds[diagonal] = cq.surface_distance(source_mesh, mesh, .5 * spacing)
                for diagonal, bound in bounds.items():
                    for direction in ('sourceToOutput', 'outputToSource'):
                        key = diagonal + direction
                        row = bound[direction]
                        passed[key] = row['passed']
                        ratios[key] = row['sampledMax'] / (.5 * spacing)
                        if not row['passed'] and ratios[key] <= 1:
                            ratios[key] = 1.000001
                broken = [key for key in passed if protected.get(key) and not passed[key]]
                eligible = bool(bounds) and not broken
    return dict(quality=quality, guideFit=fit, intersections=contacts, surface=surface, witnessBounds=bounds,
                gateRatios=ratios, gatePassed=passed, protectedGateFailures=broken, eligibleForRepair=eligible,
                violationScore=max(ratios.values()) if eligible else None,
                qualified=bool(eligible and all(passed.values()) and surface['passed']))


def _guide_witnesses(positions, guides, passed, spacing):
    selected_points = []
    for index, (path, curve) in enumerate(zip(guides.paths, guides.curves)):
        if passed[f'guide{index}Angle'] and passed[f'guide{index}Distance']:
            continue
        points = cq._sample(curve, 257)
        tangent = np.roll(points, -1, axis=0) - np.roll(points, 1, axis=0)
        tangent[0] = points[1] - points[0]
        tangent[-1] = points[-1] - points[-2]
        if path['closed']:
            tangent[0] = tangent[-1] = points[1] - points[-2]
        tangent /= np.maximum(1e-12, np.linalg.norm(tangent, axis=1))[:, None]
        edges = np.array(list(zip(path['vertices'][:-1], path['vertices'][1:])), dtype=int)
        a = positions[edges[:, 0]]
        delta = positions[edges[:, 1]] - a
        t = np.clip(((points[:, None, :] - a) * delta).sum(axis=2) / (delta * delta).sum(axis=1), 0, 1)
        distances = np.linalg.norm(points[:, None, :] - a - t[:, :, None] * delta, axis=2)
        owners = distances.argmin(axis=1)
        unit = delta / np.linalg.norm(delta, axis=1)[:, None]
        angle = np.degrees(np.arccos(np.clip(np.abs((tangent * unit[owners]).sum(axis=1)), 0, 1)))
        mask = np.zeros(len(points), dtype=bool)
        if not passed[f'guide{index}Angle']:
            mask |= angle > 30
        if not passed[f'guide{index}Distance']:
            mask |= distances[np.arange(len(points)), owners] > .2 * spacing
        selected_points.extend(points[mask])
    return np.asarray(selected_points).reshape(-1, 3)


def _remember(source_mesh, positions, faces, assessment, constraints, keys, candidate_id):
    for diagonal, bound in assessment['witnessBounds'].items():
        a, b = ([0, 1, 2], [0, 2, 3]) if diagonal == '02' else ([0, 1, 3], [1, 2, 3])
        tri = np.r_[faces[:, a], faces[:, b]]
        mesh = trimesh.Trimesh(positions, tri, process=False)
        for direction in ('sourceToOutput', 'outputToSource'):
            row = bound[direction]
            if row['passed'] or row['witness'] is None:
                continue
            witness = np.asarray([row['witness']])
            near, _, owner = trimesh.proximity.closest_point(mesh, witness)
            indices = tri[owner[0]]
            barycentric = trimesh.triangles.points_to_barycentric(positions[indices][None], near)[0]
            if not np.isfinite(barycentric).all() or barycentric.min() <= -1e-8:
                continue
            barycentric = np.maximum(barycentric, 0)
            barycentric /= barycentric.sum()
            key = (tuple(map(int, indices)), tuple(np.round(barycentric, 5)))
            if key in keys:
                continue
            keys.add(key)
            target = trimesh.proximity.closest_point(source_mesh, witness)[0][0]
            constraints.append(dict(vertices=indices.tolist(), barycentric=barycentric.tolist(), target=target.tolist(),
                                    witness=row['witness'], diagonal=diagonal, direction=direction,
                                    discoveredCandidate=candidate_id, sampledMax=row['sampledMax']))


def repair(source_mesh, positions, faces, edges, guides, target, *, job, record):
    """Return an assessed candidate after at most eight constrained local passes."""
    spacing = np.sqrt(source_mesh.area / target)
    current = assess(source_mesh, positions, faces, guides, target)
    record(current, phase='joint-guide-surface', initial=True)
    if not current['eligibleForRepair']:
        return positions, current
    constraints, keys, steps = [], set(), []
    candidate_id = 0
    for step in range(8):
        if current['qualified']:
            break
        surface_points = np.asarray([d['witness'] for bound in current['witnessBounds'].values()
                                     for d in (bound['sourceToOutput'], bound['outputToSource'])
                                     if not d['passed'] and d['witness'] is not None]).reshape(-1, 3)
        guide_points = _guide_witnesses(positions, guides, current['gatePassed'], spacing)
        before = len(constraints)
        witnesses = np.r_[surface_points, guide_points, np.asarray([item['target'] for item in constraints]).reshape(-1, 3)]
        if not len(witnesses):
            break
        source_points = trimesh.proximity.closest_point(source_mesh, witnesses)[0]
        patch = set()
        for a, b in (([0, 1, 2], [0, 2, 3]), ([0, 1, 3], [1, 2, 3])):
            tri = np.r_[faces[:, a], faces[:, b]]
            mesh = trimesh.Trimesh(positions, tri, process=False)
            owner = trimesh.proximity.closest_point(mesh, witnesses)[2]
            patch.update(tri[owner].ravel())
        for item in constraints:
            patch.update(item['vertices'])
        for _ in range(2):
            patch.update(faces[np.any(np.isin(faces, list(patch)), axis=1)].ravel())
        cq._progress(job, f'Refining guide alignment and surface accuracy · pass {step + 1}')
        proposal, refinement = fitter.refine(source_mesh, positions, faces, edges, guides, target,
                                             patch_vertices=patch, witness_source=source_points,
                                             tangent_tail_weight=80.0, surface_constraints=constraints, constraint_weight=8.)
        accepted = False
        step_record = dict(step=step, patchVertices=len(patch), constraintsBefore=before, continued=False)
        steps.append(step_record)
        for power in range(5):
            alpha = .5 ** power
            candidate = positions + alpha * (proposal - positions)
            trial = assess(source_mesh, candidate, faces, guides, target, current['gatePassed'])
            candidate_id += 1
            _remember(source_mesh, candidate, faces, trial, constraints, keys, candidate_id)
            record(trial, phase='joint-guide-surface', step=step, alpha=alpha, refinement=refinement,
                   patchVertices=len(patch), surfaceConstraintCount=len(constraints))
            progress = trial['eligibleForRepair'] and trial['violationScore'] < current['violationScore'] - 1e-6
            if trial['qualified'] or progress:
                positions, current, accepted = candidate, trial, True
                step_record.update(continued=True, candidate=candidate_id)
                break
        step_record['constraintsAfter'] = len(constraints)
        cq._write(job / 'joint-guide-repair.json', dict(steps=steps, constraints=constraints, qualified=current['qualified'],
                                                       tangentTailWeight=80.0, constraintWeight=8.))
        if not accepted and len(constraints) == before:
            break
    return positions, current
