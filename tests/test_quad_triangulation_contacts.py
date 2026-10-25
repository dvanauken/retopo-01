"""OBJ quad contacts must be safe under either or mixed diagonal choices."""
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from surface_intersections import measure


class QuadTriangulations(unittest.TestCase):
    def test_mixed_choices_can_cross_when_both_uniform_choices_are_clear(self):
        # Two vertically separated saddle quads. Both uniform triangulations
        # are disjoint, but upper A(1--3) meets lower B(0--2) in their interiors.
        v=np.array([[-1,-1,0],[1,-1,1],[1,1,0],[-1,1,1],
                    [-.5,-.5,.6],[.5,-.5,1.6],[.5,.5,.6],[-.5,.5,1.6]])
        f=np.array([[0,1,2,3],[4,5,6,7]])
        point=np.array([0,4/15,13/15])
        for tri in (v[[1,2,3]],v[[4,6,7]]):
            weights=np.linalg.lstsq(np.r_[tri.T,np.ones((1,3))],np.r_[point,1.],rcond=None)[0]
            self.assertTrue(np.all(weights>0)); np.testing.assert_allclose(weights@tri,point,atol=1e-14)
        self.assertTrue(measure(v,f)['passed'])
        self.assertTrue(measure(v,np.roll(f,-1,axis=1))['passed'])
        mixed=f.copy(); mixed[0]=np.roll(mixed[0],-1)
        self.assertFalse(measure(v,mixed)['passed'])
        result=measure(v,f,both_quad_diagonals=True)
        self.assertFalse(result['passed']); self.assertEqual(result['nonAdjacentIntersectingFacePairs'],[[0,1]])

    def toilet_patch(self):
        # Four faces of actual perturbed Circle export ff12115c...; independently
        # confirmed LP witnesses are retained in toilet-diagonal-contacts/variants.
        v=np.array([[-.32911317526159717,.517874167429549,.05428906222545778],
                    [-.38007545974780854,.48022720498589383,.014783486810335431],
                    [-.3999257700719784,.4393174208455928,.08608485150512189],
                    [-.39544477199413935,.4476927356321369,.02290974148723504],
                    [-.37679081760763883,.41280062904556863,.06008701233281634],
                    [-.3120593000793651,.3413249082483708,.058956904147590035],
                    [-.2679938353374492,.38349093002252627,.059800001719899236],
                    [-.3339052515120706,.3250922260847668,.09086150187883299],
                    [-.339164801069971,.3693954317579691,.021255062865461753]])
        return v,np.array([[4,3,1,0],[3,4,5,8],[7,2,3,8],[6,5,4,0]])

    def test_actual_toilet_patch_exposes_contacts_hidden_by_renderer_fan(self):
        v,f=self.toilet_patch()
        self.assertTrue(measure(v,f)['passed'])
        result=measure(v,f,both_quad_diagonals=True)
        self.assertFalse(result['passed'])
        self.assertIn([0,2],result['adjacentIntersectingFacePairs'])
        self.assertIn([1,2],result['adjacentIntersectingFacePairs'])

    def test_cyclic_origin_and_winding_cannot_hide_the_actual_contacts(self):
        v,f=self.toilet_patch(); expected=measure(v,f,both_quad_diagonals=True)
        for offsets in ((0,0,0,0),(1,1,1,1),(0,1,0,1),(3,0,2,1)):
            shifted=np.array([np.roll(face,offset) for face,offset in zip(f,offsets)])
            for faces in (shifted,shifted[:,::-1]):
                actual=measure(v,faces,both_quad_diagonals=True)
                for key in ('passed','adjacentIntersectingFacePairs','nonAdjacentIntersectingFacePairs'):
                    self.assertEqual(actual[key],expected[key])

    def test_legal_hinged_and_coplanar_shared_boundaries_still_pass(self):
        for far in ([[1,0,1],[1,1,1]],[[2,0,0],[2,1,0]]):
            v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]]+far,dtype=float)
            self.assertTrue(measure(v,[[0,1,2,3],[1,4,5,2]],both_quad_diagonals=True)['passed'])


if __name__=='__main__': unittest.main()
