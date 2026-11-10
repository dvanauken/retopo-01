"""One continuous output edge loop along each authored guide.

The guide check used to accept any connected output edge path that stayed near
the guide (curved_quad._guide_path and guides_pass). A path that steps sideways
from one edge loop to the next at most of its vertices passed, as long as its
vertices had been pulled onto the curve: job 483afe83 (island 6, request 200)
turned at 8 of the 13 vertices of its guide path and was accepted.

ZRemesher at Curves Strength 100 cuts the guide into the source and registers
the cut edges in the integer solve, so one edge loop runs along the guide
(recovered 0x28b920; extraction keeps it, 0x2a7cc0). This module asks for that
outcome: one connected, forward-ordered output edge path per guide that never
turns from one loop onto another, measured in requested faces the way
crease_rows measures rim rows.

A path turns at a vertex when the edge it arrives by and the edge it leaves by
border the same face. Through a regular vertex that is exactly leaving the
loop; an interior vertex of valence three cannot be passed without a turn.

A guide with a sharp corner is the exception. A loop cannot bend there, and
native does not ask it to: the guide's parameter edges fall into groups, one
field axis each (0x28b920), and at the corner the guide passes from one axis to
the other. In the mesh that is one turn at the corner vertex. So one turn is
excused at each corner of the guide itself, where the guide's direction changes
by CORNER_DEGREES or more from the face before a point to the face after it.

Evidence level. The requirement (a loop on the guide) is native behaviour at
strength 100. The limits are this application's existing numbers, reused from
crease_rows with their meaning there; nothing here is recovered native
arithmetic, and native applies no acceptance test of its own.
"""
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from crease_rows import (find_row, measure_path, _nearest, _arc, _at, _samples,
                         ROW_P95_FACES, ROW_MAX_FACES, ROW_END_FACES, ROW_TANGENT_DEGREES)

POLICY = 'guide-rows-v2'
# Limits: crease_rows' numbers with the same meaning (0.25 h at the 95th percentile, 0.5 h
# maximum, 1 h in the last face of an open end, 30 degrees over one face), plus no turns.
GUIDE_TURNS = 0
# Engineering choice (native has no angle here: its axis groups come out of the solved field).
# A cross field repeats every 90 degrees, so past 45 the other axis of the cross is the nearer
# one: a bend of the guide of 45 degrees or more from one face to the next is a corner, where the loop
# along the guide changes family and the path may turn once.
CORNER_DEGREES = 45.
CORNER_REACH_FACES = .5   # a path vertex within the half-face row maximum of a corner is at that corner


def _face_list(faces):
    return [[int(v) for v in face] for face in faces]


def edge_faces(faces):
    """Faces on each undirected edge; faces may be quads or mixed polygons."""
    owners = {}
    for index, face in enumerate(_face_list(faces)):
        for a, b in zip(face, face[1:] + face[:1]):
            owners.setdefault((min(a, b), max(a, b)), set()).add(index)
    return owners


def turns(path, owners, closed=False):
    """Path positions at which the path turns: arriving and leaving edge border one face."""
    result = []
    triples = list(enumerate(zip(path[:-2], path[1:-1], path[2:]), 1))
    if closed and len(path) > 3:
        triples.append((0, (path[-2], path[0], path[1])))
    for position, (a, b, c) in triples:
        if owners.get((min(a, b), max(a, b)), set()) & owners.get((min(b, c), max(b, c)), set()):
            result.append(position)
    return sorted(result)


def corners(curve, closed, spacing):
    """Corners of a guide: arc-length intervals over which its direction changes by CORNER_DEGREES or more across one face.

    The change at a point is the angle between the chord over the face before
    it and the chord over the face after it (one-face chords, as the direction
    limit uses, so the sub-face steps of a drawn stroke are not corners). An
    open guide has no corner within one face of its ends.
    """
    curve = np.asarray(curve, float)
    arc = _arc(curve)
    total = float(arc[-1])
    if total <= spacing:
        return []
    samples = _samples(curve, spacing)
    positions = _arc(samples)
    half = spacing   # chord length on each side

    def at(parameters):
        return _at(curve, arc, np.mod(parameters, total) if closed else np.clip(parameters, 0., total))
    before = samples - at(positions - half)
    after = at(positions + half) - samples
    norms = np.linalg.norm(before, axis=1) * np.linalg.norm(after, axis=1)
    cosine = np.divide((before * after).sum(1), norms, out=np.ones(len(samples)), where=norms > 0)
    angle = np.degrees(np.arccos(np.clip(cosine, -1, 1)))
    sharp = angle >= CORNER_DEGREES
    if not closed:
        sharp &= (positions >= half) & (positions <= total - half)
    zones, start = [], None
    for index, flag in enumerate(sharp):
        if flag and start is None:
            start = index
        if start is not None and (not flag or index == len(sharp) - 1):
            end = index if flag else index - 1
            zones.append((float(positions[start]), float(positions[end])))
            start = None
    return zones


def _corner_of(parameter, zones, spacing, total=None):
    """Index of the corner a curve parameter belongs to, or -1."""
    reach = CORNER_REACH_FACES * spacing
    for index, (low, high) in enumerate(zones):
        if low - reach <= parameter <= high + reach:
            return index
        if total is not None and (parameter + total <= high + reach or parameter - total >= low - reach):
            return index
    return -1


def excused(path, turned, vertices, curve, closed, spacing):
    """The turns of a path that are corners of the guide itself: at most one per corner."""
    zones = corners(curve, closed, spacing)
    if not zones or not turned:
        return []
    ids = [path[position] for position in turned]
    _, parameter = _nearest(np.asarray(vertices, float)[ids], np.asarray(curve, float))
    total = float(_arc(np.asarray(curve, float))[-1]) if closed else None
    used, result = set(), []
    for position, value in zip(turned, parameter):
        corner = _corner_of(float(value), zones, spacing, total)
        if corner >= 0 and corner not in used:
            used.add(corner)
            result.append(position)
    return result


def find_loop(vertices, faces, curve, spacing):
    """Cheapest connected output edge path along an open curve that turns only at the guide's own corners, or [].

    The costs, the forward-order rule, the one-face reach and the price of
    stopping short of the curve ends are find_row's (crease_rows). The search
    runs over directed edges so that a step may follow another only when the
    two do not border one face, or when the vertex between them is at a corner
    of the guide.
    """
    vertices = np.asarray(vertices, float)
    curve = np.asarray(curve, float)
    owners = edge_faces(faces)
    distance, parameter = _nearest(vertices, curve)
    zones = corners(curve, False, spacing)
    cornered = np.array([_corner_of(float(t), zones, spacing) >= 0 for t in parameter]) if zones else np.zeros(len(vertices), bool)
    if float(_arc(curve)[-1]) <= 0:
        return []
    allowed = distance <= ROW_END_FACES * spacing
    directed = [(a, b) for a, b in owners if allowed[a] and allowed[b]]
    directed = [(a, b) for a, b in directed + [(b, a) for a, b in directed]
                if parameter[b] - parameter[a] >= 0 and np.linalg.norm(vertices[b] - vertices[a]) > 0]
    if not directed:
        return []
    index = {pair: i for i, pair in enumerate(directed)}
    leaving = {}
    for i, (a, _) in enumerate(directed):
        leaving.setdefault(a, []).append(i)

    def weight(a, b):
        return float(np.linalg.norm(vertices[b] - vertices[a]) * (1 + 40 * ((distance[a] + distance[b]) * .5 / spacing) ** 2))

    def uncovered(reach):
        return reach + 40 * reach ** 3 / (3 * spacing ** 2)
    count = len(directed)
    origin, sink = count, count + 1
    rows, cols, costs = [], [], []
    for i, (a, b) in enumerate(directed):
        rows.append(origin)
        cols.append(i)
        costs.append(uncovered(float(np.linalg.norm(vertices[a] - curve[0]))) + weight(a, b))
        rows.append(i)
        cols.append(sink)
        costs.append(uncovered(float(np.linalg.norm(vertices[b] - curve[-1]))))
        arriving = owners[(min(a, b), max(a, b))]
        for j in leaving.get(b, ()):
            c = directed[j][1]
            if c == a or (not cornered[b] and arriving & owners[(min(b, c), max(b, c))]):
                continue
            rows.append(i)
            cols.append(j)
            costs.append(weight(b, c))
    graph = csr_matrix((np.maximum(costs, 1e-300), (rows, cols)), shape=(count + 2, count + 2))
    cost, predecessor = dijkstra(graph, indices=origin, return_predecessors=True)
    if not np.isfinite(cost[sink]):
        return []
    states, current = [], int(predecessor[sink])
    while current != origin:
        states.append(current)
        current = int(predecessor[current])
    states.reverse()
    path = [directed[states[0]][0]] + [directed[s][1] for s in states]
    return path if len(set(path)) == len(path) and len(path) >= 2 else []


def measure(vertices, faces, curves, spacing):
    """Guide report: every authored guide needs one continuous, non-turning output edge loop.

    An open guide passes on its cheapest non-turning path when that path meets
    every limit. Otherwise the cheapest connected path (find_row) is reported
    with its turns, so a zig-zag chain shows as turns rather than as a short
    stray loop. A closed guide is measured on its cheapest connected loop only.
    `turns` counts the turns that are not corners of the guide itself; one turn
    per guide corner is excused and reported as `cornerTurns`.
    """
    vertices = np.asarray(vertices, float)
    limits = dict(rowP95=ROW_P95_FACES * spacing, rowMax=ROW_MAX_FACES * spacing, rowEndMax=ROW_END_FACES * spacing,
                  rowTangentP95Degrees=ROW_TANGENT_DEGREES, turns=GUIDE_TURNS)
    owners = edge_faces(faces)
    output_edges = np.asarray(sorted(owners), int).reshape(-1, 2)
    report = dict(policy=POLICY, limits=limits, spacing=float(spacing), guides=[], passed=True,
                  scope='Each authored guide is measured to one connected, forward-ordered output edge path that never turns from one edge loop '
                        'onto another (a turn: the arriving and leaving edges border one face), except once at each corner of the guide itself '
                        f'(a bend of {CORNER_DEGREES:g} degrees or more between the requested face before a point and the one after). Distance from the guide to that path at an '
                        'eighth-face sampling; direction over one requested face; the last face of arc at each open end answers to the one-face '
                        'end limit only.')
    for index, curve in enumerate(curves):
        curve = np.asarray(curve, float)
        closed = bool(np.linalg.norm(curve[0] - curve[-1]) < 1e-8)
        item = dict(curve=index, closed=closed, lengthFaces=float(_arc(curve)[-1] / spacing))
        connected = find_row(vertices, output_edges, curve, closed, spacing)
        candidates = ([] if closed else [find_loop(vertices, faces, curve, spacing)]) + [connected]
        item.update(vertices=[], passed=False, failures=['rowMissing'])
        for path in candidates:
            if not path:
                continue
            values, worst = measure_path(vertices, path, curve, closed, spacing)
            every = turns(path, owners, closed)
            at_corners = excused(path, every, vertices, curve, closed, spacing)
            turned = [position for position in every if position not in at_corners]
            values['turns'] = len(turned)
            failures = [key for key, value in values.items() if value > limits[key]]
            item.update(vertices=[int(v) for v in path], values=values,
                        valuesInFaces={k: float(v / spacing) for k, v in values.items() if k in ('rowP95', 'rowMax', 'rowEndMax')},
                        turnPositions=turned, cornerTurns=len(at_corners), cornerTurnPositions=at_corners,
                        guideCorners=len(corners(curve, closed, spacing)),
                        pathVertices=len(path) - int(closed), continuousLoop=not turned,
                        worstSample=worst.tolist(), passed=not failures, failures=failures)
            if not failures:
                break
        report['guides'].append(item)
    report['passed'] = all(item['passed'] for item in report['guides'])
    return report
