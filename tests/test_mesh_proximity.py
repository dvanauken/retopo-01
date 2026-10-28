from pathlib import Path
import sys,unittest
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mesh_proximity import TriangleProximity


class ExactProximity(unittest.TestCase):
    def test_random_mesh_queries_match_reference_distances(self):
        rng=np.random.default_rng(71);v=rng.normal(size=(600,3));f=np.arange(600).reshape(-1,3)
        mesh=trimesh.Trimesh(v,f,process=False);points=np.r_[rng.normal(size=(2000,3))*2,v,v[f].mean(1)]
        distances,owners=TriangleProximity(v,f).query(points)
        reference=trimesh.proximity.closest_point(mesh,points)[1]
        np.testing.assert_allclose(distances,reference,atol=2e-12,rtol=2e-12)
        # Each returned triangle must itself realize the reported distance.
        closest=trimesh.triangles.closest_point(v[f[owners]],points)
        np.testing.assert_allclose(np.linalg.norm(closest-points,axis=1),distances,atol=2e-12,rtol=2e-12)

    def test_collinear_and_collapsed_triangles_have_segment_and_point_distances(self):
        v=np.array([[0,0,0],[1,0,0],[2,0,0],[5,0,0]],float);f=np.array([[0,1,2],[3,3,3]])
        distance,owner=TriangleProximity(v,f).query([[1,.5,0],[6,0,0],[2,0,0]])
        np.testing.assert_allclose(distance,[.5,1,0]);np.testing.assert_array_equal(owner,[0,1,0])

    def test_long_thin_triangle_and_far_queries_are_not_lost_by_tree_pruning(self):
        v=np.array([[0,0,0],[10000,0,0],[0,1e-8,0],[0,0,1],[1,0,1],[0,1,1]],float);f=np.array([[0,1,2],[3,4,5]])
        distance,owner=TriangleProximity(v,f).query([[5000,1e-9,1e-4],[20000,0,0],[0,0,.5]])
        np.testing.assert_allclose(distance,[1e-4,10000,.5],atol=1e-12);self.assertEqual(owner[0],0)


if __name__=='__main__':unittest.main()
