"""Geometric invariants for the added quad warpage residual."""
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from curved_quad import _warpage


class Warpage(unittest.TestCase):
    def test_planar_and_warped_quad(self):
        p=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]],dtype=float); f=np.array([[0,1,2,3]])
        self.assertEqual(_warpage(p,f)[0],0)
        p[3,2]=.2
        self.assertGreater(abs(_warpage(p,f)[0]),.09)

    def test_vertex_origin_and_winding_do_not_change_magnitude(self):
        p=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,.2]],dtype=float)
        value=abs(_warpage(p,np.array([[0,1,2,3]]))[0])
        for offset in range(4):
            f=np.roll(np.array([[0,1,2,3]]),offset,axis=1)
            self.assertAlmostEqual(abs(_warpage(p,f)[0]),value)
            self.assertAlmostEqual(abs(_warpage(p,f[:,::-1])[0]),value)

    def test_rigid_transform_and_uniform_scale(self):
        p=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,.2]],dtype=float); f=np.array([[0,1,2,3]])
        value=abs(_warpage(p,f)[0]); rng=np.random.default_rng(671)
        for scale in (.001,1,1000):
            rotation,_=np.linalg.qr(rng.normal(size=(3,3)))
            changed=p@rotation*scale+[.4,-.8,1.2]
            self.assertAlmostEqual(abs(_warpage(changed,f)[0])/scale,value,places=10)


if __name__=='__main__': unittest.main()
