"""Cut guide curves into the source triangles by the rules recovered from ZRemesher.

ZRemesher curve modes 1 and 2 (Curves Strength 98 and above) do not steer the
field from the drawn polyline. They cut the curve into the source mesh and hand
the resulting source edges to the field, the integer solve and extraction as
constrained edges. This module ports that cut, stage by stage, from the
workbench recovery (`targets/zbrush/understanding/guided/GUIDE_EMBEDDING.md`,
`ORIGINAL_SOURCE_EMBEDDING.md`, `TRIANGLE_CUTTING.md` and the `recovered_*`
scripts named below). Engine addresses are RVAs of `xremeshlib2.dll`.

  projection      0x2e9730  nearest source triangle, optional snap to one of its vertices
  classification  0x10bdd0  face point -> vertex or edge within the classifier tolerance
  direct paths    0x10c0a0  same face, faces sharing an edge, vertex/edge neighbours
  walk            0x10d2e0  crossing by crossing toward the next sample, per-face tangent
  fallback        0x0fd6f0  source-vertex path when the walk fails
  prepass         0x255b10  5 % endpoint relocation (moves source vertices), run collapse,
                            endpoint propagation
  triangulation   0x2567b0  chords split their faces (0x252e50 uses Triangle with `pzQ`);
                            a free end point outside its (moved) triangle is put back
                            inside by the half-plane repair 0x253d80

What is and is not claimed. The rules, their order and their constants are the
recovered ones. The arithmetic is double precision throughout; native mixes
float32 storage and float32 determinants, so results are not byte-identical.
Native cuts its conditioned (densified) source; this module cuts whatever
source it is given. Branches the recovery left open are marked `Engineering`
where they occur: nearest-triangle tie order, same-edge spans, the closed-path
prepass, the planar triangulation of faces crossed edge to edge (native splits
the polygon at 0x254210 and converts it later; here every cut face goes through
Triangle), and the point merge on an edge.
"""
from collections import defaultdict, deque
import numpy as np
import trimesh
import triangle

VERTEX, EDGE, FACE = 1, 2, 4            # native attachment kinds (0x10bdd0)

QUERY_REACH = .025                      # 0x2e9730: nearest-face query radius, times the bbox diagonal
SNAP_SQUARED = 1.1111111319905831e-7    # 0x1c16e0 (bytes fb9bee33): squared vertex-snap distance, times the diagonal squared
CLASSIFY = 1e-6                         # 0x1c97b0: classifier tolerance, times the bbox diagonal
CLASSIFY_FLOOR = 1e-8                   # 0x1c97b0: floor of that tolerance
WALK_FRACTION = 1e-5                    # projector +4: edge-parameter tolerance of the walk
WALK_REVERSAL = .98                     # 0x10d2e0 (bytes 5c8fc2f5285cef3f): measure from the far end above this parameter
WALK_TANGENT = .3                       # 0x10d2e0: least in-face length of the unit direction, first pass
WALK_TANGENT_EXPANDED = .05             # the same in the expanded-tolerance retry
WALK_STEPS = 1000                       # 0x10d2e0 step guard
PARALLEL = 1e-5                         # 0x2e8e80 (bytes f168e388b5f8e43e): cross-length below which line and edge are parallel
PARALLEL_REACH = 1e-6                   # walk: a parallel candidate farther than this from the line is skipped
ENDPOINT_FRACTION = .05                 # 0x258c40 (+0x10): edge parameter below which a cut point becomes the edge's vertex
PROPAGATION_SWEEPS = 5                  # 0x255b10 endpoint propagation
FALLBACK_REACH = 20.                    # 0x0fd6f0: path-length limit, times the span length
INWARD_NUDGE = .001                     # 0x253d80 (bytes fca9f1d24d62503f): step from the edge toward the opposite corner
INWARD_PASSES = 3                       # 0x253d80
MERGE = 1e-9                            # Engineering: two cut points on one edge closer than this times the extent are one point


class _Topology:
    """Edge numbering and incidence in native order (recovered_mesh_topology.build)."""

    def __init__(self, count, faces):
        self.faces = faces
        corners = [[] for _ in range(count)]
        for face, row in enumerate(faces):
            for k in range(3):
                corners[int(row[k])].append((3 * face + k, int(row[(k + 1) % 3]), int(row[(k + 2) % 3])))
        edges = []
        for vertex, incident in enumerate(corners):
            seen = set()
            for _, following, previous in incident:
                for neighbor in (following, previous):
                    if neighbor > vertex and neighbor not in seen:
                        seen.add(neighbor)
                        edges.append((vertex, neighbor))
        self.edges = np.asarray(edges, int).reshape(-1, 2)
        self.lookup = {edge: i for i, edge in enumerate(edges)}
        self.face_edges = np.array([[self.lookup[tuple(sorted((int(row[k]), int(row[(k + 1) % 3]))))] for k in range(3)] for row in faces])
        self.edge_corners = [[] for _ in edges]
        for face in range(len(faces)):
            for k in range(3):
                self.edge_corners[self.face_edges[face, k]].append(3 * face + k)
        if any(len(row) > 2 for row in self.edge_corners):
            raise ValueError('Guide cutting needs a manifold source: an edge has more than two faces.')
        self.vertex_corners = [[corner for corner, _, _ in row] for row in corners]
        self.vertex_edges = [[] for _ in range(count)]
        for edge, (a, b) in enumerate(edges):
            self.vertex_edges[a].append(edge)
            self.vertex_edges[b].append(edge)

    def faces_of(self, kind, index):
        if kind == FACE:
            return {index}
        if kind == EDGE:
            return {corner // 3 for corner in self.edge_corners[index]}
        return {corner // 3 for corner in self.vertex_corners[index]}

    def edges_of(self, kind, index):
        """Source edges an attachment lies on."""
        if kind == EDGE:
            return {index}
        if kind == VERTEX:
            return set(self.vertex_edges[index])
        return set()


def _next(corner):
    return corner + 1 if corner % 3 != 2 else corner - 2


def _inward(point, triangle):
    """0x253d80: a planar point outside a counterclockwise triangle is put just inside it.

    Edge by edge, a point on the outer side is projected to the edge segment
    and stepped 0.001 of the way toward the opposite corner; up to three passes.
    """
    q = [float(point[0]), float(point[1])]
    for _ in range(INWARD_PASSES):
        changed = False
        for edge in range(3):
            a, b, c = (triangle[(edge + i) % 3] for i in range(3))
            dx, dy, px, py = b[0] - a[0], b[1] - a[1], q[0] - a[0], q[1] - a[1]
            if 0 <= dx * py - dy * px:
                continue
            changed = True
            squared = dy * dy + dx * dx
            if squared == 0:
                continue
            t = min(1., max(0., (dy * py + dx * px) / squared))
            x, y = (1 - t) * a[0] + b[0] * t, (1 - t) * a[1] + b[1] * t
            q = [(c[0] - x) * INWARD_NUDGE + x, (c[1] - y) * INWARD_NUDGE + y]
        if not changed:
            break
    return np.array(q)


def _line_edge(origin, direction, a, b):
    """0x2e8e80: (distance, s on the unit line, t on the edge, parallel) of the mutual closest points.

    The edge parameter is not clamped. Native evaluates the 2x2 determinants in
    float32; doubles here.
    """
    delta = b - a
    length = float(np.linalg.norm(delta))
    u = delta / length
    v = a - origin
    c = float(direction @ u)
    denominator = c * c - 1.
    if float(np.linalg.norm(np.cross(direction, u))) < PARALLEL or denominator == 0.:
        return float(np.linalg.norm(np.cross(direction, v))), float(v @ direction), 0., True
    vd, vu = float(v @ direction), float(v @ u)
    return 0., (c * vu - vd) / denominator, (vu - c * vd) / denominator / length, False


class _Cutter:
    def __init__(self, vertices, faces):
        self.vertices = vertices
        self.faces = faces
        self.topology = _Topology(len(vertices), faces)
        self.mesh = trimesh.Trimesh(vertices, faces, process=False)
        self.normals = self.mesh.face_normals
        extent = np.ptp(vertices, axis=0)
        self.diagonal = float(np.sqrt(extent @ extent))
        self.tolerance = max(self.diagonal * CLASSIFY, CLASSIFY_FLOOR)

    # --- 0x2e9730 and 0x10bdd0 -------------------------------------------------

    def project(self, curve):
        """Attach each sample: nearest triangle, then snap to one of its vertices. Samples with no face in reach are left out."""
        closed = len(curve) > 1 and bool((curve[0] == curve[-1]).all())
        samples = curve[:-1] if closed else curve
        # Engineering: trimesh's nearest-triangle query; native walks its own box tree and keeps the first of tied triangles.
        points, distances, owners = trimesh.proximity.closest_point(self.mesh, samples)
        result = []
        for point, distance, face in zip(points, distances, owners):
            if not distance < QUERY_REACH * self.diagonal:
                continue
            pair, best = (FACE, int(face)), np.inf
            for vertex in self.faces[face]:
                squared = float(((self.vertices[vertex] - point) ** 2).sum())
                if squared <= SNAP_SQUARED * self.diagonal ** 2 and squared < best:
                    pair, best = (VERTEX, int(vertex)), squared
            result.append((pair, self.vertices[pair[1]].copy() if pair[0] == VERTEX else point))
        if closed and result:
            result.append(result[0])
        return [self.classify(pair, point) for pair, point in result], closed

    def classify(self, pair, point):
        """Face point to vertex or edge inside the classifier tolerance; the last qualifying one wins."""
        kind, index = pair
        squared = self.tolerance ** 2
        if kind != FACE:
            return (kind, index), point
        selected = None
        for vertex in self.faces[index]:
            if float(((point - self.vertices[vertex]) ** 2).sum()) < squared:
                selected = int(vertex)
        if selected is not None:
            return (VERTEX, selected), self.vertices[selected].copy()
        for edge in self.topology.face_edges[index]:
            a, b = self.vertices[self.topology.edges[edge]]
            direction = (b - a) / np.linalg.norm(b - a)
            residual = (point - a) - direction * float((point - a) @ direction)   # infinite supporting line, as native
            if float(residual @ residual) < squared:
                selected, projected = int(edge), point - residual
        if selected is None:
            return (FACE, index), point
        for vertex in self.topology.edges[selected]:
            if float(((projected - self.vertices[vertex]) ** 2).sum()) < squared:
                return (VERTEX, int(vertex)), self.vertices[vertex].copy()
        return (EDGE, selected), projected

    def parameter(self, edge, point):
        """0x0fbec0: a ratio of lengths from the edge's first vertex, capped at one."""
        a, b = self.vertices[self.topology.edges[edge]]
        return min(1., float(np.linalg.norm(point - a) / np.linalg.norm(b - a)))

    def node(self, pair, point):
        kind, index = pair
        return dict(kind=kind, id=index, t=self.parameter(index, point) if kind == EDGE else 0., point=np.asarray(point, float).copy())

    # --- 0x10c0a0 ---------------------------------------------------------------

    def direct(self, start, start_point, end, end_point):
        """Spans that need no walk: (handled, nodes to append)."""
        (kind, index), (end_kind, target) = start, end
        topology = self.topology
        if kind == end_kind == FACE:
            if index == target:
                return True, []                      # the sample inside the face is not kept
            common = [int(e) for e in topology.face_edges[index] if e in topology.face_edges[target]]
            if len(common) != 1:
                return False, []
            a, b = self.vertices[topology.edges[common[0]]]
            delta = end_point - start_point
            _, _, t, parallel = _line_edge(start_point, delta / np.linalg.norm(delta), a, b)
            if parallel or not 0. <= t <= 1.:
                return False, []                     # Engineering: native appends unclamped; leave such spans to the walk
            return True, [dict(kind=EDGE, id=common[0], t=t, point=a * (1 - t) + b * t)]
        if kind == end_kind == VERTEX:
            if index != target and tuple(sorted((index, target))) in topology.lookup:
                return True, [self.node(end, end_point)]
            return False, []
        if kind == FACE and end_kind == VERTEX and target in self.faces[index]:
            return True, [self.node(end, end_point)]
        if kind == VERTEX and end_kind == EDGE and index in topology.edges[target]:
            return True, [self.node(end, end_point)]
        if kind == EDGE and end_kind == VERTEX and target in topology.edges[index]:
            return True, [self.node(end, end_point)]
        if kind == end_kind == EDGE and index == target:
            return True, [self.node(end, end_point)]  # Engineering: two samples on one edge; no recovered branch
        return False, []

    # --- 0x11a470 and 0x10d2e0 ----------------------------------------------------

    def candidates(self, pair, end):
        """(finished, candidate corners, vertex reached directly or None)."""
        (kind, index), (end_kind, target) = pair, end
        topology, flat, corners = self.topology, self.faces.ravel(), []
        if kind == FACE:
            if end_kind == FACE and index == target:
                return True, corners, None
            corners.extend(3 * index + k for k in range(3))
        elif kind == EDGE:
            if end_kind == VERTEX and target in topology.edges[index]:
                return True, corners, target
            for corner in topology.edge_corners[index]:
                if end_kind == FACE and target == corner // 3:
                    return True, corners, None
                a = _next(corner)
                b = _next(a)
                corners.extend((a, b))
                if end_kind == VERTEX and target == flat[b]:
                    return True, corners, target
        else:
            for corner in topology.vertex_corners[index]:
                if end_kind == FACE and target == corner // 3:
                    return True, corners, None
                candidate = _next(corner)
                corners.append(candidate)
                if end_kind == VERTEX and target == flat[candidate]:
                    return True, corners, target
        return False, corners, None

    def walk(self, start, start_point, end, end_point):
        """Crossings from one attached sample toward the next, or None when the walk fails.

        At each step the unit direction to the target is projected into each
        candidate face on its own, the line is intersected with the candidate
        edge, and the farthest forward crossing inside the edge is taken.
        """
        topology = self.topology
        current, pair, previous, rows = np.asarray(start_point, float), start, (0, -1), []
        absolute = self.tolerance ** 2
        for _ in range(WALK_STEPS + 1):
            finished, corners, vertex = self.candidates(pair, end)
            if finished:
                if vertex is not None:
                    rows.append(dict(kind=VERTEX, id=int(vertex), t=0., point=self.vertices[vertex].copy()))
                return rows
            delta = end_point - current
            if not np.any(delta):
                return None
            direction = delta / np.linalg.norm(delta)
            choice = None
            for expanded in (False, True):
                best, choice = -1e6, None
                tolerance = WALK_FRACTION * (10 if expanded else 1)
                margin = WALK_FRACTION * (100 if expanded else 3)
                for corner in corners:
                    edge = int(topology.face_edges[corner // 3, corner % 3])
                    normal = self.normals[corner // 3]
                    tangent = direction - normal * float(direction @ normal)
                    size = float(np.linalg.norm(tangent))
                    if size < (WALK_TANGENT_EXPANDED if expanded else WALK_TANGENT):
                        continue
                    tangent /= size
                    a, b = self.vertices[topology.edges[edge]]
                    distance, s, t, parallel = _line_edge(current, tangent, a, b)
                    if not parallel and t > WALK_REVERSAL:
                        _, s, reverse, parallel = _line_edge(current, tangent, b, a)
                        t = 1 - reverse
                    if parallel:
                        if distance > PARALLEL_REACH:
                            continue
                        first, second = float((a - current) @ tangent), float((b - current) @ tangent)
                        t, s = (1., second) if first <= second else (0., first)
                    else:
                        if -margin <= t <= tolerance:
                            t = 0.
                        if 1 - tolerance <= t <= 1 + margin:
                            t = 1.
                    if 0. <= t <= 1. and s > best:
                        best, choice = s, (edge, t, a * (1 - t) + b * t)
                if choice is not None and best >= 0:
                    break
            if choice is None or best < 0:
                return None                           # native goes on to endpoint repair; here the fallback path takes over
            edge, t, point = choice
            a, b = self.vertices[topology.edges[edge]]
            da, db = float(((point - a) ** 2).sum()), float(((point - b) ** 2).sum())
            if da < absolute and t < .1:
                t = 0.
            elif not (da >= absolute and db >= absolute):
                t = 1. if (db < absolute and t > .9) or da >= absolute else 0.
            following = (VERTEX, int(topology.edges[edge, int(t)])) if t in (0., 1.) else (EDGE, edge)
            if following == previous and previous[0] != 0:
                return None
            if following[0] == VERTEX:
                rows.append(dict(kind=VERTEX, id=following[1], t=0., point=self.vertices[following[1]].copy()))
            else:
                rows.append(dict(kind=EDGE, id=edge, t=float(t), point=point))
            previous, pair, current = pair, following, point
            if pair == end:
                return rows
        return None

    # --- 0x0fd6f0 -----------------------------------------------------------------

    def fallback(self, start, start_point, end, end_point):
        """Source-vertex path from the start attachment to the end attachment, or None."""
        topology, positions = self.topology, self.vertices

        def attached(kind, index):
            return [index] if kind == VERTEX else [int(v) for v in (topology.edges[index] if kind == EDGE else self.faces[index])]
        seeds, targets = attached(*end), attached(*start)
        lengths = np.linalg.norm(positions[topology.edges[:, 0]] - positions[topology.edges[:, 1]], axis=1)
        cost = np.full(len(positions), np.inf)
        previous = np.full(len(positions), -1)
        queued = np.zeros(len(positions), bool)
        queue = deque()
        limit = float(np.linalg.norm(start_point - end_point)) * FALLBACK_REACH
        for seed in seeds:
            if not queued[seed]:
                queue.append(seed)
                queued[seed] = True
            previous[seed] = -2
            cost[seed] = 0. if end[0] == VERTEX else float(np.linalg.norm(start_point - positions[seed]))
        for target in targets:
            previous[target] = -3
        while queue:
            vertex = queue.popleft()
            queued[vertex] = False
            incident = topology.vertex_edges[vertex]
            neighbors = [int(topology.edges[e, 1] if topology.edges[e, 0] == vertex else topology.edges[e, 0]) for e in incident]
            keys = [float(((start_point - positions[n]) ** 2).sum()) for n in neighbors]
            for offset in np.argsort(keys, kind='stable'):
                edge, neighbor = incident[offset], neighbors[offset]
                candidate = lengths[edge] + cost[vertex]
                if previous[neighbor] == -3:
                    limit = candidate                 # native: meeting a target replaces the pruning limit
                    continue
                if candidate < cost[neighbor] and candidate < limit:
                    cost[neighbor], previous[neighbor] = candidate, vertex
                    if np.linalg.norm(start_point - positions[neighbor]) + candidate < limit and not queued[neighbor]:
                        queue.append(neighbor)
                        queued[neighbor] = True
        for target in targets:
            for edge in topology.vertex_edges[target]:
                neighbor = int(topology.edges[edge, 1] if topology.edges[edge, 0] == target else topology.edges[edge, 0])
                if previous[neighbor] == -2 or previous[neighbor] >= 0:
                    candidate = lengths[edge] + cost[neighbor]
                    if candidate < cost[target]:
                        cost[target], previous[target] = candidate, neighbor
        selected = -1
        if len(targets) == 1:
            selected = targets[0]
        else:
            best = np.inf
            for target in targets:
                if previous[target] >= 0:
                    candidate = float(np.linalg.norm(start_point - positions[target])) + cost[target]
                    if candidate < best:
                        best, selected = candidate, target
        if selected < 0 or previous[selected] < 0:
            return None
        ids = [] if start[0] == VERTEX else [selected]
        cursor = int(previous[selected])
        while cursor != -2:
            if cursor < 0 or len(ids) > len(positions):
                return None
            ids.append(cursor)
            cursor = int(previous[cursor])
        return [dict(kind=VERTEX, id=v, t=0., point=positions[v].copy()) for v in ids]

    # --- 0x103060 -----------------------------------------------------------------

    def segments(self, attached):
        """Surface-path records for one projected curve, and how each span was resolved."""
        records, record = [], [self.node(*attached[0])]
        counts = dict(spans=0, direct=0, walked=0, fallback=0, flushed=0)
        for (start, start_point), (end, end_point) in zip(attached[:-1], attached[1:]):
            if start[0] == end[0] == VERTEX and start[1] == end[1]:
                continue
            counts['spans'] += 1
            handled, nodes = self.direct(start, start_point, end, end_point)
            if handled:
                counts['direct'] += 1
            else:
                nodes = self.walk(start, start_point, end, end_point)
                if nodes is not None:
                    counts['walked'] += 1
                else:
                    nodes = self.fallback(start, start_point, end, end_point)
                    if nodes is not None:
                        counts['fallback'] += 1
            if nodes is None:
                counts['flushed'] += 1
                if len(record) >= 2:
                    records.append(record)
                record = [self.node(end, end_point)]
            else:
                record.extend(nodes)
        if attached[-1][0][0] == FACE and (len(record) < 2 or record[-1]['kind'] != FACE or record[-1]['id'] != attached[-1][0][1]
                                           or np.any(record[-1]['point'] != attached[-1][1])):
            record.append(self.node(*attached[-1]))   # the free end point inside its face is kept
        if len(record) >= 2:
            records.append(record)
        return records, counts

    # --- 0x255b10 -----------------------------------------------------------------

    def prepare(self, record, requests):
        """5 % endpoint relocation, shared-edge run collapse and endpoint propagation, in place.

        Engineering: closed records take the open-path policy; the native
        closed-path wrap handling is not ported.
        """
        edges = self.topology.edges
        for node in record:
            if node['kind'] != EDGE:
                continue
            if 0. < node['t'] < ENDPOINT_FRACTION:
                vertex = int(edges[node['id'], 0])
            elif 1. - ENDPOINT_FRACTION < node['t'] < 1.:
                vertex = int(edges[node['id'], 1])
            else:
                continue
            requests.append((vertex, node['point'].copy()))
            node.update(kind=VERTEX, id=vertex, t=0.)
        # Between two path vertices joined by a source edge, points on that same edge fold into the edge.
        keep, last = np.ones(len(record), bool), None
        for i, node in enumerate(record):
            if node['kind'] != VERTEX:
                continue
            if last is not None and i > last + 1 and node['id'] != record[last]['id']:
                shared = self.topology.lookup.get(tuple(sorted((node['id'], record[last]['id']))))
                if shared is not None and all(n['kind'] == EDGE and n['id'] == shared for n in record[last + 1:i]):
                    keep[last + 1:i] = False
            last = i
        record[:] = [node for node, kept in zip(record, keep) if kept]
        for _ in range(PROPAGATION_SWEEPS):
            changed = False
            for i in range(1, len(record) - 1):
                if record[i]['kind'] != VERTEX or FACE in (record[i - 1]['kind'], record[i + 1]['kind']):
                    continue
                for j in (i - 1, i + 1):
                    if record[j]['kind'] == EDGE and record[i]['id'] in edges[record[j]['id']]:
                        record[j].update(kind=VERTEX, id=record[i]['id'], t=0.)
                        changed = True
            if not changed:
                break
        record[:] = [node for i, node in enumerate(record)
                     if not (i and node['kind'] == VERTEX and record[i - 1]['kind'] == VERTEX and record[i - 1]['id'] == node['id'])]


def cut(vertices, faces, curves, *, source_paths=()):
    """Cut `curves` into the triangle mesh; returns (points, triangles, report).

    `source_paths` are vertex-id paths along existing source edges (admitted
    creases). They are not moved or re-routed; where a guide crosses one, both
    pieces keep the crease's identity. Identities are numbered guides first,
    then source paths. The report holds, per identity, its cut-mesh edges and
    its ordered vertex chain (`chains`), the relocated source vertices and the
    parent source triangle of every output triangle.
    """
    vertices = np.asarray(vertices, float)
    raw = np.asarray(faces)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices) or not np.isfinite(vertices).all():
        raise ValueError('Source vertices must be finite 3D points')
    if raw.ndim != 2 or raw.shape[1] != 3 or not len(raw) or not np.issubdtype(raw.dtype, np.integer):
        raise ValueError('Source faces must be integer triangles')
    faces = raw.astype(int)
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError('Source triangle index outside vertex range')
    cutter = _Cutter(vertices, faces)
    topology = cutter.topology
    extent = float(np.ptp(vertices, axis=0).max())
    eps = extent * MERGE
    curves = [np.asarray(curve, float) for curve in curves]
    records, requests, attachments, spans = [], [], [], []
    for ci, curve in enumerate(curves):
        if curve.ndim != 2 or curve.shape[1] != 3 or len(curve) < 2 or not np.isfinite(curve).all():
            raise ValueError('Guides require at least two finite 3D samples')
        attached, closed = cutter.project(curve)
        if len(attached) < 2:
            raise ValueError(f'Guide {ci + 1} does not lie on the source surface.')
        pieces, counts = cutter.segments(attached)
        kinds = [pair[0] for pair, _ in attached]
        attachments.append(dict(curve=ci, samples=len(curve), attached=len(attached), closed=closed,
                                onVertices=kinds.count(VERTEX), onEdges=kinds.count(EDGE), inFaces=kinds.count(FACE)))
        spans.append(dict(counts, curve=ci, pieces=len(pieces)))
        if len(pieces) != 1:
            # Engineering: native keeps every piece as its own record. One connected row per guide is what the
            # application asks for downstream, so a guide the walk cannot keep in one piece is refused here.
            raise ValueError(f'Guide {ci + 1} could not be cut into the source as one connected path ({len(pieces)} pieces).')
        records.append(pieces[0])
    for record in records:
        cutter.prepare(record, requests)
    # Queued source-vertex positions are applied in path order; the last request for a vertex decides.
    points = [p.copy() for p in vertices]
    relocations = {}
    for vertex, position in requests:
        points[vertex] = position
        relocations[vertex] = position
    edge_points, face_points = defaultdict(list), defaultdict(list)

    def edge_vertex(edge, t, position):
        for stored, index in edge_points[edge]:
            if np.linalg.norm(points[index] - position) <= eps:
                return index, stored
        points.append(position.copy())
        edge_points[edge].append((float(t), len(points) - 1))
        return len(points) - 1, float(t)

    def face_vertex(face, position):
        for index in face_points[face]:
            if np.linalg.norm(points[index] - position) <= eps:
                return index
        points.append(position.copy())
        face_points[face].append(len(points) - 1)
        return len(points) - 1

    constraints = defaultdict(list)       # face -> (vertex, vertex, identity) chords
    runs = []                             # (edge, t, t, identity) intervals along a source edge
    for ci, record in enumerate(records):
        ids = []
        for node in record:
            if node['kind'] == VERTEX:
                ids.append(node['id'])
            elif node['kind'] == EDGE:
                index, node['t'] = edge_vertex(node['id'], node['t'], node['point'])
                ids.append(index)
            else:
                ids.append(face_vertex(node['id'], node['point']))
        for (a, i), (b, j) in zip(zip(record[:-1], ids[:-1]), zip(record[1:], ids[1:])):
            if i == j:
                continue
            shared = topology.edges_of(a['kind'], a['id']) & topology.edges_of(b['kind'], b['id'])
            if shared:
                edge = min(shared)
                first = a['t'] if a['kind'] == EDGE else float(topology.edges[edge, 1] == a['id'])
                second = b['t'] if b['kind'] == EDGE else float(topology.edges[edge, 1] == b['id'])
                runs.append((edge, min(first, second), max(first, second), ci))
                continue
            common = topology.faces_of(a['kind'], a['id']) & topology.faces_of(b['kind'], b['id'])
            if not common:
                raise ValueError(f'Guide {ci + 1} has consecutive cut points that share no source triangle.')
            constraints[min(common)].append((i, j, ci))
    guide_edges = defaultdict(set)
    for pi, path in enumerate(source_paths):
        path = [int(v) for v in path]
        if len(path) < 2:
            raise ValueError('An admitted source path needs at least one edge')
        for a, b in zip(path[:-1], path[1:]):
            edge = topology.lookup.get(tuple(sorted((a, b))))
            if a == b or edge is None:
                raise ValueError('An admitted feature is not a source mesh edge')
            runs.append((edge, 0., 1., len(curves) + pi))
    output, owners, slivers, repairs = [], [], 0, []
    for fi, face in enumerate(faces):
        boundary = []
        for k in range(3):
            a, b = int(face[k]), int(face[(k + 1) % 3])
            edge = int(topology.face_edges[fi, k])
            boundary.extend([a] + [index for _, index in sorted(edge_points[edge], reverse=a > b)])
        if len(boundary) == 3 and fi not in constraints:
            output.append(face.tolist())
            owners.append(fi)
            continue
        ids = list(dict.fromkeys(boundary + [i for a, b, _ in constraints[fi] for i in (a, b)]))
        table = {index: i for i, index in enumerate(ids)}
        q = vertices[face]
        u = (q[1] - q[0]) / np.linalg.norm(q[1] - q[0])
        normal = cutter.normals[fi]
        basis = np.array([u, np.cross(normal, u)]).T
        # A relocated corner can leave a free guide end outside its triangle; native repairs the planar point.
        # Engineering: the vertex itself is moved to the repaired point, so the cut mesh stays consistent.
        corners = (np.array([points[int(i)] for i in face]) - q[0]) @ basis
        for index in face_points[fi]:
            planar = (points[index] - q[0]) @ basis
            repaired = _inward(planar, corners)
            if np.any(repaired != planar):
                points[index] = q[0] + basis @ repaired
                repairs.append(index)
        uv = (np.array([points[i] for i in ids]) - q[0]) @ basis
        unique = {}
        for a, b in zip(boundary, boundary[1:] + boundary[:1]):
            unique[tuple(sorted((table[a], table[b])))] = 1
        for a, b, ci in constraints[fi]:
            key = tuple(sorted((table[a], table[b])))
            unique[key] = max(unique.get(key, 1), 1000 + ci)   # one marker per segment: the later identity where two coincide
        built = triangle.triangulate(dict(vertices=uv, segments=list(unique), segment_markers=list(unique.values())), 'pQ')
        if 'triangles' not in built:
            raise ValueError('Empty constrained face triangulation')
        global_ids = ids.copy()
        for local in built['vertices'][len(ids):]:
            global_ids.append(face_vertex(fi, q[0] + basis @ local))   # crossing of two chords inside the face
        for tri in built['triangles']:
            tri = [global_ids[int(i)] for i in tri]
            p = np.asarray([points[i] for i in tri])
            area = float(np.cross(p[1] - p[0], p[2] - p[0]) @ normal)
            if area < 0:
                tri[1], tri[2] = tri[2], tri[1]
                area = -area
            slivers += area <= extent * extent * 1e-18   # kept: dropping one would open the shared edge
            output.append(tri)
            owners.append(fi)
        for e, marker in zip(built['segments'], built['segment_markers'].ravel()):
            if marker >= 1000:
                guide_edges[int(marker) - 1000].add(tuple(sorted(global_ids[int(i)] for i in e)))
    for edge, low, high, identity in runs:
        a, b = map(int, topology.edges[edge])
        chain = [(0., a)] + sorted(edge_points[edge]) + [(1., b)]
        inside = [index for t, index in chain if low - 1e-12 <= t <= high + 1e-12]
        guide_edges[identity].update(tuple(sorted(pair)) for pair in zip(inside[:-1], inside[1:]))
    points = np.asarray(points)
    output = np.asarray(output, int)
    result = trimesh.Trimesh(points, output, process=False)
    if cutter.mesh.is_watertight != result.is_watertight or not result.is_winding_consistent or result.euler_number != cutter.mesh.euler_number:
        raise ValueError('Guide cutting changed the source topology or winding')
    present = {tuple(e) for e in np.sort(result.edges_unique, axis=1).tolist()}
    chains = {}
    for identity in range(len(curves) + len(source_paths)):
        edges = sorted(guide_edges.get(identity, ()))
        if not edges or any(edge not in present for edge in edges):
            raise ValueError(f'Feature {identity} was not kept as cut-mesh edges.')
        chains[identity] = _ordered(edges)
    for ci, record in enumerate(records):
        chain = chains[ci]
        if chain is None:
            raise ValueError(f'Guide {ci + 1} did not cut into one simple path (it branches or crosses itself).')
        if np.linalg.norm(points[chain[-1]] - record[0]['point']) < np.linalg.norm(points[chain[0]] - record[0]['point']):
            chain.reverse()
    worst = 0.
    for ci, curve in enumerate(curves):
        a = points[chains[ci][:-1]]
        d = points[chains[ci][1:]] - a
        for sample in curve:
            t = np.clip(((sample - a) * d).sum(1) / np.maximum(1e-300, (d * d).sum(1)), 0, 1)
            worst = max(worst, float(np.linalg.norm(sample - a - t[:, None] * d, axis=1).min()))
    moved = [dict(vertex=int(v), distance=float(np.linalg.norm(p - vertices[v]))) for v, p in sorted(relocations.items())]
    report = dict(attachments=attachments, spans=spans, sourceOwners=owners,
                  guideEdges={str(k): [list(e) for e in sorted(v)] for k, v in guide_edges.items()},
                  chains={str(k): v for k, v in chains.items()},
                  relocatedVertices=moved, relocationRequests=len(requests),
                  sourceVertices=len(vertices), cutVertices=len(points), sourceTriangles=len(faces), cutTriangles=len(output),
                  guideSampleMaxDistance=worst, zeroAreaTriangles=int(slivers), inwardRepairs=len(repairs),
                  constants=dict(inwardNudge=INWARD_NUDGE, queryReach=QUERY_REACH, snapSquared=SNAP_SQUARED, classify=CLASSIFY, classifyFloor=CLASSIFY_FLOOR,
                                 walkFraction=WALK_FRACTION, walkReversal=WALK_REVERSAL, endpointFraction=ENDPOINT_FRACTION,
                                 propagationSweeps=PROPAGATION_SWEEPS, bboxDiagonal=cutter.diagonal, classifierTolerance=cutter.tolerance),
                  method='Recovered ZRemesher guide cut: projection 0x2e9730, classification 0x10bdd0, direct paths 0x10c0a0, walk 0x10d2e0, '
                         'vertex-path fallback 0x0fd6f0, 5% endpoint relocation and propagation 0x255b10, per-face constrained triangulation. '
                         'Double precision; not byte-identical to native float32 arithmetic.',
                  triangleVersion=triangle.__version__)
    return points, output, report


def _ordered(edges):
    """Vertex chain of an edge set that is one simple open or closed path, else None. A loop repeats its first vertex."""
    neighbors = defaultdict(list)
    for a, b in edges:
        neighbors[a].append(b)
        neighbors[b].append(a)
    if any(len(v) > 2 for v in neighbors.values()):
        return None
    ends = sorted(v for v, n in neighbors.items() if len(n) == 1)
    if len(ends) not in (0, 2):
        return None
    chain, previous = [ends[0] if ends else min(neighbors)], None
    while True:
        following = [v for v in neighbors[chain[-1]] if v != previous]
        if not following or (len(chain) > 1 and chain[-1] == chain[0]):
            break
        previous = chain[-1]
        chain.append(following[0])
    return chain if len(chain) == len(edges) + 1 else None
