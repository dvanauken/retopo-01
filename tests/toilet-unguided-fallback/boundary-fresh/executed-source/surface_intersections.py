"""Screen polygon contacts, allowing only their shared topological boundary.

By default quads use the renderer's fan. The optional all-diagonals mode checks
every triangle pairing from either diagonal of each quad, including mixed choices
on neighboring faces. Coordinates are normalized
source coordinates; double-precision predicates use a 1e-9 length tolerance.
Degeneracy, winding and vertex links are checked separately by the quality gates.
"""
import numpy as np
from rtree.index import Index, Property


def triangle_contacts(a, b, eps=1e-9):
    """Vertices of the convex triangle intersection, including touching contacts."""
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = np.cross(a[1] - a[0], a[2] - a[0]), np.cross(b[1] - b[0], b[2] - b[0])
    la, lb = np.linalg.norm(na), np.linalg.norm(nb)
    if min(la, lb) < eps * eps:
        return []  # Degeneracy is checked separately by the quality gate.
    na /= la; nb /= lb
    da, db = (a - b[0]) @ nb, (b - a[0]) @ na
    if any(np.all(d > eps) or np.all(d < -eps) for d in (da, db)):
        return []

    def inside(p, t, normal):
        return all(np.dot(np.cross(t[(i + 1) % 3] - t[i], p - t[i]), normal)
                   >= -eps * np.linalg.norm(t[(i + 1) % 3] - t[i]) for i in range(3))

    if np.max(np.abs(da)) <= eps and np.max(np.abs(db)) <= eps:
        # Clip the first triangle to the second in their common plane. Unlike
        # a boolean overlap test, the resulting polygon distinguishes shared
        # edges from folded faces occupying area on the same side of that edge.
        polygon = list(a)
        for i in range(3):
            origin, edge = b[i], b[(i + 1) % 3] - b[i]
            inward = np.cross(nb, edge); inward /= np.linalg.norm(inward)
            clipped = []
            for j, point in enumerate(polygon):
                previous = polygon[j - 1]
                dp, dc = np.dot(previous - origin, inward), np.dot(point - origin, inward)
                if (dp >= -eps) != (dc >= -eps):
                    # The clipping line itself is at zero. Clamp for points
                    # admitted by the tolerance immediately outside that line.
                    t = np.clip(dp / (dp - dc), 0., 1.)
                    clipped.append(previous + t * (point - previous))
                if dc >= -eps:
                    clipped.append(point)
            polygon = clipped
            if not polygon:
                break
        return polygon

    contacts = []
    for first, other, normal in ((a, b, nb), (b, a, na)):
        for i in range(3):
            p, q = first[i], first[(i + 1) % 3]
            start, change = np.dot(p - other[0], normal), np.dot(q - p, normal)
            if abs(start) <= eps and inside(p, other, normal):
                contacts.append(p)
            if abs(change) > eps:
                t = -start / change
                margin = eps / max(eps, np.linalg.norm(q - p))
                contact = p + np.clip(t, 0., 1.) * (q - p)
                if -margin <= t <= 1 + margin and inside(contact, other, normal):
                    contacts.append(contact)
    return contacts


def triangle_intersects(a, b, eps=1e-9):
    return bool(triangle_contacts(a, b, eps))


def _on_boundary(point, vertices, shared_vertices, shared_edges, eps):
    if any(np.linalg.norm(point - vertices[i]) <= eps for i in shared_vertices):
        return True
    for a, b in shared_edges:
        start, delta = vertices[a], vertices[b] - vertices[a]
        denominator = np.dot(delta, delta)
        if denominator > eps * eps:
            t = np.clip(np.dot(point - start, delta) / denominator, 0., 1.)
            if np.linalg.norm(point - start - t * delta) <= eps:
                return True
    return False


def _possible_contacts(v, triangles, face_edges, face_pairs, eps):
    """Batch exact separating-plane exclusions; retain ambiguous contacts.

    Triangles sharing an edge in different planes can meet only along that
    edge. For a shared vertex, a strict half-space test can likewise establish
    that this vertex is their only contact. These are geometric exclusions,
    not blanket exclusions of adjacent polygons.
    """
    rows = [(a, b, x, y) for a, b in face_pairs for x in triangles[a] for y in triangles[b]]
    if not rows:
        return []
    ia, ib = np.asarray([r[2] for r in rows]), np.asarray([r[3] for r in rows])
    a, b = v[ia], v[ib]
    na, nb = np.cross(a[:,1]-a[:,0], a[:,2]-a[:,0]), np.cross(b[:,1]-b[:,0], b[:,2]-b[:,0])
    la, lb = np.linalg.norm(na, axis=1), np.linalg.norm(nb, axis=1)
    na /= np.maximum(la[:,None], eps*eps); nb /= np.maximum(lb[:,None], eps*eps)
    da = np.einsum('ijk,ik->ij', a-b[:,0,None,:], nb)
    db = np.einsum('ijk,ik->ij', b-a[:,0,None,:], na)
    active = (la > eps*eps) & (lb > eps*eps)
    for d in (da, db):
        active &= ~(np.all(d > eps, axis=1) | np.all(d < -eps, axis=1))
    common = [set(x).intersection(y) for x,y in zip(ia,ib)]
    shared = np.array([len(ids) for ids in common])
    common_boundary = np.array([len(ids)==2 and tuple(sorted(ids)) in face_edges[r[0]].intersection(face_edges[r[1]]) for ids,r in zip(common,rows)])
    coplanar = (np.max(np.abs(da),axis=1) <= eps) & (np.max(np.abs(db),axis=1) <= eps)
    active &= ~(common_boundary & ~coplanar)
    for d in (da, db):
        only_vertex = (np.sum(np.abs(d) <= eps, axis=1) == 1) & (np.all(d >= -eps, axis=1) | np.all(d <= eps, axis=1))
        active &= ~((shared == 1) & only_vertex)
    return [rows[i] for i in np.flatnonzero(active)]


def measure(vertices, faces, *, both_quad_diagonals=False):
    eps = 1e-9
    v = np.asarray(vertices, dtype=float)
    polygons = [v[f] for f in faces]
    bounds = [np.r_[p.min(axis=0) - eps, p.max(axis=0) + eps] for p in polygons]
    tree = Index(((i, b, None) for i, b in enumerate(bounds)), properties=Property(dimension=3))
    ownership = [set(f) for f in faces]
    edges = [{tuple(sorted((f[i], f[(i + 1) % len(f)]))) for i in range(len(f))} for f in faces]
    triangles = [[[f[0], f[i], f[i+1]] for i in range(1,len(f)-1)] for f in faces]
    if both_quad_diagonals:
        for face, parts in zip(faces, triangles):
            if len(face)==4:
                parts.extend([[face[1],face[2],face[3]],[face[1],face[3],face[0]]])
    face_pairs = [(a,b) for a,bound in enumerate(bounds) for b in tree.intersection(bound) if b > a]
    tree.close()
    pairs, adjacent = [], []
    rejected = set()
    for a, b, x, y in _possible_contacts(v, triangles, edges, face_pairs, eps):
        if (a,b) in rejected:
            continue
        shared = ownership[a].intersection(ownership[b])
        common_edges = edges[a].intersection(edges[b])
        contacts = triangle_contacts(v[x], v[y], eps)
        if not contacts:
            continue
        # Interior and segment midpoints also reject a contact spanning
        # separate shared vertices without a shared topological edge.
        points = np.asarray(contacts)
        probes = np.r_[points, points.mean(axis=0, keepdims=True), (points + np.roll(points, 1, axis=0)) * .5]
        if not shared or any(not _on_boundary(p, v, shared, common_edges, eps * 4) for p in probes):
            rejected.add((a,b))
            (adjacent if shared else pairs).append([a,b])
    return dict(passed=not pairs and not adjacent, nonAdjacentIntersectingFacePairs=sorted(pairs),
                adjacentIntersectingFacePairs=sorted(adjacent),
                quadDiagonalPolicy='all_pairings' if both_quad_diagonals else 'renderer_fan',
                scope='Indexed polygon bounds and triangle contact vertices, '+('both quad diagonals with every mixed triangle pairing' if both_quad_diagonals else 'fan triangulation')+', 1e-9 length tolerance. Contacts are allowed only on common topological vertices/edges (4e-9 boundary tolerance). Floating-point screen; degeneracy and manifold checks are separate.')
