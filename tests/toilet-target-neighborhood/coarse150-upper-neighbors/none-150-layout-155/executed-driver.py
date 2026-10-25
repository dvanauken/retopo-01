"""Bounded fallback for a guided layout that needs distributed curve fitting.

Every accepted mesh still passes the ordinary shape, topology, whole-surface,
contact and guide gates. Local fitting uses measured surface failure witnesses;
neither model identifiers nor retained test geometry participate.
"""
from pathlib import Path
import hashlib
import json
import subprocess

import numpy as np
import trimesh

import curved_quad as cq
import surface_guide_refine as fitter
from features import output_creases


def _assess(source_mesh, positions, faces, guides, target):
    spacing = np.sqrt(source_mesh.area / target)
    quality = cq.quad_quality(positions, faces, target)
    fit = cq._guide_fit(positions, guides.paths, guides.curves)
    guided = all(p['p95Distance'] <= .2 * spacing and p['p95TangentAngleDegrees'] <= 30 for p in fit)
    intersections = dict(passed=None, checked=False, reason='Shape or guide gate rejected before contact checking.')
    surface = dict(passed=None, checked=False, wholeSurfaceDiagonals={})
    bounds = {}
    eligible = False
    if quality['passed'] and guided:
        intersections = dict(cq.surface_intersections(positions, faces, both_quad_diagonals=True), checked=True)
        if intersections['passed']:
            surface = cq.validate_surface(np.asarray(source_mesh.vertices), np.asarray(source_mesh.faces), positions, faces, target)
            surface['checked'] = True
            bounds = surface['wholeSurfaceDiagonals'].copy()
            # A sparse-screen rejection can still supply local repair witnesses.
            # These extra measurements do not override the failed acceptance gate.
            if not bounds and all(v for k, v in surface['checks'].items() if k not in ('sampledSurface', 'wholeSurface')):
                for name, a, b in (('02', [0, 1, 2], [0, 2, 3]), ('13', [0, 1, 3], [1, 2, 3])):
                    mesh = trimesh.Trimesh(positions, np.r_[faces[:, a], faces[:, b]], process=False)
                    bounds[name] = cq.surface_distance(source_mesh, mesh, .5 * spacing)
            eligible = bool(bounds)
    score = max((d['sampledMax'] for b in bounds.values() for d in (b['sourceToOutput'], b['outputToSource'])), default=None)
    return dict(quality=quality, guideFit=fit, intersections=intersections, surface=surface,
                witnessBounds=bounds, eligibleForRepair=eligible, maxObservedSurfaceError=score,
                qualified=bool(eligible and surface['passed']))


def _repair(source_mesh, positions, faces, edges, guides, target, current, record, job):
    spacing = np.sqrt(source_mesh.area / target)
    for step in range(6):
        if current['qualified']:
            break
        witnesses = np.asarray([d['witness'] for b in current['witnessBounds'].values()
                                for d in (b['sourceToOutput'], b['outputToSource'])
                                if not d['passed'] and d['witness'] is not None]).reshape(-1, 3)
        if not len(witnesses):
            break  # An unresolved bound with no witness cannot authorize movement.
        source_points = trimesh.proximity.closest_point(source_mesh, witnesses)[0]
        patch = set()
        for a, b in (([0, 1, 2], [0, 2, 3]), ([0, 1, 3], [1, 2, 3])):
            tri = np.r_[faces[:, a], faces[:, b]]
            mesh = trimesh.Trimesh(positions, tri, process=False)
            owner = trimesh.proximity.closest_point(mesh, witnesses)[2]
            patch.update(tri[owner].ravel())
        for _ in range(2):
            patch.update(faces[np.any(np.isin(faces, list(patch)), axis=1)].ravel())
        cq._progress(job, f'Refining local surface accuracy · pass {step + 1}')
        proposal, refinement = fitter.refine(source_mesh, positions, faces, edges, guides, target,
                                             patch_vertices=patch, witness_source=source_points)
        accepted = False
        for power in range(5):
            alpha = .5 ** power
            candidate = positions + alpha * (proposal - positions)
            trial = _assess(source_mesh, candidate, faces, guides, target)
            record(trial, phase='local-surface-repair', step=step, alpha=alpha,
                   refinement=refinement, patchVertices=len(patch), witnesses=witnesses.tolist())
            progress = (trial['eligibleForRepair'] and
                        trial['maxObservedSurfaceError'] < current['maxObservedSurfaceError'] - spacing * 1e-6)
            if trial['qualified'] or progress:
                positions, current, accepted = candidate, trial, True
                break
        if not accepted:
            break
    return positions, current


def construct(source_mesh, curves, *, target, job, blender, input_path, history):
    """Try one additional fresh layout; return an accepted result or None."""
    seed = 2
    cq._progress(job, 'Building an additional layout for guide fitting')
    raw = job / f'quadri-layout-{seed}.json'
    command = [str(blender), '--background', '--threads', '8', '--python', str(cq.ROOT / 'scripts/quadriflow_mesh.py'),
               '--', '--input', str(input_path), '--output', str(raw), '--target', str(155), '--seed', str(seed)]
    with (job / f'quadri-layout-{seed}.log').open('w', encoding='utf-8') as log:
        process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if process.returncode or not raw.is_file():
        raise RuntimeError('The additional quad layout could not be built. The local calculation log was retained.')
    packet = json.loads(raw.read_text(encoding='utf-8'))
    positions, faces = np.asarray(packet['vertices'], dtype=float), np.asarray(packet['faces'], dtype=int)
    if faces.ndim != 2 or faces.shape[1] != 4 or not len(faces) or not np.isfinite(positions).all():
        raise ValueError('The additional quad layout returned invalid geometry.')
    edges = cq._edges(faces)
    guides = fitter.prepare(positions, edges, curves, np.sqrt(source_mesh.area / target))
    fallback_history = []

    def record(assessment, **details):
        assessment.update(seed=seed, iteration=len(fallback_history), **details)
        fallback_history.append(assessment)
        history.append(assessment)
        cq._write(job / 'sampled-guide-history.json', dict(attempts=fallback_history))

    def accepted(positions, current, method, extra_files=()):
        files = [Path(cq.__file__), Path(__file__), Path(fitter.__file__), cq.ROOT / 'quad_quality.py',
                 cq.ROOT / 'surface_intersections.py', cq.ROOT / 'surface_distance.py', cq.ROOT / 'scripts/quadriflow_mesh.py',
                 *extra_files]
        metadata = dict(backend=cq.BACKEND, nativeComparisonPerformed=False, generalAlgorithmRecovered=False,
                        target=target, guideMode=2, closedValidation=current['surface'], guidePaths=current['guideFit'],
                        intersectionValidation=current['intersections'], outputCreases=output_creases(positions, faces.tolist()),
                        refinementHistory=history, fittingMethod=method,
                        layoutEngine=dict(name='Blender QuadriFlow', version=packet['blenderVersion'], executable=str(blender), seed=seed),
                        sourceHashes={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                        limitations=['Engineering layout and fitting route, not recovered native equivalence.',
                                     'Guide fitting and surface preservation are approximate and can reject incompatible inputs.',
                                     'Whole-surface bounds and contact predicates use double precision; topology is checked separately.',
                                     'One additional layout and bounded refinement; general crease/attribute transfer is not implemented.'])
        cq._write(job / 'surface-solver.json', metadata)
        return positions, faces.tolist(), metadata

    repaired = False
    for iteration in range(5):
        cq._progress(job, f'Fitting sampled guide paths · pass {iteration + 1}')
        positions, refinement = fitter.refine(source_mesh, positions, faces, edges, guides, target)
        current = _assess(source_mesh, positions, faces, guides, target)
        record(current, phase='sampled-guide-fit', globalIteration=iteration, refinement=refinement)
        if current['eligibleForRepair'] and not current['qualified'] and not repaired:
            repaired = True
            repaired_positions, repaired_assessment = _repair(source_mesh, positions, faces, edges, guides, target, current, record, job)
            # Keep the global iteration sequence independent of unsuccessful local trials.
            if repaired_assessment['qualified']:
                positions, current = repaired_positions, repaired_assessment
        if current['qualified']:
            return accepted(positions, current, 'sampled-guide-paths-with-local-surface-repair')
    if curves:
        import surface_guide_joint as joint
        positions, current = joint.repair(source_mesh, positions, faces, edges, guides, target, job=job, record=record)
        if current['qualified']:
            return accepted(positions, current, 'sampled-guide-paths-with-joint-surface-repair', [Path(joint.__file__)])
    cq._write(job / 'failed-sampled-guide-candidate.json', dict(vertices=positions.tolist(), faces=faces.tolist()))
    return None
