"""Guides enter source connectivity and the field before integer quad extraction.

Independent QuadriFlow integration. Final acceptance uses the app's unchanged
quality, topology, contact, guide and whole-surface gates. Retain every candidate.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import time

import numpy as np
import trimesh

from guide_embedding import embed
from guide_embedding_check import verify
from guide_ordered_targets import targets as ordered_targets
from measure_geometry import read_obj
from features import output_creases
from curved_quad import (BACKEND, guides_pass, _edges, _guide_path, _guide_fit, _refine,
                         _progress, validate_surface)
from quad_quality import measure as quality
from surface_intersections import measure as contacts

ROOT = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj(path, vertices, faces):
    with path.open('w', encoding='utf-8') as stream:
        for point in vertices:
            stream.write('v ' + ' '.join(format(float(x), '.17g') for x in point) + '\n')
        for face in faces:
            stream.write('f ' + ' '.join(str(int(x) + 1) for x in face) + '\n')


def runtime():
    vendor = ROOT / 'engine/guided-quadriflow'
    manifest = json.loads((vendor / 'manifest.json').read_text())
    executable = vendor / 'quadriflow.exe'
    if sha(executable) != manifest['executableSha256']:
        raise RuntimeError('The guided layout executable differs from its reviewed build. Restore engine/guided-quadriflow.')
    directory = Path(os.environ.get('RETOPO_MINGW_RUNTIME', manifest['runtimeDirectory']))
    runtime_hashes = {}
    for name, identity in manifest['runtimeImports'].items():
        path = directory / name
        if not path.is_file() or sha(path) != identity['sha256']:
            raise RuntimeError('The guided layout runtime is missing or changed: ' + str(path) + '. See GUIDED_LAYOUT.md for the pinned runtime setup.')
        runtime_hashes[str(path)] = identity['sha256']
    env = os.environ.copy()
    env['PATH'] = str(directory) + os.pathsep + env.get('PATH', '')
    for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
        env[key] = '1'
    return executable, env, dict(manifest, runtimeHashes=runtime_hashes)


def construct(source, triangles, curves, *, target, job):
    job = Path(job)
    if isinstance(target, bool) or not isinstance(target, (int, np.integer)) or not 150 <= target <= 1800:
        raise ValueError('Target must be an integer from 150 to 1800.')
    source = np.asarray(source, dtype=float)
    triangles = np.asarray(triangles, dtype=int)
    curves = [np.asarray(c, dtype=float) for c in curves]
    if not curves:
        raise ValueError('The guided layout route requires at least one curve.')
    source_mesh = trimesh.Trimesh(source, triangles, process=False)
    if not source_mesh.is_watertight or not source_mesh.is_winding_consistent:
        raise ValueError('Guided surface layout requires a closed, consistently wound source.')
    executable, env, engine = runtime()
    out = job / 'guided-layout'
    out.mkdir(exist_ok=False)
    files = [ROOT / n for n in ('guided_layout.py', 'guide_embedding.py', 'guide_embedding_check.py',
                               'guide_ordered_targets.py', 'curved_quad.py', 'quad_quality.py',
                               'surface_intersections.py', 'surface_distance.py')]
    dependencies = out / 'dependencies'; dependencies.mkdir()
    for path in files:
        shutil.copy2(path, dependencies / path.name)
    source_hashes = {str(path): sha(path) for path in files}
    obj(out / 'source.obj', source, triangles)
    write(out / 'curves.json', dict(curves=[c.tolist() for c in curves], coordinateFrame='source'))
    write(out / 'settings.json', dict(target=int(target), seedPolicy=[0, 1], maxLayouts=4,
                                    maxRefinementPasses=5, guideWidth=.5, orientationWeight=1,
                                    positionWeight=0, embeddedGuidePositions=True,
                                    sourceHashes=source_hashes, layoutEngine=engine))
    _progress(job, 'Embedding guides into the source surface')
    p, f, embedding = embed(source, triangles, curves)
    obj(out / 'embedded.obj', p, f)
    write(out / 'embedding.json', embedding)
    checked = verify(source, triangles, p, f, embedding, curves)
    write(out / 'embedding-check.json', checked)
    if not checked['passed']:
        raise ValueError('Guide embedding failed source coverage or connected-path checks. The diagnostic files were retained.')
    segments = []
    for ci, edges in embedding['guideEdges'].items():
        for a, b in edges:
            owner = trimesh.proximity.closest_point(source_mesh, [(p[a] + p[b]) * .5])[2][0]
            segments.append([int(ci), *p[a], *p[b], *source_mesh.face_normals[owner]])
    with (out / 'segments.txt').open('w', encoding='utf-8') as stream:
        stream.write(str(len(segments)) + '\n')
        for segment in segments:
            stream.write(' '.join(format(float(x), '.17g') for x in segment) + '\n')
    spacing = float(np.sqrt(source_mesh.area / target))
    history = []
    budget, seed, previous_budgets = int(target), 0, set()
    started = time.monotonic()
    for attempt in range(4):
        # The server owns a 10-minute outer deadline. Stop admitting new work
        # before it; subprocesses have separate bounded execution time.
        if time.monotonic() - started > 420:
            break
        folder = out / f'attempt-{attempt}'; folder.mkdir()
        command = [str(executable), '-i', str(out / 'embedded.obj'), '-o', str(folder / 'layout.obj'),
                   '-f', str(budget), '-seed', str(seed), '-field', str(folder / 'field.csv'),
                   '-guides', str(out / 'segments.txt'), '-guide-width', '.5', '-orientation-weight', '1',
                   '-position-weight', '0', '-embedded-guides', '-project-guide-positions']
        row = dict(attempt=attempt, seed=seed, layoutBudget=budget, target=int(target), command=command,
                   passed=False, refinements=[])
        history.append(row)
        _progress(job, f'Building guided quad layout · attempt {attempt + 1}')
        try:
            with (folder / 'process.log').open('w', encoding='utf-8') as log:
                process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=env, timeout=150,
                                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            row['exitCode'] = process.returncode
            if process.returncode:
                raise ValueError('The guided layout process failed; its log was retained.')
            positions, faces = read_obj(folder / 'layout.obj')
            faces = np.asarray(faces, dtype=int)
            if faces.ndim != 2 or faces.shape[1] != 4 or not len(faces) or not np.isfinite(positions).all():
                raise ValueError('The guided layout returned invalid quad geometry.')
            row['layoutQuality'] = quality(positions, faces, target)
            row['faceCount'] = len(faces)
            # Count feedback changes only the internal budget. Acceptance and
            # all geometric tolerances always use the submitted user target.
            if abs(len(faces) - target) / target > .15:
                previous_budgets.add((seed, budget))
                corrected = int(np.clip(round(budget * target / len(faces)), 50, 100000))
                row['countCorrection'] = corrected
                if (seed, corrected) in previous_budgets:
                    seed += 1
                    budget = int(target)
                else:
                    budget = corrected
                if seed > 1:
                    break
                continue
            edges = _edges(faces)
            paths, pin_rows, target_rows = [], [], []
            for curve in curves:
                path, ids, _ = _guide_path(positions, edges, curve, spacing)
                paths.append(path); pin_rows.extend(ids)
                target_rows.extend(ordered_targets(positions[ids], curve, path['closed']))
            pins = np.asarray(pin_rows, dtype=int)
            targets = np.asarray(target_rows, dtype=float)
            for pin in set(pin_rows):
                shared = targets[pins == pin]
                if np.max(np.linalg.norm(shared - shared[0], axis=1)) > .1 * spacing:
                    raise ValueError('Guide paths compete for the same output vertices. Separate the guides or increase density.')
            for iteration in range(5):
                _progress(job, f'Refining guided quads · pass {iteration + 1}')
                positions, details = _refine(source_mesh, positions, faces, edges, pins, targets, target)
                obj(folder / f'candidate-{iteration}.obj', positions, faces)
                fit = _guide_fit(positions, paths, curves, spacing)
                q = quality(positions, faces, target)
                contact = contacts(positions, faces, both_quad_diagonals=True)
                surface = validate_surface(source, triangles, positions, faces, target, whole_surface=False)
                guide_ok = guides_pass(fit, spacing)
                if q['passed'] and contact['passed'] and surface['passed'] and guide_ok:
                    _progress(job, 'Checking the full surface and both quad diagonals')
                    surface = validate_surface(source, triangles, positions, faces, target)
                accepted = q['passed'] and contact['passed'] and surface['passed'] and guide_ok
                row['refinements'].append(dict(iteration=iteration, passed=accepted, refinement=details,
                                               quality=q, contacts=contact, surface=surface, guideFit=fit))
                row['passed'] = accepted
                write(out / 'attempts.json', history)
                if accepted:
                    metadata = dict(backend=BACKEND, nativeComparisonPerformed=False, generalAlgorithmRecovered=False,
                                    target=int(target), guideMode=2, closedValidation=surface, guidePaths=fit,
                                    intersectionValidation=contact, outputCreases=output_creases(positions, faces.tolist()),
                                    refinementHistory=history, sourceHashes=source_hashes,
                                    layoutEngine=dict(name='Guide-constrained QuadriFlow fork', seed=seed,
                                                      layoutBudget=budget, executable=str(executable), **engine),
                                    limitations=['Independent engineering implementation; no native parity claim.',
                                                 'Double-precision surface and contact bounds with explicit tolerances.',
                                                 'Complex guide networks can reject; general crease and attribute transfer remains unfinished.'])
                    write(job / 'surface-solver.json', metadata)
                    return positions, faces.tolist(), metadata
        except (ValueError, subprocess.TimeoutExpired) as error:
            row['error'] = str(error)
        finally:
            write(out / 'attempts.json', history)
        seed += 1
        budget = int(target)
        if seed > 1:
            break
    write(job / 'surface-solver-failure.json', dict(passed=False, attempts=history))
    raise ValueError('The guided layout did not pass all shape, guide, contact and surface checks. '
                     'No new mesh was accepted; the attempted layouts and measurements were retained.')
