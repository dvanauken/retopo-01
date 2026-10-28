from pathlib import Path
import sys, unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from boundary_geometry import loops, validate, correspondence, fit_ring, directed_bound, conform_ring, closest


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0]],float)
        self.f=np.array([[0,1,2],[0,2,3]])
    def test_triangle_to_quad_preserves_entire_boundary(self):
        report=validate(self.v,self.f,self.v,[[0,1,2,3]],1e-8)
        self.assertTrue(report['passed']); self.assertEqual(report['loops'],1)
    def test_interior_chord_deviation_cannot_hide_between_samples(self):
        # Endpoints of the replacement edge lie on a bent source boundary,
        # while the edge interior cuts across its re-entrant corner.
        v=np.array([[0,0,0],[.5,.5,0],[1,0,0],[1,1,0],[0,1,0]])
        r=validate(v,[[0,1,4],[1,3,4],[1,2,3]],self.v,[[0,1,2,3]],.05)
        self.assertFalse(r['passed'])
    def test_missing_hole_rejects(self):
        v=np.r_[self.v,self.v*.4+.3];f=[[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]
        self.assertEqual(len(loops(f)),2)
        self.assertFalse(validate(v,f,self.v,[[0,1,2,3]],.01)['passed'])
    def test_nonmanifold_and_branched_boundaries_reject(self):
        with self.assertRaises(ValueError):loops([[0,1,2],[1,0,3],[0,1,4]])
        with self.assertRaises(ValueError):loops([[0,1,2],[0,3,4]])
    def test_boundary_motion_rejects(self):
        shifted=self.v.copy();shifted[:,0]+=.2
        self.assertFalse(validate(self.v,self.f,shifted,[[0,1,2,3]],.05)['passed'])
    def test_corner_fit_preserves_cycle_without_cutting_corners_in_either_winding(self):
        cut=np.array([[.1,0,0],[.9,0,0],[1,.1,0],[1,.9,0],[.9,1,0],[.1,1,0],[0,.9,0],[0,.1,0]])
        for candidate in (cut,cut[::-1]):
            result=fit_ring(candidate,self.v)
            self.assertTrue(directed_bound(self.v,result,.001)['passed'])
            self.assertTrue(directed_bound(result,self.v,.001)['passed'])
            self.assertTrue(np.all(np.min(np.linalg.norm(self.v[:,None]-result[None],axis=2),axis=1)<1e-10))
            self.assertTrue(np.all(np.linalg.norm(result-np.roll(result,-1,axis=0),axis=1)>0))
    def test_conforming_puts_vertices_on_gentle_bends_without_reordering(self):
        # A 16-gon turns 22.5 degrees per vertex, below fit_ring's corner rule; 24 evenly
        # spaced output vertices offset by half a source edge cut every one of its bends.
        ring=np.array([[np.cos(a),np.sin(a),0] for a in np.linspace(0,2*np.pi,16,endpoint=False)])
        side=np.linalg.norm(ring[1]-ring[0]);total=16*side
        def at(s):
            s=s%total;k=int(s//side);return ring[k]+(s-k*side)/side*(ring[(k+1)%16]-ring[k])
        cut=np.array([at(side*.5+i*total/24) for i in range(24)]);tolerance=.01
        for candidate in (cut,cut[::-1]):
            self.assertFalse(directed_bound(ring,candidate,tolerance)['passed'])
            result=conform_ring(candidate,ring,tolerance)
            self.assertTrue(directed_bound(ring,result,tolerance)['passed']);self.assertTrue(directed_bound(result,ring,tolerance)['passed'])
            self.assertTrue(np.all(np.min(np.linalg.norm(ring[:,None]-result[None],axis=2),axis=1)<1e-9))
            order=closest(result,ring)[2];steps=(np.roll(order,-1)-order)%16
            self.assertTrue(np.all(steps<8) if candidate is cut else np.all((-steps)%16<8))
            # Vertices slide along the boundary by less than one output edge.
            self.assertLess(np.linalg.norm(result-candidate,axis=1).max(),total/24)
        exact=np.array([at(i*total/32) for i in range(32)])
        np.testing.assert_allclose(conform_ring(exact,ring,tolerance),exact,atol=1e-12)


if __name__=='__main__':unittest.main()
