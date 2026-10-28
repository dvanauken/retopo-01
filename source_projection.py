"""Normal-aware, bounded surface correspondence for fitting thin sheets.

This chooses fitting constraints, not certified distances. Final geometric
validation must still search the entire source independently.
"""
import numpy as np
import trimesh
from scipy.spatial import cKDTree


class OrientedSurface:
    def __init__(self, mesh):
        self.mesh = mesh
        self.centers = cKDTree(mesh.triangles_center)
        self.vertices = cKDTree(mesh.vertices)

    def closest(self, points, normals, minimum_dot=.1):
        points, normals = np.asarray(points), np.asarray(normals)
        locations, distances, owners = [], [], []
        for start in range(0, len(points), 256):
            p, n = points[start:start+256], normals[start:start+256]
            _, centers = self.centers.query(p, k=min(48, len(self.mesh.faces)))
            _, vertices = self.vertices.query(p, k=min(4, len(self.mesh.vertices)))
            centers = np.asarray(centers).reshape(len(p), -1)
            vertices = np.asarray(vertices).reshape(len(p), -1)
            incident = self.mesh.vertex_faces[vertices].reshape(len(p), -1)
            candidates = np.concatenate([centers, incident], axis=1)
            valid = candidates >= 0
            candidates = np.maximum(candidates, 0)
            tri = self.mesh.triangles[candidates]
            near = trimesh.triangles.closest_point(tri.reshape(-1, 3, 3),
                    np.broadcast_to(p[:, None], tri.shape[:2]+(3,)).reshape(-1, 3)).reshape(len(p), -1, 3)
            squared = ((near-p[:, None])**2).sum(axis=2)
            aligned = (self.mesh.face_normals[candidates]*n[:, None]).sum(axis=2) >= minimum_dot
            eligible = valid & aligned
            # A poor initial normal is recorded by ordinary distance/shape
            # gates; it cannot manufacture a nonfinite fitting constraint.
            eligible[~eligible.any(axis=1)] = valid[~eligible.any(axis=1)]
            selected = np.where(eligible, squared, np.inf).argmin(axis=1)
            rows = np.arange(len(p))
            locations.extend(near[rows, selected]); distances.extend(np.sqrt(squared[rows, selected])); owners.extend(candidates[rows, selected])
        return np.asarray(locations).reshape(-1, 3), np.asarray(distances), np.asarray(owners, dtype=int)
