"""Connected feature-row assessment and candidate ranking: engineering policy.

The recovered guide/integer stages motivate assessing ordered edge rows, but
this score is not a recovered ZRemesher objective. Caller-supplied tolerances
reuse existing feature acceptance policy. Source-edge graph distances are
conservative approximations, not the recovered attachment walk. Exact engine
paths and source-face attachments may be supplied instead of inferred paths.
"""
from collections import Counter, defaultdict
from heapq import heappop, heappush
import numpy as np
import trimesh

POLICY = 'connected-feature-rows-v1'
RANK_ORDER = ('unrealizedRows', 'mergedPathPairs', 'collapsedLoopPairs', 'junctionMismatches',
              'tangentError', 'distanceP95OverSpacing', 'spacingVariation',
              'interiorPoleExcess', 'targetRelativeError')


def graph_paths(edges):
    """Deterministic chains split at non-degree-two vertices; loops repeat start."""
    remaining = {tuple(sorted(map(int, e))) for e in np.asarray(edges, int).reshape(-1, 2)}
    if any(a == b for a, b in remaining):
        raise ValueError('Feature edge has identical endpoints.')
    adjacent = defaultdict(set)
    for a, b in remaining:
        adjacent[a].add(b)
        adjacent[b].add(a)
    paths = []
    starts = sorted(v for v in adjacent if len(adjacent[v]) != 2) + sorted(adjacent)
    for start in starts:
        for following in sorted(adjacent[start]):
            edge = tuple(sorted((start, following)))
            if edge not in remaining:
                continue
            remaining.remove(edge)
            path = [start, following]
            while len(adjacent[path[-1]]) == 2 and path[-1] != start:
                candidates = [v for v in sorted(adjacent[path[-1]])
                              if tuple(sorted((path[-1], v))) in remaining]
                if not candidates:
                    break
                following = candidates[0]
                remaining.remove(tuple(sorted((path[-1], following))))
                path.append(following)
            paths.append(path)
    return paths


def _arc(points):
    return np.r_[0., np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]


def _at(points, arc, parameters, closed=False):
    t = np.asarray(parameters, float)
    t = np.mod(t, arc[-1]) if closed else np.clip(t, 0., arc[-1])
    return np.stack([np.interp(t, arc, points[:, i]) for i in range(3)], axis=-1)


def _nearest(points, curve):
    """Exact point-to-segment distance and ordered polyline arclength."""
    a, delta = curve[:-1], np.diff(curve, axis=0)
    length = np.linalg.norm(delta, axis=1)
    arc = np.r_[0., np.cumsum(length)]
    distance, parameter = [], []
    for first in range(0, len(points), 256):
        p = np.asarray(points)[first:first + 256]
        t = np.clip(((p[:, None] - a) * delta).sum(2) / (length * length), 0., 1.)
        squared = ((p[:, None] - a - t[:, :, None] * delta) ** 2).sum(2)
        ids, rows = squared.argmin(1), np.arange(len(p))
        distance.extend(np.sqrt(squared[rows, ids]))
        parameter.extend(arc[ids] + t[rows, ids] * length[ids])
    return np.asarray(distance), np.asarray(parameter)


def _samples(points, step):
    arc = _arc(points)
    # Preserve original corners in addition to uniformly spaced samples.
    t = np.unique(np.r_[arc, np.linspace(0., arc[-1], int(np.ceil(arc[-1] / step)) + 1)])
    return _at(points, arc, t)


def _source_distances(adjacency, seeds):
    distance = np.full(len(adjacency), np.inf)
    queue = []
    for vertex, value in seeds.items():
        distance[vertex] = value
        heappush(queue, (value, vertex))
    while queue:
        value, vertex = heappop(queue)
        if value != distance[vertex]:
            continue
        for following, length in adjacency[vertex]:
            candidate = value + length
            if candidate < distance[following]:
                distance[following] = candidate
                heappush(queue, (candidate, following))
    return distance


def prepare(source, triangles, feature_edges, curves, spacing, *, max_distance,
            sample_spacing, paths=None):
    """Prepare source chains once. Explicit paths replace inferred paths.

    Each explicit path has id/kind and source vertices or geometric points,
    optionally closed. max_distance and sample_spacing are caller policies in
    source units. Defaults assign crease:N / guide:N ids.
    """
    source, triangles = np.asarray(source, float), np.asarray(triangles, int)
    if spacing <= 0 or max_distance < 0 or sample_spacing <= 0:
        raise ValueError('Invalid feature-row distance or sampling scale.')
    mesh = trimesh.Trimesh(source, triangles, process=False)
    edges = np.unique(np.sort(np.stack((triangles, np.roll(triangles, -1, axis=1)), axis=2)
                              .reshape(-1, 2), axis=1), axis=0)
    adjacency = [[] for _ in source]
    for a, b in edges:
        length = float(np.linalg.norm(source[a] - source[b]))
        adjacency[a].append((int(b), length))
        adjacency[b].append((int(a), length))
    if paths is None:
        paths = [dict(id=f'crease:{i}', kind='crease', vertices=path, closed=path[0] == path[-1])
                 for i, path in enumerate(graph_paths(feature_edges))]
        paths += [dict(id=f'guide:{i}', kind='guide', points=curve) for i, curve in enumerate(curves)]
    records = []
    for index, spec in enumerate(paths):
        ids = spec.get('vertices', spec.get('sourceVertexIds'))
        points = np.asarray(source[np.asarray(ids, int)] if ids is not None else spec['points'], float)
        if len(points) < 2 or not np.isfinite(points).all():
            raise ValueError('A feature path requires at least two finite points.')
        closed = bool(spec.get('closed', np.array_equal(points[0], points[-1])))
        if closed and not np.array_equal(points[0], points[-1]):
            points = np.r_[points, points[:1]]
            if ids is not None:
                ids = list(ids) + [ids[0]]
        keep = np.r_[True, np.linalg.norm(np.diff(points, axis=0), axis=1) > 0]
        points = points[keep]
        if ids is not None:
            ids = np.asarray(ids, int)[keep].tolist()
        if len(points) < (4 if closed else 2):
            raise ValueError('A closed feature path needs three distinct points.')
        samples = _samples(points, sample_spacing)
        seeds = {int(v): 0. for v in ids} if ids is not None else {}
        face_samples = {}
        if ids is None:
            locations, _, owners = trimesh.proximity.closest_point(mesh, samples)
            for point, owner, triangle in zip(locations, owners, triangles[owners]):
                face_samples.setdefault(int(owner), []).append(point)
                for vertex in triangle:
                    value = float(np.linalg.norm(point - source[vertex]))
                    seeds[int(vertex)] = min(seeds.get(int(vertex), np.inf), value)
        records.append(dict(id=spec.get('id', index), kind=spec.get('kind', 'crease'),
                            sourceVertices=ids, points=points, closed=closed, arc=_arc(points),
                            samples=samples, faceSamples=face_samples, intrinsic=_source_distances(adjacency, seeds)))
    if len({str(p['id']) for p in records}) != len(records):
        raise ValueError('Feature path ids must be unique.')
    face_neighbors = [set() for _ in triangles]
    for a, b in mesh.face_adjacency:
        face_neighbors[int(a)].add(int(b))
        face_neighbors[int(b)].add(int(a))
    return dict(source=source, triangles=triangles, mesh=mesh, paths=records, faceNeighbors=face_neighbors,
                spacing=float(spacing), maxDistance=float(max_distance), sampleSpacing=float(sample_spacing))



def _straight_surface_connection(prepared, point, owner, target):
    """Exact flat-surface shortcut, with an explicit connected triangle walk.

    A nearest feature point may lie across a neighboring triangle even when
    detouring through mesh vertices is expensive. Clip the straight segment to
    coplanar source triangles, then require connected interval coverage from
    the known attachment face. Holes, detached sheets and folds cannot bridge
    this walk. Tolerances are coordinate ULP accumulation, not a distance band.
    """
    source, triangles = prepared['source'], prepared['triangles']
    scale = float(np.abs(source).max())
    epsilon = float(np.spacing(scale)) * len(source)
    bounds = np.r_[np.minimum(point, target) - epsilon, np.maximum(point, target) + epsilon]
    candidates = list(prepared['mesh'].triangles_tree.intersection(bounds))
    if owner not in candidates:
        candidates.append(int(owner))
    candidate_triangles = source[triangles[candidates]]
    normals = prepared['mesh'].face_normals[candidates]
    coplanar = ((np.abs(((point - candidate_triangles[:, 0]) * normals).sum(1)) <= epsilon)
                & (np.abs(((target - candidate_triangles[:, 0]) * normals).sum(1)) <= epsilon))
    candidates = np.asarray(candidates, int)[coplanar]
    candidate_triangles = candidate_triangles[coplanar]
    if not len(candidates):
        return False
    first = trimesh.triangles.points_to_barycentric(candidate_triangles, np.broadcast_to(point, (len(candidates), 3)))
    last = trimesh.triangles.points_to_barycentric(candidate_triangles, np.broadcast_to(target, (len(candidates), 3)))
    unit_epsilon = np.finfo(float).eps * len(source)
    intervals = {}
    for face, a, b in zip(candidates, first, last):
        low, high = 0., 1.
        for coordinate, change in zip(a, b - a):
            if abs(change) <= unit_epsilon:
                if coordinate < -unit_epsilon:
                    high = -1.
                    break
            elif change > 0:
                low = max(low, -coordinate / change)
            else:
                high = min(high, -coordinate / change)
        if low <= high + unit_epsilon and high >= -unit_epsilon and low <= 1. + unit_epsilon:
            intervals[int(face)] = (max(0., low), min(1., high))
    if owner not in intervals or intervals[owner][0] > unit_epsilon:
        return False
    seen, queue = {int(owner)}, [int(owner)]
    while queue:
        face = queue.pop()
        low, high = intervals[face]
        if high >= 1. - unit_epsilon:
            return True
        for following in prepared['faceNeighbors'][face]:
            if following in seen or following not in intervals:
                continue
            next_low, next_high = intervals[following]
            if max(low, next_low) <= min(high, next_high) + unit_epsilon:
                seen.add(following)
                queue.append(following)
    return False


def _intrinsic(prepared, path, locations, owners):
    triangles = prepared['triangles'][owners]
    points = prepared['source'][triangles]
    result = (path['intrinsic'][triangles] + np.linalg.norm(points - locations[:, None], axis=2)).min(1)
    ids = path['sourceVertices']
    if ids is not None:
        feature = {tuple(sorted((a, b))) for a, b in zip(ids[:-1], ids[1:])}
        # Exact within incident source faces; avoids graph detours along long edges.
        for corner in range(3):
            a, b = triangles[:, corner], triangles[:, (corner + 1) % 3]
            selected = np.array([tuple(sorted((int(x), int(y)))) in feature for x, y in zip(a, b)])
            if not selected.any():
                continue
            delta = prepared['source'][b[selected]] - prepared['source'][a[selected]]
            offset = locations[selected] - prepared['source'][a[selected]]
            t = np.clip((offset * delta).sum(1) / (delta * delta).sum(1), 0., 1.)
            result[selected] = np.minimum(result[selected], np.linalg.norm(offset - t[:, None] * delta, axis=1))
    else:
        # Authored guide samples have source-face provenance. Within that face
        # direct distances avoid a conservative detour to remote triangle corners.
        for owner, samples in path['faceSamples'].items():
            selected = np.flatnonzero(owners == owner)
            if len(selected):
                direct = np.linalg.norm(locations[selected, None] - np.asarray(samples)[None], axis=2).min(1)
                result[selected] = np.minimum(result[selected], direct)
    # Repair false rejections from graph detours with a verified straight
    # surface segment, rather than inflating the caller's corridor tolerance.
    direct, parameters = _nearest(locations, path['points'])
    for index in np.flatnonzero((result > prepared['maxDistance']) & (direct <= prepared['maxDistance'])):
        target = _at(path['points'], path['arc'], parameters[index])
        if _straight_surface_connection(prepared, locations[index], int(owners[index]), target):
            result[index] = direct[index]
    return result


def _register(prepared, path, vertices, edges, intrinsic):
    distance, parameter = _nearest(vertices, path['points'])
    allowed = (distance <= prepared['maxDistance']) & (intrinsic <= prepared['maxDistance'])
    if not allowed.any():
        return []
    candidates = np.flatnonzero(allowed)
    start = int(candidates[np.argmin(np.linalg.norm(vertices[candidates] - path['points'][0], axis=1))])
    closed, total = path['closed'], path['arc'][-1]
    end = start if closed else int(candidates[np.argmin(np.linalg.norm(vertices[candidates] - path['points'][-1], axis=1))])
    if not closed and start == end:
        return []
    if closed:
        parameter = (parameter - parameter[start]) % total
    count, layers = len(vertices), 2 if closed else 1
    adjacency = [[] for _ in range(count * layers)]
    for a, b in edges:
        if not (allowed[a] and allowed[b]):
            continue
        step = parameter[b] - parameter[a]
        if closed:
            step = (step + total / 2) % total - total / 2
        if step < 0:
            a, b, step = b, a, -step
        if step == 0:
            continue
        length = float(np.linalg.norm(vertices[b] - vertices[a]))
        if length == 0:
            continue
        midpoint = _nearest((vertices[a] + vertices[b])[None] / 2, path['points'])[1][0]
        # One-face tangent window, capped at half a closed loop so its two
        # endpoints cannot coincide after wrapping (explicit ranking policy).
        half = min(prepared['spacing'], total / 2) / 2 if closed else prepared['spacing'] / 2
        tangent = (_at(path['points'], path['arc'], midpoint + half, closed)
                   - _at(path['points'], path['arc'], midpoint - half, closed))
        norm = float(np.linalg.norm(tangent))
        loss = 1. - float(np.clip(np.dot(vertices[b] - vertices[a], tangent) / (length * norm), -1., 1.)) ** 2 if norm else 1.
        # Explicit path policy: integrated tangent error, then length, then
        # integrated proximity. A lexicographic tuple has no fitted weights.
        cost = (length * loss, length, length * (distance[a] + distance[b]) / 2)
        wrap = int(round((step - (parameter[b] - parameter[a])) / total)) if closed else 0
        for layer in range(layers):
            destination = layer + wrap
            if 0 <= destination < layers:
                adjacency[layer * count + a].append((destination * count + b, cost))
    end += count if closed else 0
    best, predecessor = {start: (0., 0., 0.)}, {}
    queue = [(best[start], start)]
    while queue:
        cost, current = heappop(queue)
        if cost != best[current]:
            continue
        if current == end:
            result = [current]
            while result[-1] != start:
                result.append(predecessor[result[-1]])
            result = [int(v % count) for v in result[::-1]]
            unique = result[:-1] if closed else result
            return result if len(set(unique)) == len(unique) and len(unique) >= (3 if closed else 2) else []
        for following, addition in adjacency[current]:
            value = tuple(a + b for a, b in zip(cost, addition))
            if value < best.get(following, (np.inf, np.inf, np.inf)):
                best[following], predecessor[following] = value, current
                heappush(queue, (value, following))
    return []


def _topology(faces):
    incidence, neighbors, incident_faces = Counter(), defaultdict(set), defaultdict(list)
    for face in faces:
        for vertex in face:
            incident_faces[int(vertex)].append(len(face))
        for a, b in zip(face, np.roll(face, -1)):
            a, b = int(a), int(b)
            incidence[tuple(sorted((a, b)))] += 1
            neighbors[a].add(b)
            neighbors[b].add(a)
    boundary = {v for edge, count in incidence.items() if count == 1 for v in edge}
    interior = set(neighbors) - boundary
    quad_interior = [v for v in interior if all(n == 4 for n in incident_faces[v])]
    poles = [v for v in quad_interior if len(neighbors[v]) != 4]
    histogram = lambda ids: {str(k): int(v) for k, v in sorted(Counter(len(neighbors[i]) for i in ids).items())}
    return dict(interiorValence=histogram(interior), interiorAllQuadValence=histogram(quad_interior),
                boundaryValence=histogram(boundary), interiorPoleVertices=sorted(poles),
                interiorPoleCount=len(poles), interiorPoleExcess=sum(abs(len(neighbors[v]) - 4) for v in poles),
                triangleAdjacentVertices=sum(any(n == 3 for n in values) for values in incident_faces.values()),
                boundaryVertices=len(boundary)), np.asarray(sorted(incidence), int).reshape(-1, 2)



def _overlapping_source_support(a, b):
    """Whether two source polylines share a positive-length straight segment.

    Shared junction points alone do not authorize shared output edges. The
    numerical tolerance is accumulated coordinate ULPs, not a geometric band.
    It only accommodates arithmetic during projected guide embedding.
    """
    scale = max(float(np.abs(a).max()), float(np.abs(b).max()))
    tolerance = float(np.spacing(scale)) * (len(a) + len(b))
    for start, end in zip(a[:-1], a[1:]):
        delta = end - start
        length = float(np.linalg.norm(delta))
        unit = delta / length
        projection = (b - start) @ unit
        residual = np.linalg.norm((b - start) - projection[:, None] * unit, axis=1)
        for i in range(len(b) - 1):
            if max(residual[i], residual[i + 1]) > tolerance:
                continue
            low, high = sorted((projection[i], projection[i + 1]))
            if min(length, high) - max(0., low) > tolerance:
                return True
    return False


def measure(prepared, vertices, faces, *, paths=None, source_faces=None):
    """JSON-safe row report; exact engine paths may replace graph inference.

    Supplied paths contain feature/id, vertices (output ids), closed. Source
    faces may give one attachment triangle id per output vertex. Missing rows
    are explicit and cannot be mistaken for a zero-error realization.
    """
    vertices = np.asarray(vertices, float)
    topology, edges = _topology(faces)
    edge_set = set(map(tuple, edges.tolist()))
    if source_faces is None:
        locations, _, owners = trimesh.proximity.closest_point(prepared['mesh'], vertices)
    else:
        owners = np.asarray(source_faces, int)
        if owners.shape != (len(vertices),):
            raise ValueError('source_faces must have one triangle id per output vertex.')
        locations = trimesh.triangles.closest_point(prepared['source'][prepared['triangles'][owners]], vertices)
    supplied = {str(p.get('feature', p.get('id'))): p for p in paths or []}
    rows, all_distances, variations = [], [], []
    tangent_sum, tangent_weight = 0., 0.
    for path in prepared['paths']:
        intrinsic = _intrinsic(prepared, path, locations, owners)
        given = supplied.get(str(path['id']))
        ids = list(map(int, given['vertices'])) if given is not None else _register(prepared, path, vertices, edges, intrinsic)
        closed = path['closed']
        if closed and ids and ids[0] != ids[-1]:
            ids.append(ids[0])
        if not closed and len(ids) >= 2 and min(ids) >= 0 and max(ids) < len(vertices):
            forward = np.linalg.norm(vertices[ids[0]] - path['points'][0]) + np.linalg.norm(vertices[ids[-1]] - path['points'][-1])
            reverse = np.linalg.norm(vertices[ids[-1]] - path['points'][0]) + np.linalg.norm(vertices[ids[0]] - path['points'][-1])
            if reverse < forward:
                ids.reverse()
        unique, errors = ids[:-1] if closed else ids, []
        if len(unique) < (3 if closed else 2):
            errors.append('missing ordered output path')
        elif min(ids) < 0 or max(ids) >= len(vertices) or len(set(unique)) != len(unique):
            errors.append('invalid or repeated output vertex')
        elif any(tuple(sorted((a, b))) not in edge_set for a, b in zip(ids[:-1], ids[1:])):
            errors.append('output path is disconnected')
        row = dict(feature=path['id'], id=path['id'], kind=path['kind'], closed=closed, vertices=ids,
                   registration='engine' if given is not None else 'directed-graph', errors=errors)
        if errors:
            row['realized'] = False
            rows.append(row)
            continue
        points = vertices[ids]
        distances = np.r_[_nearest(path['samples'], points)[0],
                          _nearest(_samples(points, prepared['sampleSpacing']), path['points'])[0]]
        all_distances.extend(distances.tolist())
        if distances.max() > prepared['maxDistance']:
            errors.append('row leaves feature distance corridor')
        if intrinsic[unique].max() > prepared['maxDistance']:
            errors.append('row leaves source-sheet corridor')
        _, parameters = _nearest(points, path['points'])
        increments = np.diff(parameters)
        if closed:
            increments = (increments + path['arc'][-1] / 2) % path['arc'][-1] - path['arc'][-1] / 2
        if closed and not np.isclose(abs(increments.sum()), path['arc'][-1], rtol=np.finfo(float).eps * len(increments), atol=0.):
            errors.append('row does not wind once around feature')
        nonzero = increments[increments != 0]
        if len(nonzero) and np.any(nonzero > 0) and np.any(nonzero < 0):
            errors.append('row reverses feature order')
        delta = np.diff(points, axis=0)
        lengths = np.linalg.norm(delta, axis=1)
        midpoints = _nearest((points[:-1] + points[1:]) / 2, path['points'])[1]
        half = min(prepared['spacing'], path['arc'][-1] / 2) / 2 if closed else prepared['spacing'] / 2
        tangents = (_at(path['points'], path['arc'], midpoints + half, closed)
                    - _at(path['points'], path['arc'], midpoints - half, closed))
        denominator = lengths * np.linalg.norm(tangents, axis=1)
        cosine = np.divide((delta * tangents).sum(1), denominator, out=np.zeros_like(lengths), where=denominator > 0)
        losses = 1. - np.clip(cosine, -1., 1.) ** 2
        tangent_sum += float(np.dot(lengths, losses))
        tangent_weight += float(lengths.sum())
        if np.any(lengths == 0):
            errors.append('zero-length row edge')
            variation = 0.
        else:
            pairs = np.roll(lengths, -1) / lengths if closed else lengths[1:] / lengths[:-1]
            variation = float(np.mean(np.abs(np.log(pairs)))) if len(pairs) else 0.
            variations.append(variation)
        row.update(realized=not errors, distanceP95=float(np.percentile(distances, 95)),
                   distanceMax=float(distances.max()), sourceSheetDistanceMax=float(intrinsic[unique].max()),
                   tangentError=float(np.dot(lengths, losses) / lengths.sum()) if lengths.sum() else 1.,
                   spacingVariation=variation)
        rows.append(row)
    collapsed, merged = [], []
    for i, a in enumerate(rows):
        if not a['vertices']:
            continue
        a_edges = {tuple(sorted(e)) for e in zip(a['vertices'][:-1], a['vertices'][1:])}
        for j, b in enumerate(rows[:i]):
            if not b['vertices']:
                continue
            b_edges = {tuple(sorted(e)) for e in zip(b['vertices'][:-1], b['vertices'][1:])}
            shared = a_edges & b_edges
            if not shared:
                continue
            overlap = _overlapping_source_support(prepared['paths'][i]['points'], prepared['paths'][j]['points'])
            if not overlap:
                merged.append(dict(features=[b['feature'], a['feature']], edges=[list(e) for e in sorted(shared)]))
                if a['closed'] and b['closed'] and a_edges == b_edges:
                    collapsed.append([b['feature'], a['feature']])
    junctions = defaultdict(dict)
    source_neighbors = defaultdict(set)
    for path, row in zip(prepared['paths'], rows):
        source_ids = path['sourceVertices']
        if source_ids is None:
            continue
        for a, b in zip(source_ids[:-1], source_ids[1:]):
            source_neighbors[a].add(b)
            source_neighbors[b].add(a)
        if not row['vertices']:
            continue
        if path['closed']:
            # A cycle has no distinguished output start. Shared source junctions
            # must be the unique common output vertex of the incident rows,
            # rather than a nearest-coordinate guess or row.vertices[0].
            junctions[source_ids[0]][path['id']] = (set(row['vertices'][:-1]), True)
        else:
            junctions[source_ids[0]][path['id']] = ({row['vertices'][0]}, False)
            junctions[source_ids[-1]][path['id']] = ({row['vertices'][-1]}, False)
    mismatches, ambiguous, junction_matches = 0, 0, []
    for source_vertex, incidences in junctions.items():
        if len(incidences) < 2:
            continue
        if all(closed for _, closed in incidences.values()) and len(source_neighbors[source_vertex]) == 2:
            # Coincident copies of one loop share an arbitrary source start,
            # which is not a branch junction.
            continue
        common = set.intersection(*(vertices for vertices, _ in incidences.values()))
        if len(common) != 1:
            mismatches += 1
            ambiguous += len(common) > 1
        junction_matches.append(dict(sourceVertex=int(source_vertex),
                                     outputVertices=sorted(common),
                                     status='matched' if len(common) == 1 else 'ambiguous' if common else 'missing'))
    return dict(policy=POLICY, rankOrder=list(RANK_ORDER), paths=rows, pathCount=len(rows),
                passed=all(row['realized'] for row in rows) and not merged and not mismatches,
                realizedRows=sum(row['realized'] for row in rows), unrealizedRows=sum(not row['realized'] for row in rows),
                missingLoops=sum(row['closed'] and not row['realized'] for row in rows),
                mergedPathPairs=len(merged), mergedRows=merged, sharedRowEdges=sum(len(pair['edges']) for pair in merged),
                collapsedLoopPairs=len(collapsed), collapsedLoops=collapsed, junctionMismatches=int(mismatches),
                junctionAmbiguities=int(ambiguous), junctionMatches=junction_matches,
                tangentError=tangent_sum / tangent_weight if tangent_weight else 0.,
                distanceP95OverSpacing=float(np.percentile(all_distances, 95) / prepared['spacing']) if all_distances else 0.,
                spacingVariation=float(np.mean(variations)) if variations else 0., topology=topology,
                interiorPoleExcess=topology['interiorPoleExcess'],
                maxDistance=prepared['maxDistance'], sampleSpacing=prepared['sampleSpacing'],
                attachment='provided-source-faces' if source_faces is not None else 'nearest-source-face',
                limitations=['Engineering ranking, not a recovered native objective.',
                             'Source-edge geodesics are conservative; flat shortcuts require connected source-triangle coverage.',
                             'Distances are sampled; independent surface/topology/intersection gates remain required.',
                             'Boundary valences are reported separately, not treated as interior poles.'])


def rank_key(report, *, target=None, face_count=None):
    """Lower is better; exact lexicographic policy without scalar weights."""
    count_error = abs(face_count - target) / target if target and face_count is not None else 0.
    return tuple(report[key] for key in RANK_ORDER[:-1]) + (float(count_error),)

