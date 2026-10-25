"""Engineering closed-surface quad layout, guide fitting and measured acceptance.

Guided meshes embed authored curves before an independent QuadriFlow fork
constructs connectivity. Unguided meshes retain the Blender QuadriFlow route.
Both routes require shape, surface, contact and guide acceptance. No fixture IDs or saved
geometry participate. The recovered reference engine remains unchanged.
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
from scipy.optimize import least_squares
from scipy.sparse import csr_matrix, lil_matrix
from scipy.sparse.csgraph import dijkstra

from features import output_creases
from measure_geometry import guide_alignment, topology
from measure_polygon_geometry import triangulate
from mesh_validation import links
from quad_quality import measure as quad_quality
from surface_intersections import measure as surface_intersections
from surface_distance import measure as surface_distance

ROOT = Path(__file__).resolve().parent
BACKEND = 'engineering-guided-surface-quads'


def find_blender():
    configured = os.environ.get('RETOPO_BLENDER')
    candidates = [Path(configured)] if configured else []
    found = shutil.which('blender')
    if found:
        candidates.append(Path(found))
    candidates.extend(sorted(Path(os.environ.get('ProgramFiles', 'C:/Program Files')).glob('Blender Foundation/Blender */blender.exe'), reverse=True))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError('The surface quad solver needs Blender. Install Blender or set RETOPO_BLENDER to its executable, then restart the local server.')


def _write(path, data):
    path.write_text(json.dumps(data, allow_nan=False), encoding='utf-8')


def _progress(job, stage):
    temporary = job / 'progress.tmp'
    _write(temporary, {'stage': stage})
    # Windows readers/AV can hold the destination without delete sharing.
    # Progress is advisory: a briefly locked display file must not discard an
    # otherwise usable solve. Keep the previous complete status on exhaustion.
    for delay in (0., .01, .02, .04, .08):
        if delay:
            time.sleep(delay)
        try:
            temporary.replace(job / 'progress.json')
            break
        except PermissionError:
            continue
    print(stage, flush=True)


def _edges(faces):
    return np.unique(np.sort(np.c_[faces.ravel(), np.roll(faces, -1, axis=1).ravel()], axis=1), axis=0)


def _corners(positions, faces):
    q = positions[faces]
    a, b = np.roll(q, -1, axis=1) - q, np.roll(q, 1, axis=1) - q
    normal = np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0]) + np.cross(q[:, 2] - q[:, 0], q[:, 3] - q[:, 0])
    normal /= np.maximum(1e-20, np.linalg.norm(normal, axis=1))[:, None]
    denominator = np.maximum(1e-20, np.linalg.norm(a, axis=2) * np.linalg.norm(b, axis=2))
    return (np.cross(a, b) * normal[:, None, :]).sum(axis=2) / denominator, (a * b).sum(axis=2) / denominator


def _arc(curve):
    return np.r_[0., np.cumsum(np.linalg.norm(np.diff(curve, axis=0), axis=1))]


def _sample(curve, count=257):
    arc = _arc(curve)
    return np.array([np.interp(np.linspace(0, arc[-1], count), arc, curve[:, i]) for i in range(3)]).T


def _nearest_curve(points, curve):
    a, delta = curve[:-1], np.diff(curve, axis=0)
    lengths = np.linalg.norm(delta, axis=1)
    arc, denominator = _arc(curve), lengths ** 2
    distances, parameters = [], []
    for first in range(0, len(points), 256):
        batch = points[first:first + 256]
        t = np.clip(((batch[:, None, :] - a) * delta).sum(axis=2) / denominator, 0, 1)
        residual = batch[:, None, :] - a - t[:, :, None] * delta
        ds = (residual * residual).sum(axis=2)
        ids, rows = ds.argmin(axis=1), np.arange(len(batch))
        distances.extend(np.sqrt(ds[rows, ids]))
        parameters.extend(arc[ids] + t[rows, ids] * lengths[ids])
    return np.asarray(distances), np.asarray(parameters)


def _targets(curve, count, closed, first):
    # Keep significant corners instead of distributing every vertex uniformly
    # across small notches. Subdivide first when the authored curve is sparse.
    points = curve[:-1].copy() if closed else curve.copy()
    if len(points) < count:
        points = np.unique(np.r_[_arc(curve), np.linspace(0, _arc(curve)[-1], count * 3)])
        points = np.array([np.interp(points, _arc(curve), curve[:, i]) for i in range(3)]).T
        if closed:
            points = points[:-1]
    if closed:
        offset = int(np.argmin(np.linalg.norm(points - first, axis=1)))
        points = np.roll(points, -offset, axis=0)
    keep = list(range(len(points)))
    while len(keep) > count:
        q = points[keep]
        area = np.linalg.norm(np.cross(q - np.roll(q, 1, axis=0), np.roll(q, -1, axis=0) - q), axis=1)
        area[0] = np.inf
        if not closed:
            area[-1] = np.inf
        keep.pop(int(area.argmin()))
    return points[keep]


def _guide_path(positions, edges, curve, spacing):
    distance, parameter = _nearest_curve(positions, curve)
    closed = bool(np.linalg.norm(curve[0] - curve[-1]) < 1e-8)
    n = len(positions)
    start = int(np.argmin(np.linalg.norm(positions - curve[0], axis=1)))
    rows, cols, weights = [], [], []
    length = _arc(curve)[-1]
    if closed:
        parameter = (parameter - parameter[start]) % length
        parameter[start] = 0.
    for a, b in np.r_[edges, edges[:, ::-1]]:
        if max(distance[a], distance[b]) > 3.2 * spacing:
            continue
        weight = np.linalg.norm(positions[a] - positions[b]) * (1 + 40 * ((distance[a] + distance[b]) * .5 / spacing) ** 2)
        if closed:
            step = (parameter[b] - parameter[a] + length / 2) % length - length / 2
            wrap = int(round((step - (parameter[b] - parameter[a])) / length))
            for layer in (0, 1):
                destination = layer + wrap
                if destination in (0, 1):
                    rows.append(layer * n + a); cols.append(destination * n + b); weights.append(weight)
        else:
            rows.append(a); cols.append(b); weights.append(weight)
    graph = csr_matrix((weights, (rows, cols)), shape=((2 * n, 2 * n) if closed else (n, n)))
    distances, predecessor = dijkstra(graph, indices=start, return_predecessors=True)
    end = start + n if closed else int(np.argmin(np.linalg.norm(positions - curve[-1], axis=1)))
    if start == end or not np.isfinite(distances[end]):
        raise ValueError('A guide has no resolvable output edge path at this density. Increase the target or shorten the guide.')
    current, path = end, [end]
    while current != start:
        current = int(predecessor[current]); path.append(current)
    path = np.asarray(path[::-1], dtype=int) % n
    unique = path[:-1] if closed else path
    if len(set(unique)) != len(unique) or len(unique) < (4 if closed else 2):
        raise ValueError('The guide needs a simpler edge path or a higher target density.')
    return {'vertices': path.tolist(), 'closed': closed}, unique, _targets(curve, len(unique), closed, positions[start])


def _guide_fit(positions, paths, curves):
    result = []
    for index, (path, curve) in enumerate(zip(paths, curves)):
        ids = path['vertices']
        alignment = guide_alignment(positions, list(zip(ids[:-1], ids[1:])), _sample(curve))
        result.append(dict(path, curve=index, p95Distance=alignment['p95Distance'],
                           p95TangentAngleDegrees=alignment['p95UnsignedTangentAngleDegrees'], alignment=alignment,
                           sampleMethod='257 samples uniformly spaced by authored polyline arc length; measured against this connected output-edge path.'))
    return result


def validate_surface(source, triangles, positions, faces, target, *, whole_surface=True):
    """Preserve reference limits and require whole-triangle distance bounds.

    Sparse samples remain useful diagnostics and an inexpensive rejection
    screen. Acceptance additionally bounds both possible quad diagonals, since
    nonplanar exported quads can be triangulated differently by OBJ consumers.
    Set whole_surface=False only for intermediate refinement screening.
    """
    source, positions = np.asarray(source), np.asarray(positions)
    base, _, _ = topology(source, triangles.tolist())
    output, _, _ = topology(positions, faces.tolist())
    star = links(faces.tolist())
    st = np.asarray(triangles)
    source_mesh = trimesh.Trimesh(source, st, process=False)
    tolerance = .5 * float(np.sqrt(source_mesh.area / target))
    try:
        ot = triangulate(positions, faces.tolist())
    except ValueError as error:
        # An intermediate fold is a rejected candidate, not an exception that
        # prevents remaining refinement passes or layout seeds from being tried.
        return dict(passed=False, checks=dict(validTriangulation=False), reason=str(error),
                    sampledSurfaceTolerance=tolerance, topology=output, vertexLinks=star,
                    wholeSurfaceDiagonals={}, scope='Rejected before proximity checks: invalid projected polygon triangulation.')
    output_mesh = trimesh.Trimesh(positions, ot, process=False)
    def distance_samples(p, tri, mesh):
        samples = np.r_[p[np.unique(tri)], p[tri].mean(axis=1)]
        stride = max(1, int(np.ceil(len(samples) / 2048)))
        distance = trimesh.proximity.closest_point(mesh, samples[::stride])[1]
        return {'samples': len(distance), 'stride': stride, 'sampledMax': float(distance.max()), 'p95': float(np.percentile(distance, 95))}
    sd = distance_samples(source, st, output_mesh)
    od = distance_samples(positions, ot, source_mesh)
    checks = dict(validTriangulation=True, closed=output['boundaryEdges'] == 0, components=output['faceConnectedComponents'] == base['faceConnectedComponents'],
                  sourceEuler=output['eulerCharacteristic'] == base['eulerCharacteristic'],
                  noIncidenceDefects=all(output[k] == 0 for k in ('unusedVertices', 'nonmanifoldEdges', 'repeatedIndexFaces', 'zeroAreaFanTriangles')),
                  vertexManifold=not star['nonmanifoldVertices'], consistentWinding=star['inconsistentWindingEdges'] == 0,
                  sampledSurface=max(sd['sampledMax'], od['sampledMax']) <= tolerance)
    bounds = {}
    if whole_surface:
        if all(checks.values()):
            for name, a, b in (('02', [0, 1, 2], [0, 2, 3]), ('13', [0, 1, 3], [1, 2, 3])):
                mesh = trimesh.Trimesh(positions, np.r_[faces[:, a], faces[:, b]], process=False)
                bounds[name] = surface_distance(source_mesh, mesh, tolerance)
        checks['wholeSurface'] = bool(bounds) and all(bound['passed'] for bound in bounds.values())
    return {'passed': all(checks.values()), 'checks': checks, 'sourceToOutput': sd, 'outputToSource': od,
            'sampledSurfaceTolerance': tolerance, 'topology': output, 'vertexLinks': star,
            'wholeSurfaceDiagonals': bounds,
            'scope': ('Both quad diagonals require adaptive whole-triangle distance bounds in both directions; budgets reject unresolved bounds. Double-precision checks, separate from intersections.'
                      if whole_surface else 'Intermediate deterministic sparse-sample screen only; not final surface acceptance.')}


def _warpage(positions, faces):
    """Signed tetrahedral volume scaled to a quad's area (a length).

    A nonplanar quad describes different surfaces under its two diagonals.
    This residual reduces that ambiguity; final bounds still check both.
    """
    p = positions[faces]
    cross = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    area = cross + np.cross(p[:, 2] - p[:, 0], p[:, 3] - p[:, 0])
    return np.einsum('ij,ij->i', cross, p[:, 3] - p[:, 0]) / np.maximum(1e-15, np.linalg.norm(area, axis=1))


def _refine(source_mesh, positions, faces, edges, pins, targets, target):
    spacing = np.sqrt(source_mesh.area / target)
    jacobian, cosine = _corners(positions, faces)
    bad = (jacobian.min(axis=1) < .7) | (np.abs(cosine).max(axis=1) > .75)
    bad |= np.abs(_warpage(positions, faces)) > spacing * .05
    vertex_anchor, vertex_error, vertex_triangles = trimesh.proximity.closest_point(source_mesh, positions)
    active = set(faces[bad].ravel()) | set(pins) | set(np.flatnonzero(vertex_error > spacing * .25))
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
    ids = np.array(sorted(active), dtype=int)
    if not len(ids):
        return positions, {'vertices': 0, 'evaluations': 0}
    lookup = np.full(len(positions), -1, dtype=int); lookup[ids] = np.arange(len(ids))
    local_faces = faces[np.any(np.isin(faces, ids), axis=1)]
    local_edges = edges[np.any(np.isin(edges, ids), axis=1)]
    anchor = vertex_anchor[ids]
    normal = source_mesh.face_normals[vertex_triangles[ids]]
    groups = [(len(local_faces) * 4, local_faces)] * 3 + [(len(local_faces), local_faces)]
    groups += [(len(local_faces), local_faces)]
    groups += [(len(local_edges), local_edges)] * 2
    groups += [(len(ids), ids[:, None]), (len(ids) * 3, ids[:, None]), (len(pins) * 3, pins[:, None]), (len(support) * 3, support),
               (len(ids), ids[:, None]), (len(support), support)]
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
    def residual(x):
        q = positions.copy(); q[ids] = x.reshape(-1, 3)
        jacobian, cosine = _corners(q, local_faces)
        length = np.linalg.norm(q[local_edges[:, 1]] - q[local_edges[:, 0]], axis=1)
        delta = q[ids] - anchor
        fl = np.linalg.norm(np.roll(q[local_faces], -1, axis=1) - q[local_faces], axis=2)
        ratio = fl.max(axis=1) / np.maximum(1e-10, fl.min(axis=1))
        surface_delta = (q[support] * barycentric[:, :, None]).sum(axis=1) - support_target
        # Keep movement inside a local surface trust region, in both directions.
        # A tangent-plane residual alone permits large sideways departures from
        # curved areas while fitting a second guide. These soft barriers leave
        # margin inside the unchanged half-edge-length acceptance tolerance.
        return np.r_[np.maximum(.7 - jacobian, 0).ravel() * 60,
                     np.maximum(np.abs(cosine) - .7, 0).ravel(), cosine.ravel() * .1,
                     np.maximum(ratio - 3.5, 0) * 10, _warpage(q, local_faces) / spacing * 8,
                     np.maximum(.4 - length / spacing, 0) * 5,
                     np.maximum(length / spacing - 1.7, 0), (delta * normal).sum(axis=1) / spacing * 6,
                     delta.ravel() / spacing * 2, (q[pins] - targets).ravel() / spacing * 80,
                     surface_delta.ravel() / spacing * 4,
                     np.maximum(np.linalg.norm(delta, axis=1) / spacing - .35, 0) * 40,
                     np.maximum(np.linalg.norm(surface_delta, axis=1) / spacing - .35, 0) * 40]
    result = least_squares(residual, positions[ids].ravel(), jac_sparsity=sparsity.tocsr(), max_nfev=150, ftol=1e-6, xtol=1e-5)
    output = positions.copy(); output[ids] = result.x.reshape(-1, 3)
    return output, {'vertices': len(ids), 'evaluations': result.nfev, 'sourceSupportPoints': len(support)}


def construct(source, triangles, curves, *, target, job, guided_layout=False):
    source, triangles = np.asarray(source, dtype=float), np.asarray(triangles, dtype=int)
    curves = [np.asarray(c, dtype=float) for c in curves]
    for curve in curves:
        if len(curve) < 2 or not np.isfinite(curve).all() or np.any(np.linalg.norm(np.diff(curve, axis=0), axis=1) == 0):
            raise ValueError('Guides need distinct consecutive finite surface samples.')
    source_mesh = trimesh.Trimesh(source, triangles, process=False)
    if not source_mesh.is_watertight or not source_mesh.is_winding_consistent or np.any(source_mesh.area_faces == 0):
        raise ValueError('The surface quad solver requires a closed, consistently wound, nondegenerate source.')
    if curves and guided_layout:
        from guided_layout import construct as construct_guided_layout
        return construct_guided_layout(source, triangles, curves, target=target, job=job)
    blender = find_blender()
    input_path = job / 'quadri-input.json'
    _write(input_path, {'vertices': source.tolist(), 'faces': triangles.tolist()})
    spacing = np.sqrt(source_mesh.area / target)
    history = []
    for seed in range(2):
        _progress(job, 'Building the quad surface layout')
        raw = job / f'quadri-layout-{seed}.json'
        command = [str(blender), '--background', '--threads', '8', '--python', str(ROOT / 'scripts/quadriflow_mesh.py'),
                   '--', '--input', str(input_path), '--output', str(raw), '--target', str(target), '--seed', str(seed)]
        with (job / f'quadri-layout-{seed}.log').open('w', encoding='utf-8') as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if process.returncode or not raw.is_file():
            raise RuntimeError('The quad layout could not be built. The local calculation log was retained.')
        packet = json.loads(raw.read_text(encoding='utf-8'))
        positions, faces = np.asarray(packet['vertices'], dtype=float), np.asarray(packet['faces'], dtype=int)
        if faces.ndim != 2 or faces.shape[1] != 4 or not len(faces) or not np.isfinite(positions).all():
            raise ValueError('The quad layout returned invalid geometry.')
        edges = _edges(faces)
        paths, pin_rows, target_rows = [], [], []
        for curve in curves:
            path, pins, targets = _guide_path(positions, edges, curve, spacing)
            paths.append(path); pin_rows.extend(pins); target_rows.extend(targets)
        pins = np.asarray(pin_rows, dtype=int)
        targets = np.asarray(target_rows, dtype=float).reshape(-1, 3)
        for pin in set(pin_rows):
            shared = targets[pins == pin]
            if np.max(np.linalg.norm(shared - shared[0], axis=1)) > spacing * .1:
                raise ValueError('Two guides compete for the same output vertices. Increase density or separate their paths.')
        for iteration in range(5):
            _progress(job, f'Fitting guides and refining quads · pass {iteration + 1}')
            positions, refinement = _refine(source_mesh, positions, faces, edges, pins, targets, target)
            quality = quad_quality(positions, faces, target)
            validation = validate_surface(source, triangles, positions, faces, target, whole_surface=False)
            fit = _guide_fit(positions, paths, curves)
            intersections = surface_intersections(positions, faces, both_quad_diagonals=True)
            guided = all(p['p95Distance'] <= .20 * spacing and p['p95TangentAngleDegrees'] <= 30 for p in fit)
            if quality['passed'] and validation['passed'] and guided and intersections['passed']:
                _progress(job, 'Checking the full surface and both quad diagonals')
                validation = validate_surface(source, triangles, positions, faces, target)
            history.append(dict(seed=seed, iteration=iteration, refinement=refinement, quality=quality, intersections=intersections,
                                surface=validation, guideFit=[{k: p[k] for k in ('curve', 'p95Distance', 'p95TangentAngleDegrees')} for p in fit]))
            if quality['passed'] and validation['passed'] and guided and intersections['passed']:
                files = [Path(__file__), ROOT / 'quad_quality.py', ROOT / 'surface_intersections.py', ROOT / 'surface_distance.py', ROOT / 'scripts/quadriflow_mesh.py']
                metadata = dict(backend=BACKEND, nativeComparisonPerformed=False, generalAlgorithmRecovered=False,
                                target=target, guideMode=2, closedValidation=validation, guidePaths=fit, intersectionValidation=intersections,
                                outputCreases=output_creases(positions, faces.tolist()), refinementHistory=history,
                                layoutEngine=dict(name='Blender QuadriFlow', version=packet['blenderVersion'], executable=str(blender), seed=seed),
                                sourceHashes={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                                limitations=['Engineering layout and fitting route, not recovered native equivalence.',
                                             'Approximate surface and guide fitting; small details can be smoothed at coarse targets.',
                                             'Surface bounds and intersection predicates use double precision; topology and geometric contact are checked separately.',
                                             'Overlapping or unresolved guide paths reject; general crease/attribute transfer is not implemented.'])
                _write(job / 'surface-solver.json', metadata)
                return positions, faces.tolist(), metadata
    def failures(attempt):
        reasons = []
        if not attempt['quality']['passed']:
            reasons.append('quad quality')
        if not attempt['surface']['passed']:
            reasons.append('source-surface accuracy')
        if not attempt['intersections']['passed']:
            reasons.append('face intersections, including overlaps between adjacent faces')
        for guide in attempt['guideFit']:
            if guide['p95Distance'] > .2 * spacing or guide['p95TangentAngleDegrees'] > 30:
                reasons.append(f"guide {guide['curve'] + 1} alignment")
        return reasons
    closest = min(history, key=lambda attempt: len(failures(attempt)))
    reasons = failures(closest)
    _write(job / 'surface-solver-failure.json', {'attempts': history, 'closestAttempt': {'seed': closest['seed'], 'iteration': closest['iteration'], 'failedRequirements': reasons}})
    _write(job / 'failed-surface-candidate.json', {'vertices': positions.tolist(), 'faces': faces.tolist()})
    raise ValueError('Generation failed: the closest candidate did not meet the limits for ' + ', '.join(reasons)
                     + '. No new mesh was accepted; your source and guides are unchanged.')
