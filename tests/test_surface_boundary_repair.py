"""Topological invariants and rejection cases for bounded bridge proposals."""
from collections import defaultdict
import json
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from surface_boundary_repair import bridge_candidates
from measure_geometry import topology


def strip(n,levels=3):
    return np.asarray([[j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i] for j in range(levels-1) for i in range(n)])


class BridgeTests(unittest.TestCase):
    def test_simple_strips_close_with_opposite_edge_directions_and_same_euler(self):
        for n in range(3,9):
            original=strip(n);before=original.copy();candidates=bridge_candidates(original)
            self.assertEqual(len(candidates),n)
            np.testing.assert_array_equal(original,before)
            for candidate in candidates:
                faces=candidate['faces'];incidence=defaultdict(list)
                for face in faces:
                    self.assertEqual(len(set(face)),4)
                    for a,b in zip(face,np.roll(face,-1)):
                        incidence[tuple(sorted((int(a),int(b))))].append((int(a),int(b)))
                self.assertTrue(all(len(items)==2 and items[0]==items[1][::-1] for items in incidence.values()))
                self.assertEqual(len(np.unique(faces))-len(incidence)+len(faces),0)
                np.testing.assert_array_equal(faces[:len(original)],original)

    def test_rejects_unbounded_and_unequal_or_single_loops(self):
        self.assertEqual(bridge_candidates(strip(9)),[])
        self.assertEqual(bridge_candidates([[0,1,2,3]]),[])
        self.assertEqual(bridge_candidates([[0,1,2,3],[2,1,4,5]]),[])

    def test_rejects_nonmanifold_and_inconsistent_winding(self):
        f=strip(4)
        self.assertEqual(bridge_candidates(np.r_[f,f[:1]]),[])
        f[0]=f[0][::-1]
        self.assertEqual(bridge_candidates(f),[])

    def test_short_tube_bridges_do_not_reuse_existing_interior_edges(self):
        f=strip(4,levels=2)
        candidates=bridge_candidates(f)
        self.assertLess(len(candidates),4)
        for candidate in candidates:
            incidence=defaultdict(int)
            for face in candidate['faces']:
                for a,b in zip(face,np.roll(face,-1)):incidence[tuple(sorted((int(a),int(b))))]+=1
            self.assertTrue(all(count==2 for count in incidence.values()))

    def test_rejects_repeated_vertices_and_closed_mesh(self):
        self.assertEqual(bridge_candidates([[0,1,2,0]]),[])
        self.assertEqual(bridge_candidates([[0,1,2,3],[3,2,1,0]]),[])

    def test_real_toilet_layout_preserves_euler_zero_and_matches_qualified_candidate(self):
        path=ROOT/'tests/toilet-layout-inventory/alternative-seeds-345/target-150-seed-4.json'
        raw=json.loads(path.read_text());candidates=bridge_candidates(raw['faces'])
        self.assertEqual(len(candidates),3)
        expected=json.loads((ROOT/'tests/toilet-boundary-bridge/coarse150-seed4/bridge-0/input.json').read_text())
        self.assertEqual(candidates[0]['faces'].tolist(),expected['faces'])
        for candidate in candidates:
            stats,_,_=topology(np.asarray(raw['vertices']),candidate['faces'].tolist())
            self.assertEqual(stats['eulerCharacteristic'],0)
            self.assertEqual(stats['boundaryEdges'],0)
            self.assertEqual(stats['nonmanifoldEdges'],0)
            self.assertEqual(stats['faceConnectedComponents'],1)
            self.assertEqual(stats['faces'],152)


if __name__=='__main__':unittest.main()
