"""Corner zones: how far the source lies from the output where crease branches meet.

The whole-surface check takes its 95th percentile over the whole part, and the
crease check measures creases to edges. A small corner where several creases
meet (island 6's feet under the back of the lip) is a few percent of either, so
a few large folded faces there passed both. This module measures the source
against the output inside such corners alone and reports it in requested
faces, so a chunky corner is named with its numbers.

Evidence level. Native ZRemesher applies no acceptance test, so nothing here
is a native rule. The measure is the one used to compare this application with
ZBrush on island 6 (2026-11-10): the distance from every source vertex of the
zone to the output surface. The zones and the limits are engineering choices,
labelled where they are defined; the limits reuse numbers the application
already applies with the same meaning.
"""
import numpy as np
import trimesh
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

POLICY = 'corner-zones-v1'
# Engineering choices. A corner is a cluster of crease junctions (three or more admitted crease
# branches meeting at one source vertex). Its zone is every source vertex within one requested
# face of one of those junctions; junctions whose zones would overlap (closer than two faces)
# form one corner. A zone needs enough source vertices for a 95th percentile to mean something.
ZONE_REACH_FACES = 1.
ZONE_LINK_FACES = 2.
ZONE_MIN_VERTICES = 20
# Limits, in requested faces, reusing the crease check's numbers with their meaning: 95% of the
# zone within a quarter face of the output, and no point of it farther than half a face.
ZONE_P95_FACES = .25
ZONE_MAX_FACES = .5


def fan(faces):
    """Triangles of polygon faces, fanned from each face's first corner (a quad is cut along corners 0-2)."""
    triangles = []
    for face in faces:
        face = [int(v) for v in face]
        triangles.extend([face[0], face[k], face[k + 1]] for k in range(1, len(face) - 1))
    return np.asarray(triangles, int).reshape(-1, 3)


def distances(points, vertices, faces):
    """Distance from each point to the output surface (faces fanned from their first corner)."""
    points = np.asarray(points, float)
    if not len(points):
        return np.zeros(0)
    surface = trimesh.Trimesh(np.asarray(vertices, float), fan(faces), process=False)
    return np.asarray(trimesh.proximity.closest_point(surface, points)[1], float)


def measure_zone(source, vertices, faces, spacing, mask):
    """Source-to-output distance over the source vertices in `mask`, in requested faces."""
    source = np.asarray(source, float)
    ids = np.flatnonzero(np.asarray(mask, bool))
    if not len(ids):
        return dict(sourceVertices=0, p95InFaces=0., maxInFaces=0., worstSourceVertex=None)
    distance = distances(source[ids], vertices, faces) / spacing
    return dict(sourceVertices=int(len(ids)), p95InFaces=float(np.percentile(distance, 95)), maxInFaces=float(distance.max()),
                worstSourceVertex=int(ids[int(distance.argmax())]))


def zones(source, edges, spacing):
    """Corner zones of a source: list of dict(junctions, vertices), largest first.

    `edges` are the admitted crease edges (source_features.detect). See the
    constants above for what a corner and its zone are.
    """
    source = np.asarray(source, float)
    edges = np.asarray(edges, int).reshape(-1, 2)
    if not len(edges):
        return []
    junctions = np.flatnonzero(np.bincount(edges.ravel(), minlength=len(source)) >= 3)
    if not len(junctions):
        return []
    pairs = cKDTree(source[junctions]).query_pairs(ZONE_LINK_FACES * spacing, output_type='ndarray').reshape(-1, 2)
    graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(junctions), len(junctions)))
    count, label = connected_components(graph, directed=False)
    tree = cKDTree(source)
    result = []
    for group in range(count):
        members = junctions[label == group]
        near = tree.query_ball_point(source[members], ZONE_REACH_FACES * spacing)
        vertices = np.unique(np.concatenate([np.asarray(ids, int) for ids in near]))
        if len(vertices) >= ZONE_MIN_VERTICES:
            result.append(dict(junctions=[int(v) for v in members], vertices=vertices))
    result.sort(key=lambda zone: (-len(zone['vertices']), zone['junctions'][0]))
    return result


def measure(source, triangles, edges, vertices, faces, spacing):
    """Corner report: every corner zone's source vertices against the output surface.

    `passed` is whether every zone meets the limits. Whether a failure rejects
    a mesh is the caller's policy (open_surface: it does when the user allows
    extra faces, and is reported otherwise).
    """
    source = np.asarray(source, float)
    limits = dict(p95InFaces=ZONE_P95_FACES, maxInFaces=ZONE_MAX_FACES)
    report = dict(policy=POLICY, limits=limits, zones=[], passed=True, failures=[],
                  scope='Corner zones: source vertices within one requested face of a cluster of crease junctions (three or more admitted crease '
                        'branches at one vertex; junctions closer than two faces form one corner; zones of fewer than '
                        f'{ZONE_MIN_VERTICES} source vertices are left to the whole-surface check). Each zone vertex is measured to the output '
                        'surface, quads cut along corners 0-2, in requested faces. Source vertices only: the measure follows the source tessellation.')
    for index, zone in enumerate(zones(source, edges, spacing)):
        mask = np.zeros(len(source), bool)
        mask[zone['vertices']] = True
        item = measure_zone(source, vertices, faces, spacing, mask)
        centre = source[zone['junctions']].mean(0)
        failures = [key for key in limits if item[key] > limits[key]]
        item.update(zone=index, junctions=len(zone['junctions']), centre=[float(x) for x in centre], passed=not failures, failures=failures)
        report['zones'].append(item)
    report['failures'] = [f"zone {item['zone'] + 1}: {key}" for item in report['zones'] for key in item['failures']]
    report['passed'] = not report['failures']
    report['worstP95InFaces'] = max((item['p95InFaces'] for item in report['zones']), default=0.)
    report['worstMaxInFaces'] = max((item['maxInFaces'] for item in report['zones']), default=0.)
    return report
