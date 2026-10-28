"""Local separating planes for rejected candidate face contacts."""
import numpy as np
from rtree.index import Index,Property


def nearby_pairs(vertices,faces,margin=0.,active_faces=None):
    """Conservative AABB neighborhood for fitting; final checks stay separate."""
    p=np.asarray(vertices)[np.asarray(faces)];bounds=np.c_[p.min(1)-margin,p.max(1)+margin]
    tree=Index(((i,box,None) for i,box in enumerate(bounds)),properties=Property(dimension=3))
    active=range(len(faces)) if active_faces is None else active_faces
    pairs={tuple(sorted((int(a),int(b)))) for a in active for b in tree.intersection(bounds[a]) if a!=b}
    tree.close()
    return sorted(pairs)


def planes(vertices, faces, pairs):
    constraints = []
    for i, j in pairs:
        ia, ib = np.asarray(faces[i]), np.asarray(faces[j])
        common = np.intersect1d(ia, ib)
        ua, ub = np.setdiff1d(ia, common), np.setdiff1d(ib, common)
        if not len(ua) or not len(ub):
            continue
        a, b = vertices[ia], vertices[ib]
        ea, eb = np.roll(a, -1, 0)-a, np.roll(b, -1, 0)-b
        axes = np.concatenate([np.cross(ea, np.roll(ea, -1, 0)),
                               np.cross(eb, np.roll(eb, -1, 0)),
                               np.cross(ea[:, None], eb[None]).reshape(-1, 3),
                               (a.mean(0)-b.mean(0))[None]])
        if len(common) == 2:
            edge = vertices[common[1]]-vertices[common[0]]
            edge /= np.linalg.norm(edge)
            axes -= (axes @ edge)[:, None]*edge
        lengths = np.linalg.norm(axes, axis=1)
        axes = axes[lengths > 1e-12]/lengths[lengths > 1e-12, None]
        axes = np.r_[axes, -axes]
        lo = (vertices[ua] @ axes.T).min(0)
        hi = (vertices[ub] @ axes.T).max(0)
        if len(common):
            middle = vertices[common].mean(0) @ axes.T
            score = np.minimum(lo-middle, middle-hi)
        else:
            score = lo-hi
        axis = axes[score.argmax()]
        constraints.append((ua, ub, common, axis))
    return constraints
