from pathlib import Path
import sys,unittest
from unittest.mock import patch
import trimesh
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from guide_embedding import embed
from guide_embedding_check import verify


class ExactFeatureEmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]],float)
        self.f=np.array([[0,1,2],[0,2,3]])

    def test_existing_edge_identity_survives_crossing_user_curve(self):
        curve=np.array([[0,.5,0],[1,.5,0]])
        p,f,meta=embed(self.v,self.f,[curve],source_paths=[[0,2]])
        checked=verify(self.v,self.f,p,f,meta,[curve,self.v[[0,2]]])
        self.assertTrue(checked['passed'],checked)
        edges=np.asarray(meta['guideEdges']['1'])
        self.assertEqual(len(edges),2)
        crossing=set(edges[0])&set(edges[1])
        self.assertEqual(len(crossing),1)
        np.testing.assert_allclose(p[next(iter(crossing))],[.5,.5,0])
        self.assertTrue(set(edges.ravel()) >= {0,2})
        np.testing.assert_array_equal(p[:len(self.v)],self.v)

    def test_fold_crease_uses_exact_edge_on_both_sheets(self):
        v=self.v.copy();v[3]=[.5,.5,.2]
        p,f,meta=embed(v,self.f,[],source_paths=[[0,2]])
        self.assertEqual(meta['guideEdges']['0'],[(0,2)])
        self.assertTrue(verify(v,self.f,p,f,meta,[v[[0,2]]])['passed'])
        self.assertEqual(len(f),2)

    def test_nonedge_feature_rejected(self):
        with self.assertRaisesRegex(ValueError,'not a source mesh edge'):
            embed(self.v,self.f,[],source_paths=[[1,3]])


class MarkedRelaxationTests(unittest.TestCase):
    def test_two_numpy_boolean_marks_allow_regular_star_sliding(self):
        import open_surface
        v=np.array([[x,y,0] for y in range(3) for x in range(3)],float)
        q=np.array([[0,1,4,3],[1,2,5,4],[3,4,7,6],[4,5,8,7]])
        mesh=trimesh.Trimesh(v,np.r_[q[:,[0,1,2]],q[:,[0,2,3]]],process=False)
        p=v.copy();p[4,0]=1.3;fixed=np.ones(len(p),bool);fixed[4]=False
        segments=(np.array([[0,1,0.]]),np.array([[2,1,0.]]))
        with patch.object(open_surface,'FREEZE_NEAR_MARKS',False):
            result=open_surface.relax(mesh,p,q,fixed,rounds=1,segments=segments,spacing=1.)
        self.assertLess(result[4,0],p[4,0])
        np.testing.assert_array_equal(result[fixed],p[fixed])
        np.testing.assert_allclose(result[4,1:],[1.,0.])


if __name__=='__main__':unittest.main()
