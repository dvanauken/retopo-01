"""Ordered, connected output edge rows along admitted source creases.

The crease check used to measure each crease sample to the nearest output edge
of any kind and then subtract a band allowance, so unrelated edges near a crease
could pass without forming a row. This module names, for every band of parallel
creases, the one crease that represents it, finds one connected and
forward-ordered output edge path for that crease, and measures the band against
that path alone: a row anywhere across the band measures zero, a row beside the
band is charged its whole gap.

Evidence level. Native ZRemesher embeds admitted creases as guide edges and
keeps them as edge rows through extraction (recovered embedded-guide and
extraction-graph modules). In the island 6 keep-creases capture at a request of
200, both rim creases have rows; the native integer policy (0x28fe70) separates
parallel guides by one cell rather than merging them, which this application's
quad-shape limits do not allow at a quarter-face gap. One row per band is
therefore this application's existing band policy (source_features.band_widths),
not a native rule. The limits reuse numbers the application already applies;
the choice of representative, the two-face minimum and the path cost are
engineering choices, labelled where they are defined. Nothing here is recovered
native arithmetic.
"""
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from feature_rows import graph_paths

POLICY = 'crease-rows-v1'
# Engineering choice: a row is at least two consecutive output edges, so a chain
# whose extent (the largest distance between two of its points) is under two
# requested faces cannot be told apart from a single edge and stays under the
# nearest-edge measure alone. Extent, not length, so a loop tighter than two
# faces across is not asked for a row it has no room for.
ROW_MIN_FACES = 2.
# Row limits, all existing numbers of this application with their existing meaning:
#   rowP95      0.25 h  crease check: "95% of each crease within a quarter face of an edge loop"
#   rowMax      0.5 h   crease check: "no crease point runs through the middle of a face"
#   rowEndMax   1 h     crease check: "a vertex within one face of every junction"; applies
#                       to the last face of arc at each end of an open chain, which the
#                       other three limits leave out
#   tangentP95  30 deg  the connected-path limit for authored guides (curved_quad)
ROW_P95_FACES = .25
ROW_MAX_FACES = .5
ROW_END_FACES = 1.
ROW_TANGENT_DEGREES = 30.
SAMPLE_FACES = .125   # the crease check's sample spacing
WIDTH_SAMPLES = 9     # crease edges per branch whose sheet widths are walked (cost bound, not a geometric limit)
_MEMO = {}            # the last representatives() answer; see there


def _arc(points):
    return np.r_[0., np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]


def _at(points, arc, parameters):
    return np.stack([np.interp(parameters, arc, points[:, k]) for k in range(points.shape[1])], axis=-1)


def _leaving(points, window):
    """Unit direction in which a polyline leaves its first point, over `window` of arc length."""
    arc = _arc(points)
    direction = _at(points, arc, min(window, arc[-1])) - points[0]
    norm = np.linalg.norm(direction)
    return direction / norm if norm > 0 else direction


def chains(source, edges, spacing):
    """Join crease branches into chains: (vertex ids, closed), loops repeating their start.

    Branches split at every vertex that is not of degree two. At such a vertex
    two branch ends are joined when one continues the other within
    BAND_DEGREES (engineering choice: the angle that already defines parallel
    bands), straightest pairs first; every end is used once.
    """
    from source_features import BAND_DEGREES
    source = np.asarray(source, float)
    branches = [list(map(int, b)) for b in graph_paths(edges)]
    ends = {}
    for index, branch in enumerate(branches):
        points = source[branch]
        ends.setdefault(branch[0], []).append((index, 0, _leaving(points, spacing)))
        ends.setdefault(branch[-1], []).append((index, 1, _leaving(points[::-1], spacing)))
    link = {}
    limit = -np.cos(np.radians(BAND_DEGREES))
    for vertex in sorted(ends):
        items = ends[vertex]
        pairs = sorted((float(items[i][2] @ items[j][2]), i, j) for i in range(len(items)) for j in range(i + 1, len(items)))
        used = set()
        for cosine, i, j in pairs:
            if cosine > limit:
                break
            if i in used or j in used or items[i][:2] == items[j][:2]:
                continue
            used.update((i, j))
            a, b = items[i][:2], items[j][:2]
            link[a], link[b] = b, a
    result, seen = [], set()

    def walk(index, entered):
        vertices, first = [], (index, entered)
        while True:
            seen.add(index)
            branch = branches[index] if entered == 0 else branches[index][::-1]
            vertices += branch if not vertices else branch[1:]
            following = link.get((index, 1 - entered))
            if following is None:
                return vertices, False
            if following == first:
                return vertices, True
            index, entered = following
    starts = [(i, e) for i in range(len(branches)) for e in (0, 1) if (i, e) not in link]
    for index, entered in starts + [(i, 0) for i in range(len(branches))]:
        if index in seen:
            continue
        vertices, closed = walk(index, entered)
        closed = closed or (len(vertices) > 3 and vertices[0] == vertices[-1])
        result.append((vertices, bool(closed)))
    return result


def sheet_widths(source, triangles, edges, selected):
    """Width of the wider sheet beside each selected crease edge.

    From the edge midpoint the surface is walked across its triangles in the
    plane perpendicular to the edge, on both sides, until another admitted
    crease or a boundary is met (or the section returns to a face already
    crossed). The larger of the two lengths is returned.
    """
    source, triangles = np.asarray(source, float), np.asarray(triangles, int)
    edges = np.asarray(edges, int).reshape(-1, 2)
    owners = {}
    for face, triangle in enumerate(triangles):
        for k in range(3):
            owners.setdefault(tuple(sorted((int(triangle[k]), int(triangle[(k + 1) % 3])))), []).append(face)
    creases = {tuple(sorted(map(int, e))) for e in edges}
    result = np.zeros(len(selected))
    for slot, index in enumerate(selected):
        a, b = map(int, edges[index])
        origin = (source[a] + source[b]) * .5
        normal = source[b] - source[a]
        normal /= max(1e-30, np.linalg.norm(normal))
        widths = []
        for face in owners.get(tuple(sorted((a, b))), []):
            entry, point, total, visited = tuple(sorted((a, b))), origin, 0., set()
            while face not in visited:
                visited.add(face)
                triangle = [int(v) for v in triangles[face]]
                signed = {v: float((source[v] - origin) @ normal) for v in triangle}
                # A vertex exactly on the plane counts as on the positive side.
                leaving = None
                for k in range(3):
                    u, w = triangle[k], triangle[(k + 1) % 3]
                    key = tuple(sorted((u, w)))
                    if key == entry or (signed[u] >= 0) == (signed[w] >= 0):
                        continue
                    t = signed[u] / (signed[u] - signed[w])
                    leaving = (key, source[u] + t * (source[w] - source[u]))
                if leaving is None:
                    break
                key, crossing = leaving
                total += float(np.linalg.norm(crossing - point))
                following = [f for f in owners[key] if f != face]
                if key in creases or not following:
                    break
                entry, point, face = key, crossing, following[0]
            widths.append(total)
        result[slot] = max(widths, default=0.)
    return result


def _parallel(points_a, points_b, starts, ends):
    """Unsigned cosine between each edge (a, b) and the polyline segment nearest its midpoint."""
    middle = (points_a + points_b) * .5
    delta = ends - starts
    squared = np.maximum(1e-30, (delta * delta).sum(1))
    cosine = np.empty(len(middle))
    for first in range(0, len(middle), 256):
        batch = slice(first, first + 256)
        t = np.clip(((middle[batch, None] - starts) * delta).sum(2) / squared, 0, 1)
        nearest = np.linalg.norm(middle[batch, None] - starts - t[:, :, None] * delta, axis=2).argmin(1)
        direction = points_b[batch] - points_a[batch]
        unit = direction / np.maximum(1e-30, np.linalg.norm(direction, axis=1))[:, None]
        cosine[batch] = np.abs((unit * (delta[nearest] / np.sqrt(squared[nearest])[:, None])).sum(1))
    return cosine


def representatives(source, triangles, edges, spacing):
    """The crease edges that must carry rows, the edges they absorb, and the row chains.

    Engineering choice: within a band of parallel creases (the existing band
    rule: within BAND_REACH of the requested spacing and BAND_DEGREES of
    parallel) the crease bordering the wider sheet represents the band. Its row
    then keeps the larger sheet's true edge, and the narrow strip between the
    band's creases is spanned by the neighbouring quads. Branches are taken
    widest sheet first (ties: longer first); a later crease edge is absorbed
    when both its ends lie within reach of the representatives chosen so far
    and it runs parallel to them, and a branch is absorbed when most of its
    length is. Returns (chains, representative mask, absorbed mask); the masks
    index `edges`; the chains are the representative edges joined into chains
    of ROW_MIN_FACES or more, longest first, as dicts(vertices, closed, length).
    """
    from source_features import BAND_REACH, BAND_DEGREES, segment_distances
    source = np.asarray(source, float)
    triangles = np.asarray(triangles, int)
    edges = np.asarray(edges, int).reshape(-1, 2)
    # One job measures many candidates against the same source: the answer depends on the
    # source, its admitted creases and the spacing only, so the last one is kept.
    key = (source.shape, source.tobytes(), triangles.tobytes(), edges.tobytes(), float(spacing))
    if _MEMO.get('key') == key:
        rows, chosen, absorbed = _MEMO['value']
        return [dict(row, vertices=list(row['vertices'])) for row in rows], chosen.copy(), absorbed.copy()
    chosen = np.zeros(len(edges), bool)
    absorbed = np.zeros(len(edges), bool)
    if not len(edges):
        return [], chosen, absorbed
    lookup = {tuple(sorted(map(int, e))): i for i, e in enumerate(edges)}
    lengths = np.linalg.norm(source[edges[:, 1]] - source[edges[:, 0]], axis=1)
    groups = []
    for branch in graph_paths(edges):
        ids = np.array([lookup[tuple(sorted(pair))] for pair in zip(branch[:-1], branch[1:])])
        picked = ids[np.unique(np.linspace(0, len(ids) - 1, min(len(ids), WIDTH_SAMPLES)).round().astype(int))]
        groups.append((branch, ids, picked))
    walked = dict(zip(np.concatenate([picked for _, _, picked in groups]).tolist(),
                      sheet_widths(source, triangles, edges, np.concatenate([picked for _, _, picked in groups])).tolist()))
    branches = []
    for branch, ids, picked in groups:
        width = float(np.median([walked[int(i)] for i in picked]))
        branches.append((-width, -float(lengths[ids].sum()), int(branch[0]), int(branch[-1]), ids))
    cosine_limit = np.cos(np.radians(BAND_DEGREES))
    for _, _, _, _, ids in sorted(branches, key=lambda item: item[:4]):
        if chosen.any():
            starts, ends = source[edges[chosen, 0]], source[edges[chosen, 1]]
            near = segment_distances(source[np.unique(edges[ids])], starts, ends) < BAND_REACH * spacing
            near = dict(zip(np.unique(edges[ids]).tolist(), near.tolist()))
            inside = np.array([near[int(a)] and near[int(b)] for a, b in edges[ids]])
            if inside.any():
                parallel = _parallel(source[edges[ids[inside], 0]], source[edges[ids[inside], 1]], starts, ends) >= cosine_limit
                absorbed[ids[inside][parallel]] = True
        if lengths[ids][absorbed[ids]].sum() > .5 * lengths[ids].sum():
            absorbed[ids] = True
            continue
        absorbed[ids] = False
        chosen[ids] = True
    rows = []
    for vertices, closed in chains(source, edges[chosen], spacing):
        points = source[vertices]
        length = float(_arc(points)[-1])
        if length < ROW_MIN_FACES * spacing:
            continue
        probe = points[np.unique(np.linspace(0, len(points) - 1, min(len(points), 64)).round().astype(int))]
        extent = float(np.linalg.norm(probe[:, None] - probe[None], axis=2).max())
        if extent >= ROW_MIN_FACES * spacing:
            rows.append(dict(vertices=vertices, closed=closed, length=length))
    rows.sort(key=lambda row: (-row['length'], row['vertices'][0], row['vertices'][-1]))
    _MEMO.clear()
    _MEMO.update(key=key, value=([dict(row, vertices=list(row['vertices'])) for row in rows], chosen.copy(), absorbed.copy()))
    return rows, chosen, absorbed


def band_edges(source, edges, rows, spacing):
    """Masks over `edges`: the row chains' own edges, and the other crease edges inside their bands.

    A crease edge is inside a row's band by the existing band rule: both ends
    within BAND_REACH of the requested spacing of the row chains and running
    within BAND_DEGREES of the nearest one.
    """
    from source_features import BAND_REACH, BAND_DEGREES, segment_distances
    source = np.asarray(source, float)
    edges = np.asarray(edges, int).reshape(-1, 2)
    own = np.zeros(len(edges), bool)
    partner = np.zeros(len(edges), bool)
    if not rows or not len(edges):
        return own, partner
    lookup = {tuple(sorted(map(int, e))): i for i, e in enumerate(edges)}
    for row in rows:
        for pair in zip(row['vertices'][:-1], row['vertices'][1:]):
            own[lookup[tuple(sorted(pair))]] = True
    starts, ends = source[edges[own, 0]], source[edges[own, 1]]
    near = segment_distances(source, starts, ends) < BAND_REACH * spacing
    candidates = np.flatnonzero(near[edges[:, 0]] & near[edges[:, 1]] & ~own)
    if len(candidates):
        cosine = _parallel(source[edges[candidates, 0]], source[edges[candidates, 1]], starts, ends)
        partner[candidates[cosine >= np.cos(np.radians(BAND_DEGREES))]] = True
    return own, partner


def _nearest(points, curve):
    """Distance to a polyline and arc-length parameter of the nearest point."""
    points = np.asarray(points, float)
    a, delta = curve[:-1], np.diff(curve, axis=0)
    length = np.linalg.norm(delta, axis=1)
    arc = np.r_[0., np.cumsum(length)]
    squared = np.maximum(1e-30, length * length)
    distance, parameter = np.empty(len(points)), np.empty(len(points))
    for first in range(0, len(points), 512):
        batch = points[first:first + 512]
        t = np.clip(((batch[:, None] - a) * delta).sum(2) / squared, 0, 1)
        gap = ((batch[:, None] - a - t[:, :, None] * delta) ** 2).sum(2)
        ids, rows = gap.argmin(1), np.arange(len(batch))
        distance[first:first + len(batch)] = np.sqrt(gap[rows, ids])
        parameter[first:first + len(batch)] = arc[ids] + t[rows, ids] * length[ids]
    return distance, parameter


def find_row(vertices, output_edges, curve, closed, spacing):
    """Cheapest connected output edge path that runs forward along a chain, or [] when there is none.

    Engineering choice, reusing the cost of authored guide paths
    (curved_quad._guide_path): an edge costs its length times
    (1 + 40 (distance / spacing)^2). An open path may start and stop short of
    the chain ends at the integral of the same cost over the chain arc it
    leaves uncovered. No edge may step backward along the chain. Vertices
    farther than the one-face end maximum cannot be on an accepted row and
    are left out.
    """
    vertices = np.asarray(vertices, float)
    curve = np.asarray(curve, float)
    count = len(vertices)
    distance, parameter = _nearest(vertices, curve)
    total = float(_arc(curve)[-1])
    allowed = distance <= ROW_END_FACES * spacing
    pairs = np.asarray(output_edges, int).reshape(-1, 2)
    pairs = pairs[allowed[pairs[:, 0]] & allowed[pairs[:, 1]]]
    if not len(pairs) or total <= 0:
        return []
    pairs = np.r_[pairs, pairs[:, ::-1]]
    a, b = pairs[:, 0], pairs[:, 1]
    length = np.linalg.norm(vertices[b] - vertices[a], axis=1)
    weight = length * (1 + 40 * ((distance[a] + distance[b]) * .5 / spacing) ** 2)
    if closed:
        start = int(np.flatnonzero(allowed)[np.argmin(distance[allowed])])
        parameter = (parameter - parameter[start]) % total
        raw = parameter[b] - parameter[a]
        step = (raw + total / 2) % total - total / 2
        keep = (step >= 0) & (length > 0)
        a, b, weight, wrap = a[keep], b[keep], weight[keep], np.rint((step[keep] - raw[keep]) / total).astype(int)
        same, cross = wrap == 0, wrap == 1
        rows = np.r_[a[same], a[same] + count, a[cross]]
        cols = np.r_[b[same], b[same] + count, b[cross] + count]
        graph = csr_matrix((np.r_[weight[same], weight[same], weight[cross]], (rows, cols)), shape=(2 * count, 2 * count))
        origin, sink = start, start + count
    else:
        keep = (parameter[b] - parameter[a] >= 0) & (length > 0)
        a, b, weight = a[keep], b[keep], weight[keep]
        ids = np.flatnonzero(allowed)

        def uncovered(reach):
            return reach + 40 * reach ** 3 / (3 * spacing ** 2)
        origin, sink = count, count + 1
        rows = np.r_[a, np.full(len(ids), origin), ids]
        cols = np.r_[b, ids, np.full(len(ids), sink)]
        costs = np.r_[weight, uncovered(np.linalg.norm(vertices[ids] - curve[0], axis=1)),
                      uncovered(np.linalg.norm(vertices[ids] - curve[-1], axis=1))]
        graph = csr_matrix((np.maximum(costs, 1e-300), (rows, cols)), shape=(count + 2, count + 2))
    cost, predecessor = dijkstra(graph, indices=origin, return_predecessors=True)
    if not np.isfinite(cost[sink]):
        return []
    path, current = [], int(sink)
    while current != origin:
        path.append(current)
        current = int(predecessor[current])
    path.append(origin)
    path = [v % count for v in path[::-1]] if closed else [v for v in path[::-1] if v < count]
    unique = path[:-1] if closed else path
    if len(set(unique)) != len(unique) or len(unique) < (3 if closed else 2):
        return []
    return path


def _samples(curve, spacing):
    """Chain vertices plus samples at the crease check's spacing, in order."""
    arc = _arc(curve)
    parameters = np.unique(np.r_[arc, np.linspace(0., arc[-1], int(np.ceil(arc[-1] / (SAMPLE_FACES * spacing))) + 1)])
    return _at(curve, arc, parameters)


def _window_chords(points, window, closed):
    """Chord over `window` of arc length around each sample (one face, as the guide check measures direction)."""
    arc = _arc(points)
    total = arc[-1]
    if closed:
        return _at(points, arc, np.mod(arc + window * .5, total)) - _at(points, arc, np.mod(arc - window * .5, total))
    low = np.clip(arc - window * .5, 0, max(0., total - window))
    return _at(points, arc, np.minimum(low + window, total)) - _at(points, arc, low)


SPAN_STEPS = 9   # points across a band span: finer than the crease check's sample spacing at the half-face reach


def _band_spans(samples, partners, spacing):
    """For each chain sample, the far end of its band: the farthest partner crease point within reach.

    The band a row represents is the strip between its representative crease
    and the parallel creases it absorbs. Its cross-section at a sample runs
    from the sample to the farthest partner edge within BAND_REACH; a sample
    with no partner in reach has a span of zero length.
    """
    from source_features import BAND_REACH
    far = samples.copy()
    if partners is None or not len(partners[0]):
        return far
    starts, ends = partners
    delta = ends - starts
    squared = np.maximum(1e-30, (delta * delta).sum(1))
    for first in range(0, len(samples), 256):
        batch = samples[first:first + 256]
        t = np.clip(((batch[:, None] - starts) * delta).sum(2) / squared, 0, 1)
        points = starts + t[:, :, None] * delta
        distance = np.linalg.norm(points - batch[:, None], axis=2)
        distance[distance >= BAND_REACH * spacing] = -1.
        pick = distance.argmax(1)
        rows = np.arange(len(batch))
        found = distance[rows, pick] >= 0
        far[first:first + len(batch)][found] = points[rows, pick][found]
    return far


def measure_path(vertices, path, curve, closed, spacing, partners=None):
    """Distances and directions from a chain's band to one connected path: (values, worst sample).

    The distance at a chain sample is the least distance from the path to the
    band span at that sample (the representative crease point when the band
    has no partner there), so a row anywhere across the band it represents
    measures zero and a row beside the band measures its gap to the band.
    """
    vertices = np.asarray(vertices, float)
    samples = _samples(np.asarray(curve, float), spacing)
    far = _band_spans(samples, partners, spacing)
    a, b = vertices[path[:-1]], vertices[path[1:]]
    delta = b - a
    squared = np.maximum(1e-30, (delta * delta).sum(1))
    distance = np.full(len(samples), np.inf)
    nearest = np.zeros(len(samples), int)
    for fraction in np.linspace(0., 1., SPAN_STEPS):
        points = samples + fraction * (far - samples)
        t = np.clip(((points[:, None] - a) * delta).sum(2) / squared, 0, 1)
        gaps = np.linalg.norm(points[:, None] - a - t[:, :, None] * delta, axis=2)
        ids = gaps.argmin(1)
        values = gaps[np.arange(len(samples)), ids]
        closer = values < distance
        distance[closer], nearest[closer] = values[closer], ids[closer]
    chords = _window_chords(samples, spacing, closed)
    norms = np.linalg.norm(chords, axis=1) * np.sqrt(squared[nearest])
    cosine = np.divide(np.abs((chords * delta[nearest]).sum(1)), norms, out=np.ones(len(samples)), where=norms > 0)
    angles = np.degrees(np.arccos(np.clip(cosine, 0, 1)))
    arc = _arc(samples)
    # The last face of arc at each end of an open chain is where it meets a junction or
    # fades out; a coarse row ends up to half an edge from it. That zone answers to the
    # one-face junction limit, the rest of the chain to the quarter- and half-face limits.
    ends = np.zeros(len(samples), bool) if closed else np.minimum(arc, arc[-1] - arc) < ROW_END_FACES * spacing
    inner = ~ends
    values = dict(rowP95=float(np.percentile(distance[inner], 95)) if inner.any() else 0.,
                  rowMax=float(distance[inner].max()) if inner.any() else 0.,
                  rowEndMax=float(distance[ends].max()) if ends.any() else 0.,
                  rowTangentP95Degrees=float(np.percentile(angles[inner], 95)) if inner.any() else 0.)
    return values, samples[int(distance.argmax())]


def measure(source, triangles, edges, vertices, faces, spacing):
    """Row report: every representative crease chain needs one connected, ordered output edge path.

    Each chain is measured to its own path only. The path has to lie on the
    band the chain represents: distances are taken from the band span (the
    strip between the representative and the parallel creases it absorbs), not
    from the representative minus a scalar allowance, so a row beside the band
    is charged its full gap whichever side it is on. The absorbed creases get
    no row of their own; they stay under the nearest-edge measure.
    """
    source, vertices = np.asarray(source, float), np.asarray(vertices, float)
    edges = np.asarray(edges, int).reshape(-1, 2)
    faces = np.asarray(faces, int)
    limits = dict(rowP95=ROW_P95_FACES * spacing, rowMax=ROW_MAX_FACES * spacing, rowEndMax=ROW_END_FACES * spacing,
                  rowTangentP95Degrees=ROW_TANGENT_DEGREES)
    rows, chosen, absorbed = representatives(source, triangles, edges, spacing)
    report = dict(policy=POLICY, minimumFaces=ROW_MIN_FACES, limits=limits, chains=[], required=len(rows), realized=0, passed=True,
                  representativeEdges=int(chosen.sum()), absorbedEdges=int(absorbed.sum()),
                  scope='One representative crease per band of parallel creases (the one bordering the wider sheet), joined into chains; '
                        'chains at least two requested faces in extent are each measured to one connected, forward-ordered output edge path. '
                        'Distance is from that path to the band span at each chain sample (the strip between the representative and the parallel '
                        'creases it absorbs); direction over one requested face; the last face of arc at each open end answers to the one-face '
                        'end limit only. Absorbed and shorter creases remain under the nearest-edge measure.')
    if not rows:
        return report
    output_edges = np.unique(np.sort(np.stack([faces, np.roll(faces, -1, 1)], axis=2).reshape(-1, 2), axis=1), axis=0)
    for row in rows:
        chain, closed = row['vertices'], row['closed']
        item = dict(sourceVertices=[int(chain[0]), int(chain[-1])], sourceVertexCount=len(chain), closed=closed, lengthFaces=row['length'] / spacing)
        path = find_row(vertices, output_edges, source[chain], closed, spacing)
        if not path:
            item.update(vertices=[], passed=False, failures=['rowMissing'])
        else:
            # The partners depend on the source only; they are kept with the representatives.
            partners = _MEMO.setdefault('partners', {})
            name = (chain[0], chain[-1], len(chain))
            if name not in partners:
                partners[name] = band_edges(source, edges, [row], spacing)[1]
            partner = partners[name]
            values, worst = measure_path(vertices, path, source[chain], closed, spacing,
                                         (source[edges[partner, 0]], source[edges[partner, 1]]))
            item['bandPartnerEdges'] = int(partner.sum())
            failures = [key for key, value in values.items() if value > limits[key]]
            item.update(vertices=[int(v) for v in path], values=values, worstSample=worst.tolist(), passed=not failures, failures=failures)
        report['chains'].append(item)
    report['realized'] = sum(item['passed'] for item in report['chains'])
    report['passed'] = report['realized'] == report['required']
    return report
