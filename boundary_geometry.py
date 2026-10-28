"""Manifold boundary cycles and bidirectional whole-segment distance bounds."""
from collections import defaultdict
import numpy as np
from scipy.optimize import linear_sum_assignment


def loops(faces):
    edges = defaultdict(list)
    for row in faces:
        for a, b in zip(row, np.roll(row, -1)):
            edges[tuple(sorted((int(a), int(b))))].append((int(a), int(b)))
    if any(len(x) > 2 for x in edges.values()):
        raise ValueError('A surface boundary requires manifold edges.')
    boundary = [rows[0] for rows in edges.values() if len(rows) == 1]
    following = dict(boundary)
    if len(following) != len(boundary) or len(set(following.values())) != len(boundary):
        raise ValueError('The source boundary branches or has inconsistent winding.')
    remaining = set(following); result = []
    while remaining:
        start = min(remaining); ring = [start]; remaining.remove(start)
        while following[ring[-1]] != start:
            nxt = following[ring[-1]]
            if nxt not in remaining: raise ValueError('The boundary is not a simple cycle.')
            remaining.remove(nxt); ring.append(nxt)
        if len(ring) < 3: raise ValueError('A boundary needs at least three vertices.')
        result.append(np.asarray(ring, int))
    return result


def closest(points, ring):
    start = ring; delta = np.roll(ring, -1, axis=0) - ring
    denom = (delta * delta).sum(1)
    if np.any(denom <= 0): raise ValueError('Zero-length source boundary segment.')
    t = np.clip(((points[:, None] - start) * delta).sum(2) / denom, 0, 1)
    candidates = start + t[:, :, None] * delta
    distance = ((points[:, None] - candidates)**2).sum(2)
    ids = distance.argmin(1)
    return candidates[np.arange(len(points)), ids], np.sqrt(distance[np.arange(len(points)), ids]), ids


def correspondence(source, source_faces, output, output_faces):
    original, generated = loops(source_faces), loops(output_faces)
    if len(original) != len(generated): raise ValueError('Remeshing changed the number of boundary loops.')
    costs = np.asarray([[np.mean(closest(output[b], source[a])[1]) for a in original] for b in generated])
    if not len(generated): return []
    rows, cols = linear_sum_assignment(costs)
    return [(generated[i], original[j]) for i, j in zip(rows, cols)]


def fit_ring(points, ring):
    """Fit an ordered cycle by arc length, anchoring sharp source corners.

    Independent nearest-point projection can collapse neighboring vertices at a
    corner or cut that corner off. This retains cyclic order and distinct samples.
    The ordinary acceptance bounds still decide whether the result is usable.
    """
    points = np.asarray(points, float); ring = np.asarray(ring, float)
    delta = np.roll(ring, -1, axis=0) - ring; length = np.linalg.norm(delta, axis=1)
    if np.any(length <= 0): raise ValueError('Zero-length source boundary segment.')
    cumulative = np.r_[0., np.cumsum(length)]; total = cumulative[-1]
    projected, _, segment = closest(points, ring)
    arc = cumulative[segment] + np.linalg.norm(projected - ring[segment], axis=1)
    step = (np.roll(arc, -1) - arc + total / 2) % total - total / 2
    reverse = step.sum() < 0
    if reverse: points = points[::-1]; arc = arc[::-1]
    unit = delta / length[:, None]
    corners = np.flatnonzero((unit * np.roll(unit, 1, axis=0)).sum(1) < np.cos(np.deg2rad(30)))
    if len(corners) > len(points): raise ValueError('The layout has too few boundary vertices to preserve source corners.')
    if len(corners):
        rows, cols = linear_sum_assignment(np.linalg.norm(ring[corners, None] - points[None], axis=2))
        anchors = sorted((int(col), float(cumulative[corners[row]])) for row, col in zip(rows, cols))
    else: anchors = [(0, float(arc[0]))]
    distances = [(anchors[(i + 1) % len(anchors)][1] - a[1]) % total for i, a in enumerate(anchors)] if len(anchors) > 1 else [total]
    if not np.isclose(sum(distances), total): raise ValueError('Boundary corner assignment would reverse cyclic order.')
    fitted = np.empty(len(points))
    for i, (start, value) in enumerate(anchors):
        end = anchors[(i + 1) % len(anchors)][0]; count = (end - start) % len(points) or len(points)
        ids = (start + np.arange(count + 1)) % len(points)
        weights = np.linalg.norm(np.diff(points[ids], axis=0), axis=1)
        # Native zero-length edges must not create repeated boundary samples.
        weights = np.maximum(weights, total / len(points) * .1)
        fitted[ids[:-1]] = (value + np.r_[0., np.cumsum(weights)[:-1]] / weights.sum() * distances[i]) % total
    ids = np.minimum(np.searchsorted(cumulative, fitted, side='right') - 1, len(ring) - 1)
    output = ring[ids] + ((fitted - cumulative[ids]) / length[ids])[:, None] * delta[ids]
    return output[::-1] if reverse else output


def conform_ring(points, ring, tolerance):
    """Keep an output boundary cycle on the source boundary without cutting its bends.

    Output vertices start at their nearest source-boundary points. While a
    source vertex lies farther than half the tolerance from the output chord,
    the nearest unanchored output vertex (by arc length, in cyclic order) moves
    onto it and the free vertices between neighboring anchors are re-spaced
    along the source boundary. Only vertices near a cut bend move, by about
    half an edge, so the adjoining quads keep their shape.
    """
    points = np.asarray(points, float); ring = np.asarray(ring, float); n = len(points)
    delta = np.roll(ring, -1, axis=0) - ring; length = np.linalg.norm(delta, axis=1)
    if np.any(length <= 0): raise ValueError('Zero-length source boundary segment.')
    cumulative = np.r_[0., np.cumsum(length)]; total = cumulative[-1]
    projected, _, segment = closest(points, ring)
    arc = cumulative[segment] + np.linalg.norm(projected - ring[segment], axis=1)
    step = (np.roll(arc, -1) - arc + total / 2) % total - total / 2
    if step.sum() < 0: return conform_ring(points[::-1], ring, tolerance)[::-1]
    # Unwrapped arc positions, nondecreasing in output order.
    arc = arc[0] + np.r_[0., np.cumsum(np.maximum(step[:-1], 0))]
    anchors = {}

    def place(values):
        values = values % total; ids = np.minimum(np.searchsorted(cumulative, values, side='right') - 1, len(ring) - 1)
        return ring[ids] + ((values - cumulative[ids]) / length[ids])[:, None] * delta[ids]

    def order_bounds(i):
        # Neighboring anchors in cyclic output order; a new anchor must fit strictly between them.
        lower = [anchors[j] for j in anchors if j < i]; upper = [anchors[j] for j in anchors if j > i]
        if not anchors: return -np.inf, np.inf
        return (max(lower) if lower else max(anchors.values()) - total,
                min(upper) if upper else min(anchors.values()) + total)

    def shift(i, goal, reach=3):
        # Move vertex i to its goal; free neighbors follow with a tapering share so order holds.
        change = goal - arc[i]; arc[i] = goal
        for direction in (1, -1):
            for k in range(1, reach + 1):
                j = (i + direction * k) % n
                if j in anchors or j == i: break
                arc[j] += change * (1 - k / (reach + 1))

    for _ in range(len(ring)):
        current = place(arc); chord = np.roll(current, -1, axis=0) - current
        t = np.clip(((ring[:, None] - current) * chord).sum(2) / np.maximum(1e-30, (chord * chord).sum(1)), 0, 1)
        deviation = np.linalg.norm(ring[:, None] - current - t[:, :, None] * chord, axis=2).min(1)
        moved = False
        for vertex in np.argsort(-deviation):
            if deviation[vertex] <= tolerance * .5: break
            gap = np.abs((arc - cumulative[vertex] + total / 2) % total - total / 2)
            for i in [i for i in np.argsort(gap) if i not in anchors][:2]:
                goal = cumulative[vertex] + total * np.round((arc[i] - cumulative[vertex]) / total)
                below, above = order_bounds(i)
                local = (arc[(i + 1) % n] - arc[i - 1]) % total / 2
                if below < goal < above and abs(goal - arc[i]) <= .6 * local:
                    shift(i, goal); anchors[i] = goal; moved = True; break
            if moved: break
        if not moved: break
    return place(arc)


def directed_bound(ring, target, tolerance):
    pending = np.stack([ring, np.roll(ring, -1, axis=0)], axis=1)
    upper = 0.; tested = 0
    for depth in range(14):
        tested += len(pending)
        if tested > 200000: break
        mid = pending.mean(1); _, _, ids = closest(mid, target)
        a = target[ids]; d = target[(ids + 1) % len(target)] - a
        t = np.clip(((pending - a[:, None]) * d[:, None]).sum(2) / (d * d).sum(1)[:, None], 0, 1)
        bounds = np.linalg.norm(pending - a[:, None] - t[:, :, None] * d[:, None], axis=2).max(1)
        done = bounds <= tolerance
        if done.any(): upper = max(upper, float(bounds[done].max()))
        unresolved = pending[~done]
        if not len(unresolved): return dict(passed=True, maximumUpperBound=upper, testedSegments=tested)
        _, distances, _ = closest(unresolved.reshape(-1, 3), target)
        if distances.max() > tolerance: return dict(passed=False, sampledMax=float(distances.max()), testedSegments=tested)
        mid = unresolved.mean(1); pending = np.concatenate([np.stack([unresolved[:, 0], mid], 1), np.stack([mid, unresolved[:, 1]], 1)])
    return dict(passed=False, reason='Boundary distance budget exhausted', testedSegments=tested)


def validate(source, source_faces, output, output_faces, tolerance):
    try: mapping = correspondence(source, source_faces, output, output_faces)
    except ValueError as error: return dict(passed=False, reason=str(error))
    reports = [dict(sourceToOutput=directed_bound(source[a], output[b], tolerance),
                    outputToSource=directed_bound(output[b], source[a], tolerance)) for b, a in mapping]
    return dict(passed=all(r['sourceToOutput']['passed'] and r['outputToSource']['passed'] for r in reports),
                loops=len(mapping), tolerance=tolerance, bounds=reports,
                method='Matched boundary cycles; adaptive whole-segment convex distance bounds in both directions.')
