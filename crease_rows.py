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

Local face sizes (2026-11-10, the user's 'Add faces where the shape needs
them' option only). Every function that takes `sizes` then measures "a face"
at a crease edge as that edge's local face (local_sizes), not the requested
one: the band reach, the two-face minimum, the row limits and the end zones.
With `sizes=None` every result is what it was before.
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
# The smallest local face a crease chain may ask for, as a fraction of the requested face.
# ZRemesher's size field never goes below 0.9 * S / 4 (0x1efb00, qualified constants: a ratio of 4
# with a factor of 0.9), and the layout engine clamps its field there. Engineering choice: a crease
# asks for the ratio of 4 without the 0.9, so no row is sized at the clamp itself. Measured on
# island 6 at 200 (64 layouts, 2026-11-10): the two 0.52-face chains sized at 0.237 had a row
# within reach in 10 and 22 layouts, and ZBrush's own mesh has no row on either.
SIZE_FLOOR = 1 / 4


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


def local_sizes(source, edges, spacing, minimum_length=None):
    """Face size at each admitted crease edge, as a fraction of the requested size (1 = requested).

    Only used when the user allows extra faces. Native ZRemesher keeps every
    admitted crease edge as a constrained edge through extraction (collector
    0x2889c0/0x28e230) and separates constrained lines in its integer solve
    (0x28fe70) whatever their distance, at the requested base size; kept
    creases do not shrink its size field (0x26faf0 marks). This application's
    layout engine has no such separation: it rounds positions to a lattice of
    the local face size, so a crease chain shorter than two local faces cannot
    carry a row (ROW_MIN_FACES). Engineering choice, standing in for the
    native separation: the faces at a chain are made small enough for the row,

        size = extent / ROW_MIN_FACES,   clamped to [floor, 1] of the requested size,

    where the extent is the largest distance between two points of the chain
    and chains are the admitted crease graph joined as chains() joins it. The
    floor is SIZE_FLOOR, and never less than half of `minimum_length`, the
    native minimum feature length S = sqrt(A / clamp(target, 1000, 10000))
    (source_features.admission_length; 0x1c9fb0/0x25a990): ZRemesher admits no
    feature shorter than S, so no row is asked of a chain shorter than S and no
    face is asked smaller than a row of two on a feature of length S. (S is
    under half a requested face below a request of 250; from 1,000 up it is the
    requested face itself and the floor is a half.) A chain whose extent is
    under ROW_MIN_FACES faces of the floor size cannot carry a row at any
    allowed size; it asks for the floor size, gets no row and stays under the
    nearest-edge measure. (Measured on island 6 at 200,
    one search of 64 layouts each, 2026-11-10: leaving those short chains at
    the requested size, 2 of 7 fitted layouts passed every check and the
    source lay up to 0.32 of a face from the result at the end of the step
    behind each foot; sizing them, 2 of the first 3 passed, at 0.26 or less.)
    The sizes go to the engine as face-size caps on its constrained edges and
    are the "local face" of the band rule and the row check, so generator and
    check agree by construction.
    """
    source = np.asarray(source, float)
    edges = np.asarray(edges, int).reshape(-1, 2)
    sizes = np.ones(len(edges))
    if not len(edges):
        return sizes
    lookup = {tuple(sorted(map(int, e))): i for i, e in enumerate(edges)}
    floor = SIZE_FLOOR if minimum_length is None else min(1., max(SIZE_FLOOR, float(minimum_length) / (ROW_MIN_FACES * spacing)))
    for vertices, _ in chains(source, edges, spacing):
        points = source[vertices]
        probe = points[np.unique(np.linspace(0, len(points) - 1, min(len(points), 64)).round().astype(int))]
        extent = float(np.linalg.norm(probe[:, None] - probe[None], axis=2).max()) / spacing
        size = min(1., max(floor, extent / ROW_MIN_FACES))
        for pair in zip(vertices[:-1], vertices[1:]):
            sizes[lookup[tuple(sorted(pair))]] = size
    return sizes


def _point_sizes(vertices, lookup, sizes):
    """Local face fraction at each vertex of a chain: the smaller of its two chain edges' sizes."""
    per_edge = np.array([sizes[lookup[tuple(sorted(pair))]] for pair in zip(vertices[:-1], vertices[1:])])
    return np.minimum(np.r_[per_edge[0], per_edge], np.r_[per_edge, per_edge[-1]])


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


def representatives(source, triangles, edges, spacing, sizes=None):
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

    With `sizes` (local_sizes, one fraction per edge) a face is the local face:
    an edge is within reach at BAND_REACH of its own local face, a chain needs
    a row at ROW_MIN_FACES of its smallest local face, and each row also holds
    `sizes`, the local face fraction at each of its vertices.
    """
    from source_features import BAND_REACH, BAND_DEGREES, segment_distances
    source = np.asarray(source, float)
    triangles = np.asarray(triangles, int)
    edges = np.asarray(edges, int).reshape(-1, 2)
    # One job measures many candidates against the same source: the answer depends on the
    # source, its admitted creases and the spacing only, so the last one is kept.
    sizes = None if sizes is None else np.asarray(sizes, float).reshape(-1)
    key = (source.shape, source.tobytes(), triangles.tobytes(), edges.tobytes(), float(spacing), None if sizes is None else sizes.tobytes())
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
            near = segment_distances(source[np.unique(edges[ids])], starts, ends)
            near = dict(zip(np.unique(edges[ids]).tolist(), near.tolist()))
            reach = BAND_REACH * spacing * (np.ones(len(ids)) if sizes is None else sizes[ids])
            inside = np.array([near[int(a)] < r and near[int(b)] < r for (a, b), r in zip(edges[ids], reach)])
            if inside.any():
                parallel = _parallel(source[edges[ids[inside], 0]], source[edges[ids[inside], 1]], starts, ends) >= cosine_limit
                absorbed[ids[inside][parallel]] = True
        if lengths[ids][absorbed[ids]].sum() > .5 * lengths[ids].sum():
            absorbed[ids] = True
            continue
        absorbed[ids] = False
        chosen[ids] = True
    rows = []
    if sizes is None:
        candidates = chains(source, edges[chosen], spacing)
    else:
        # With local faces the chains are those local_sizes sized: the admitted crease graph joined as
        # a whole, then cut to their runs of representative edges. Joining the representatives alone
        # would run a chain round a corner wherever an absorbed crease used to make a junction.
        candidates = []
        for vertices, closed in chains(source, edges, spacing):
            kept = [bool(chosen[lookup[tuple(sorted(pair))]]) for pair in zip(vertices[:-1], vertices[1:])]
            if all(kept):
                candidates.append((vertices, closed))
                continue
            first = None
            for index, flag in enumerate(kept + [False]):
                if flag and first is None:
                    first = index
                elif not flag and first is not None:
                    candidates.append((vertices[first:index + 1], False))
                    first = None
    for vertices, closed in candidates:
        points = source[vertices]
        length = float(_arc(points)[-1])
        local = None if sizes is None else _point_sizes(vertices, lookup, sizes)
        # A chain sized by its own extent measures exactly ROW_MIN_FACES local faces; the factor keeps rounding from dropping it.
        minimum = ROW_MIN_FACES * spacing * (1. if local is None else float(local.min()) * (1 - 1e-9))
        if length < minimum:
            continue
        probe = points[np.unique(np.linspace(0, len(points) - 1, min(len(points), 64)).round().astype(int))]
        extent = float(np.linalg.norm(probe[:, None] - probe[None], axis=2).max())
        if extent >= minimum:
            rows.append(dict(vertices=vertices, closed=closed, length=length) if local is None
                        else dict(vertices=vertices, closed=closed, length=length, sizes=local.tolist()))
    rows.sort(key=lambda row: (-row['length'], row['vertices'][0], row['vertices'][-1]))
    _MEMO.clear()
    _MEMO.update(key=key, value=([dict(row, vertices=list(row['vertices'])) for row in rows], chosen.copy(), absorbed.copy()))
    return rows, chosen, absorbed


def _row_sizes(row):
    """Local face fraction at each vertex of a row chain, or None when faces are the requested ones."""
    return None if row.get('sizes') is None else np.asarray(row['sizes'], float)


def band_edges(source, edges, rows, spacing, sizes=None):
    """Masks over `edges`: the row chains' own edges, and the other crease edges inside their bands.

    A crease edge is inside a row's band by the existing band rule: both ends
    within BAND_REACH of the requested spacing of the row chains and running
    within BAND_DEGREES of the nearest one. With `sizes` the reach is
    BAND_REACH of the edge's own local face.
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
    near = segment_distances(source, starts, ends)
    reach = BAND_REACH * spacing * (np.ones(len(edges)) if sizes is None else np.asarray(sizes, float).reshape(-1))
    candidates = np.flatnonzero((near[edges[:, 0]] < reach) & (near[edges[:, 1]] < reach) & ~own)
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


def find_row(vertices, output_edges, curve, closed, spacing, sizes=None):
    """Cheapest connected output edge path that runs forward along a chain, or [] when there is none.

    Engineering choice, reusing the cost of authored guide paths
    (curved_quad._guide_path): an edge costs its length times
    (1 + 40 (distance / spacing)^2). An open path may start and stop short of
    the chain ends at the integral of the same cost over the chain arc it
    leaves uncovered. No edge may step backward along the chain. Vertices
    farther than the one-face end maximum cannot be on an accepted row and
    are left out. With `sizes` (the local face fraction at each chain point)
    a face is the local face at the nearest point of the chain.
    """
    vertices = np.asarray(vertices, float)
    curve = np.asarray(curve, float)
    count = len(vertices)
    distance, parameter = _nearest(vertices, curve)
    total = float(_arc(curve)[-1])
    if sizes is not None:
        # One face is the local face at the nearest chain point; `spacing` becomes a value per output vertex.
        spacing = spacing * np.interp(parameter, _arc(curve), np.asarray(sizes, float))
    allowed = distance <= ROW_END_FACES * spacing
    pairs = np.asarray(output_edges, int).reshape(-1, 2)
    pairs = pairs[allowed[pairs[:, 0]] & allowed[pairs[:, 1]]]
    if not len(pairs) or total <= 0:
        return []
    pairs = np.r_[pairs, pairs[:, ::-1]]
    a, b = pairs[:, 0], pairs[:, 1]
    length = np.linalg.norm(vertices[b] - vertices[a], axis=1)
    if sizes is None:
        weight = length * (1 + 40 * ((distance[a] + distance[b]) * .5 / spacing) ** 2)
    else:
        # A local face can be as long as a short chain's bend is deep, so a chord across the bend would
        # cost no more than the edges round it if only its ends were measured. The middle of the edge
        # is measured too (weights 1, 2, 1: the mean distance along the edge).
        middle = _nearest((vertices[a] + vertices[b]) * .5, curve)[0]
        weight = length * (1 + 40 * ((distance[a] + 2 * middle + distance[b]) * .25 / ((spacing[a] + spacing[b]) * .5)) ** 2)
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
            return reach + 40 * reach ** 3 / (3 * (spacing if sizes is None else spacing[ids]) ** 2)
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


def _band_spans(samples, partners, spacing, local=None):
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
        distance[distance >= (BAND_REACH * spacing if local is None else (BAND_REACH * spacing * local[first:first + 256])[:, None])] = -1.
        pick = distance.argmax(1)
        rows = np.arange(len(batch))
        found = distance[rows, pick] >= 0
        far[first:first + len(batch)][found] = points[rows, pick][found]
    return far


def measure_path(vertices, path, curve, closed, spacing, partners=None, sizes=None):
    """Distances and directions from a chain's band to one connected path: (values, worst sample).

    The distance at a chain sample is the least distance from the path to the
    band span at that sample (the representative crease point when the band
    has no partner there), so a row anywhere across the band it represents
    measures zero and a row beside the band measures its gap to the band.

    With `sizes` (the local face fraction at each chain point) every distance
    is divided by the fraction at its sample before the percentile and the
    maximum are taken, so the values compare with the same limits and read
    "in local faces" once divided by the requested spacing; samples, direction
    windows and end zones are sized by the local face as well.
    """
    vertices = np.asarray(vertices, float)
    curve = np.asarray(curve, float)
    finest = spacing if sizes is None else spacing * float(np.min(sizes))
    samples = _samples(curve, finest)
    local = None
    if sizes is not None:
        local = np.interp(_nearest(samples, curve)[1], _arc(curve), np.asarray(sizes, float))
    far = _band_spans(samples, partners, spacing, local)
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
    chords = _window_chords(samples, finest, closed)
    # Direction compares the same stretch on both sides: the nearest row edge against the chain
    # between the nearest chain points of that edge's two ends. The chain's one-face chord against
    # a single row edge charged a corner of the chain itself to a row lying on it (island 6 feet,
    # a 95 degree corner at a plain chain vertex: ZBrush's row 0.01 h from the crease read 33
    # degrees at 7,200). An edge whose ends meet the chain at one point covers no stretch and
    # answers to the chain's one-face chord at the sample.
    on_chain = _at(curve, _arc(curve), _nearest(vertices[path], curve)[1])
    stretch = np.diff(on_chain, axis=0)[nearest]
    covered = np.linalg.norm(stretch, axis=1) > 1e-9 * finest
    chords[covered] = stretch[covered]
    norms = np.linalg.norm(chords, axis=1) * np.sqrt(squared[nearest])
    cosine = np.divide(np.abs((chords * delta[nearest]).sum(1)), norms, out=np.ones(len(samples)), where=norms > 0)
    angles = np.degrees(np.arccos(np.clip(cosine, 0, 1)))
    arc = _arc(samples)
    # The last face of arc at each end of an open chain is where it meets a junction or
    # fades out; a coarse row ends up to half an edge from it. That zone answers to the
    # one-face junction limit, the rest of the chain to the quarter- and half-face limits.
    worst = samples[int(distance.argmax())]
    if local is None:
        ends = np.zeros(len(samples), bool) if closed else np.minimum(arc, arc[-1] - arc) < ROW_END_FACES * spacing
    else:
        ends = np.zeros(len(samples), bool) if closed else (arc < ROW_END_FACES * spacing * local[0]) | (arc[-1] - arc < ROW_END_FACES * spacing * local[-1])
        distance = distance / local
        worst = samples[int(distance.argmax())]
    inner = ~ends
    values = dict(rowP95=float(np.percentile(distance[inner], 95)) if inner.any() else 0.,
                  rowMax=float(distance[inner].max()) if inner.any() else 0.,
                  rowEndMax=float(distance[ends].max()) if ends.any() else 0.,
                  rowTangentP95Degrees=float(np.percentile(angles[inner], 95)) if inner.any() else 0.)
    return values, worst


def measure(source, triangles, edges, vertices, faces, spacing, sizes=None):
    """Row report: every representative crease chain needs one connected, ordered output edge path.

    Each chain is measured to its own path only. The path has to lie on the
    band the chain represents: distances are taken from the band span (the
    strip between the representative and the parallel creases it absorbs), not
    from the representative minus a scalar allowance, so a row beside the band
    is charged its full gap whichever side it is on. The absorbed creases get
    no row of their own; they stay under the nearest-edge measure.

    `sizes`: local_sizes when the user allows extra faces. A face is then the
    local face at each crease edge, in the band rule, the two-face minimum and
    every limit; each chain reports its smallest local face (`faceSize`).
    """
    source, vertices = np.asarray(source, float), np.asarray(vertices, float)
    edges = np.asarray(edges, int).reshape(-1, 2)
    faces = np.asarray(faces, int)
    limits = dict(rowP95=ROW_P95_FACES * spacing, rowMax=ROW_MAX_FACES * spacing, rowEndMax=ROW_END_FACES * spacing,
                  rowTangentP95Degrees=ROW_TANGENT_DEGREES)
    rows, chosen, absorbed = representatives(source, triangles, edges, spacing, sizes)
    report = dict(policy=POLICY, minimumFaces=ROW_MIN_FACES, limits=limits, chains=[], required=len(rows), realized=0, passed=True,
                  representativeEdges=int(chosen.sum()), absorbedEdges=int(absorbed.sum()),
                  scope='One representative crease per band of parallel creases (the one bordering the wider sheet), joined into chains; '
                        'chains at least two requested faces in extent are each measured to one connected, forward-ordered output edge path. '
                        'Distance is from that path to the band span at each chain sample (the strip between the representative and the parallel '
                        'creases it absorbs); direction over one requested face; the last face of arc at each open end answers to the one-face '
                        'end limit only. Absorbed and shorter creases remain under the nearest-edge measure.')
    if sizes is not None:
        report.update(localFaces=True, smallestLocalFace=float(np.min(sizes)) if len(sizes) else 1., sizedEdges=int((np.asarray(sizes) < 1).sum()),
                      localFaceScope='Extra faces allowed: a face is the local face at each crease edge (chain extent / '
                                     f'{ROW_MIN_FACES:g}, at most the requested face, at least {SIZE_FLOOR:g} of it and at least half of the native '
                                     'minimum feature length). The band reach, the two-face minimum, the '
                                     'limits and the end zones use it; values are distances divided by the local face fraction, so they compare '
                                     'with the same limits.')
    if not rows:
        return report
    output_edges = np.unique(np.sort(np.stack([faces, np.roll(faces, -1, 1)], axis=2).reshape(-1, 2), axis=1), axis=0)
    for row in rows:
        chain, closed = row['vertices'], row['closed']
        item = dict(sourceVertices=[int(chain[0]), int(chain[-1])], sourceVertexCount=len(chain), closed=closed, lengthFaces=row['length'] / spacing)
        local = _row_sizes(row)
        if local is not None:
            item['faceSize'] = float(local.min())
        path = find_row(vertices, output_edges, source[chain], closed, spacing, local)
        if not path:
            item.update(vertices=[], passed=False, failures=['rowMissing'])
        else:
            # The partners depend on the source only; they are kept with the representatives.
            partners = _MEMO.setdefault('partners', {})
            name = (chain[0], chain[-1], len(chain))
            if name not in partners:
                partners[name] = band_edges(source, edges, [row], spacing, sizes)[1]
            partner = partners[name]
            values, worst = measure_path(vertices, path, source[chain], closed, spacing,
                                         (source[edges[partner, 0]], source[edges[partner, 1]]), local)
            item['bandPartnerEdges'] = int(partner.sum())
            failures = [key for key, value in values.items() if value > limits[key]]
            item.update(vertices=[int(v) for v in path], values=values, worstSample=worst.tolist(), passed=not failures, failures=failures)
        report['chains'].append(item)
    report['realized'] = sum(item['passed'] for item in report['chains'])
    report['passed'] = report['realized'] == report['required']
    return report
