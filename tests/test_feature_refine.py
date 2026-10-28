from pathlib import Path
import sys,unittest
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from feature_refine import refine,nearest_segments
from source_features import measure


class FeatureFitting(unittest.TestCase):
    def test_a_distinct_crease_cannot_capture_an_authored_guide_edge(self):
        points=np.array([[0.,0.,0.],[0.,0.,0.]])
        a=np.array([[-1.,0.,0.],[-1.,.1,0.]])
        b=np.array([[1.,0.,0.],[1.,.1,0.]])
        selected=nearest_segments(points,a,b,forbidden_edges=[True,False],separate_points=[True,False])
        np.testing.assert_array_equal(selected,[1,0])

    def test_local_fit_keeps_other_vertices_fixed_with_contact_constraints(self):
        v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],float)
        q=np.array([[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]])
        f=np.r_[q[:,[0,1,2]],q[:,[0,2,3]]];mesh=trimesh.Trimesh(v,f,process=False)
        p=v.copy();p[0]+=.05
        contacts=[(i,j) for i in range(6) for j in range(i+1,6)]
        fitted,_=refine(mesh,p,q,[],6,[],contacts=contacts,active_vertices=[0])
        np.testing.assert_array_equal(fitted[1:],v[1:])
        self.assertLess(np.linalg.norm(fitted[0]-v[0]),.01)
        compact,_=refine(mesh,p,q,[],6,[],contacts=contacts,active_vertices=[0],compact_active_terms=True)
        np.testing.assert_array_equal(compact[1:],v[1:])
        np.testing.assert_allclose(compact,fitted,atol=1e-6)

    def test_tangent_matching_avoids_an_edge_crossing_the_feature(self):
        points=np.array([[0.,0.,0.]])
        a=np.array([[-1.,.05,0.],[0.,-1.,0.]])
        b=np.array([[1.,.05,0.],[0.,1.,0.]])
        self.assertEqual(nearest_segments(points,a,b)[0],1)
        self.assertEqual(nearest_segments(points,a,b,np.array([[1.,0.,0.]]),1.)[0],0)

    def test_feature_fitting_restores_inset_cube_without_changing_connectivity(self):
        v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],float)
        q=np.array([[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]])
        f=np.r_[q[:,[0,1,2]],q[:,[0,2,3]]];mesh=trimesh.Trimesh(v,f,process=False)
        # Measure at 0.1-unit faces, where the 0.07 inset exceeds half a face.
        p=v*.9+.05;before=measure(v,f,p,q,600)
        fitted,detail=refine(mesh,p,q,[],6,[])
        after=measure(v,f,fitted,q,600)
        self.assertFalse(before['passed']);self.assertTrue(after['passed'],after)
        self.assertLess(after['values']['edgeMax'],before['values']['edgeMax']*.1)


if __name__=='__main__':unittest.main()
