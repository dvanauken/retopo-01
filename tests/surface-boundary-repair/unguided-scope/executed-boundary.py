"""Bounded boundary-bridge proposals for an unguided closed source.

Bridging is a topology proposal, never an acceptance shortcut. The original
source, requested density and all complete geometry gates still apply.
"""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

import curved_quad as cq
import surface_guide_refine as fitter
from features import output_creases


def bridge_candidates(faces):
    """Return at most eight oriented bridges between two simple equal loops."""
    faces = np.asarray(faces, dtype=int)
    if faces.ndim != 2 or faces.shape[1] != 4 or any(len(set(face)) != 4 for face in faces):
        return []
    incidence = defaultdict(list)
    for face in faces:
        for a, b in zip(face, np.roll(face, -1)):
            incidence[tuple(sorted((int(a), int(b))))].append((int(a), int(b)))
    if any(len(items) > 2 or (len(items) == 2 and items[0] != items[1][::-1]) for items in incidence.values()):
        return []
    boundary = [items[0] for items in incidence.values() if len(items) == 1]
    outgoing = dict(boundary)
    if not boundary or len(outgoing) != len(boundary) or len({b for a, b in boundary}) != len(boundary):
        return []
    pending, loops = set(outgoing), []
    while pending:
        first = min(pending)
        loop, current = [], first
        while current not in loop:
            if current not in pending or current not in outgoing:
                return []
            loop.append(current)
            pending.remove(current)
            current = outgoing[current]
        if current != first:
            return []
        loops.append(loop)
    if len(loops) != 2 or len(loops[0]) != len(loops[1]) or not 3 <= len(loops[0]) <= 8:
        return []
    a, b = loops
    n = len(a)
    candidates = []
    for shift in range(n):
        added = [[a[(i + 1) % n], a[i], b[(shift - i) % n], b[(shift - i - 1) % n]] for i in range(n)]
        candidates.append(dict(shift=shift, loops=loops, addedFaces=added, faces=np.r_[faces, added]))
    return candidates


def construct(source_mesh, *, target, job, blender, input_path, history):
    """Try one fresh alternate layout and its bounded bridge correspondences."""
    import surface_guide_repair as repair
    if not source_mesh.is_watertight or not source_mesh.is_winding_consistent:
        return None
    seed = 4
    folder = job / 'boundary-layout-4'
    folder.mkdir()
    cq._progress(job, 'Building an alternate closed-surface layout')
    raw = folder / 'quadri-layout-4.json'
    command = [str(blender), '--background', '--threads', '8', '--python', str(cq.ROOT / 'scripts/quadriflow_mesh.py'),
               '--', '--input', str(input_path), '--output', str(raw), '--target', str(target), '--seed', str(seed)]
    with (folder / 'quadri-layout-4.log').open('w', encoding='utf-8') as log:
        process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if process.returncode or not raw.is_file():
        raise RuntimeError('The alternate closed-surface layout could not be built. Its calculation log was retained.')
    packet = json.loads(raw.read_text(encoding='utf-8'))
    positions, faces = np.asarray(packet['vertices'], dtype=float), np.asarray(packet['faces'], dtype=int)
    if not np.isfinite(positions).all() or faces.ndim != 2 or faces.shape[1] != 4 or not len(faces):
        raise ValueError('The alternate closed-surface layout returned invalid geometry.')
    candidates = bridge_candidates(faces)
    attempts = []
    def save():
        cq._write(job / 'boundary-layout-attempts.json', dict(requestedTarget=target, seed=seed, candidates=len(candidates), attempts=attempts))
    save()
    for candidate in candidates:
        p, quads = positions.copy(), candidate['faces']
        attempt_dir = folder / ('bridge-' + str(candidate['shift']))
        attempt_dir.mkdir()
        cq._write(attempt_dir / 'input.json', dict(vertices=p.tolist(), faces=quads.tolist()))
        edges = cq._edges(quads)
        guides = fitter.prepare(p, edges, [], np.sqrt(source_mesh.area / target))
        begin = len(history)
        trial_history = []
        def record(assessment, **details):
            assessment.update(seed=seed, layoutTarget=target, boundaryBridge=candidate['shift'],
                              iteration=len(trial_history), **details)
            trial_history.append(assessment)
            history.append(assessment)
            cq._write(attempt_dir / 'history.json', dict(attempts=trial_history))
        for iteration in range(5):
            cq._progress(job, f'Fitting closed-surface layout · pass {iteration + 1}')
            p, refinement = fitter.refine(source_mesh, p, quads, edges, guides, target, edge_ratio_aim=3.4)
            current = repair._assess(source_mesh, p, quads, guides, target)
            record(current, phase='boundary-guide-fit', globalIteration=iteration, refinement=refinement)
            if current['qualified']:
                break
        if current['eligibleForRepair'] and not current['qualified']:
            p, current = repair._repair(source_mesh, p, quads, edges, guides, target, current, record, job, edge_ratio_aim=3.4)
        cq._write(attempt_dir / 'candidate.json', dict(vertices=p.tolist(), faces=quads.tolist()))
        attempts.append(dict(shift=candidate['shift'], addedFaces=candidate['addedFaces'], loops=candidate['loops'],
                             accepted=current['qualified'], firstHistoryIndex=begin, assessments=len(history) - begin,
                             artifactDirectory=str(attempt_dir.relative_to(job))))
        save()
        if current['qualified']:
            files = [Path(cq.__file__), Path(__file__), Path(fitter.__file__), Path(repair.__file__),
                     cq.ROOT / 'quad_quality.py', cq.ROOT / 'surface_intersections.py', cq.ROOT / 'surface_distance.py',
                     cq.ROOT / 'scripts/quadriflow_mesh.py']
            metadata = dict(backend=cq.BACKEND, nativeComparisonPerformed=False, generalAlgorithmRecovered=False,
                target=target, guideMode=2, closedValidation=current['surface'], guidePaths=current['guideFit'],
                intersectionValidation=current['intersections'], outputCreases=output_creases(p, quads.tolist()),
                refinementHistory=history, fittingMethod='boundary-bridge-with-local-surface-repair',
                layoutEngine=dict(name='Blender QuadriFlow', version=packet['blenderVersion'], executable=str(blender), seed=seed, targetFaces=target),
                boundaryRepair=dict(shift=candidate['shift'], loops=candidate['loops'], addedFaces=candidate['addedFaces'], edgeRatioAim=3.4),
                sourceHashes={str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
                limitations=['Engineering layout and fitting route, not recovered native equivalence.',
                             'Bounded bridge proposals for two equal boundary loops; every full geometry gate still applies.',
                             'General crease/attribute transfer is not implemented.'])
            cq._write(job / 'surface-solver.json', metadata)
            return p, quads.tolist(), metadata
    return None
