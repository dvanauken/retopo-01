from pathlib import Path
import sys,unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from surface_intersections import measure_reference as reference
from surface_contacts_fast import measure as compiled


class ContactParity(unittest.TestCase):
    def compare(self,v,q):
        for both in (False,True):
            expected=reference(v,q,both_quad_diagonals=both);actual=compiled(v,q,both_quad_diagonals=both)
            for key in ('passed','nonAdjacentIntersectingFacePairs','adjacentIntersectingFacePairs','quadDiagonalPolicy'):
                self.assertEqual(actual[key],expected[key],(key,v,q))

    def test_random_warped_overlapping_and_adjacent_quads(self):
        random=np.random.default_rng(742)
        for _ in range(60):
            v=random.normal(size=(7,3));self.compare(v,[[0,1,2,3],[0,4,5,6],[3,2,5,4]])

    def test_coplanar_boundaries_overlap_and_tolerance(self):
        for offset in (0,1e-10,1e-8,.25,1.,1.00000001):
            v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[offset,0,0],[offset+1,0,0],[offset+1,1,0],[offset,1,0]])
            self.compare(v,[[0,1,2,3],[4,5,6,7]])
        self.compare(np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[2,0,0],[2,1,0]]),[[0,1,2,3],[1,4,5,2]])


if __name__=='__main__':unittest.main()
