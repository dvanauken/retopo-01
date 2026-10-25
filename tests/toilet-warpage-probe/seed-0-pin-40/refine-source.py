def warpage(positions,faces):
    p=positions[faces]
    cross=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0])
    area=cross+np.cross(p[:,2]-p[:,0],p[:,3]-p[:,0])
    return np.einsum('ij,ij->i',cross,p[:,3]-p[:,0])/np.maximum(1e-15,np.linalg.norm(area,axis=1))

def _refine(source_mesh, positions, faces, edges, pins, targets, target):
    spacing = np.sqrt(source_mesh.area / target)
    jacobian, cosine = _corners(positions, faces)
    bad = (jacobian.min(axis=1) < .7) | (np.abs(cosine).max(axis=1) > .75)
    bad |= np.abs(warpage(positions, faces)) > spacing * .05
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
                     np.maximum(ratio - 3.5, 0) * 10, warpage(q, local_faces) / spacing * 8, np.maximum(.4 - length / spacing, 0) * 5,
                     np.maximum(length / spacing - 1.7, 0), (delta * normal).sum(axis=1) / spacing * 6,
                     delta.ravel() / spacing * 2, (q[pins] - targets).ravel() / spacing * 40.0,
                     surface_delta.ravel() / spacing * 4,
                     np.maximum(np.linalg.norm(delta, axis=1) / spacing - .35, 0) * 40,
                     np.maximum(np.linalg.norm(surface_delta, axis=1) / spacing - .35, 0) * 40]
    result = least_squares(residual, positions[ids].ravel(), jac_sparsity=sparsity.tocsr(), max_nfev=150, ftol=1e-6, xtol=1e-5)
    output = positions.copy(); output[ids] = result.x.reshape(-1, 3)
    return output, {'vertices': len(ids), 'evaluations': result.nfev, 'sourceSupportPoints': len(support)}
