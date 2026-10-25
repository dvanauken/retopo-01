"""Geometric controls for triangle contacts and legitimate mesh adjacency."""
import sys
import unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from surface_intersections import measure, triangle_intersects


class Crossings(unittest.TestCase):
    def setUp(self):
        self.a = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=float)

    def test_crossing(self):
        b = np.array([[.2, .2, -1], [.2, .2, 1], [.6, .2, 0]])
        self.assertTrue(triangle_intersects(self.a, b))
        self.assertTrue(triangle_intersects(b, self.a))

    def test_overlapping_boxes_without_intersection(self):
        b = np.array([[.8, .8, -1], [.8, .8, 1], [1.5, 1.5, 0]])
        self.assertFalse(triangle_intersects(self.a, b))

    def test_parallel_disjoint_planes(self):
        self.assertFalse(triangle_intersects(self.a, self.a + [0, 0, .01]))

    def test_coplanar_containment(self):
        self.assertTrue(triangle_intersects(self.a, self.a * .2 + [.1, .1, 0]))

    def test_coplanar_crossing_without_containment(self):
        b = np.array([[-.1, .4, 0], [.8, .4, 0], [.8, .5, 0]])
        self.assertTrue(triangle_intersects(self.a, b))

    def test_coplanar_disjoint(self):
        self.assertFalse(triangle_intersects(self.a, self.a + [2, 0, 0]))

    def test_index_reports_nonadjacent_crossing(self):
        v = np.r_[self.a, [[.2, .2, -1], [.2, .2, 1], [.6, .2, 0]]]
        self.assertEqual(measure(v, [[0, 1, 2], [3, 4, 5]])['nonAdjacentIntersectingFacePairs'], [[0, 1]])

    def test_legitimate_coplanar_shared_edge(self):
        self.assertTrue(measure([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], [[0, 1, 2], [0, 2, 3]])['passed'])

    def test_folded_shared_edge_is_rejected(self):
        v = np.r_[self.a, [[.2, .3, 0]]]
        result = measure(v, [[0, 1, 2], [1, 0, 3]])
        self.assertEqual(result['adjacentIntersectingFacePairs'], [[0, 1]])
        self.assertFalse(result['passed'])

    def test_hinged_shared_edge_is_allowed(self):
        self.assertTrue(measure(np.r_[self.a, [[.2, .3, .2]]], [[0, 1, 2], [1, 0, 3]])['passed'])

    def test_shared_vertex_does_not_hide_crossing(self):
        v = np.r_[self.a, [[.5, .2, -.5], [.5, .2, .5]]]
        self.assertEqual(measure(v, [[0, 1, 2], [0, 3, 4]])['adjacentIntersectingFacePairs'], [[0, 1]])

    def test_shared_vertex_touch_is_allowed(self):
        v = np.r_[self.a, [[-1, 0, .5], [0, -1, .5]]]
        self.assertTrue(measure(v, [[0, 1, 2], [0, 3, 4]])['passed'])

    def test_separate_vertex_ids_touch_is_rejected(self):
        v = np.r_[self.a, [[0, 0, 0], [-1, 0, .5], [0, -1, .5]]]
        self.assertFalse(measure(v, [[0, 1, 2], [3, 4, 5]])['passed'])

    def test_shared_edge_quads_overlap_away_from_edge(self):
        # The neighboring quads share a legitimate edge but fold over each
        # other further away. Skipping their pair would miss this defect.
        v = [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [.8, .7, .1], [.2, .7, -.1]]
        self.assertFalse(measure(v, [[0, 1, 2, 3], [1, 0, 5, 4]])['passed'])

    def test_shared_diagonal_is_not_a_topological_boundary(self):
        v = [[0,0,0], [1,0,0], [1,1,0], [0,1,0], [.5,.5,1], [.5,.5,-1]]
        self.assertFalse(measure(v, [[0,1,2,3], [0,4,2,5]])['passed'])

    def test_contact_classification_is_rotation_and_winding_independent(self):
        rng = np.random.default_rng(381)
        for _ in range(15):
            rotation, _ = np.linalg.qr(rng.normal(size=(3, 3)))
            shift = rng.uniform(-2, 2, 3)
            for third, expected in (([.2, .3, 0], False), ([.2, -.3, 0], True), ([.2, .3, .2], True)):
                v = np.r_[self.a, [third]] @ rotation + shift
                for f in ([[0, 1, 2], [1, 0, 3]], [[2, 1, 0], [3, 0, 1]]):
                    self.assertEqual(measure(v, f)['passed'], expected)

    def test_generated_contacts_against_independent_linear_programs(self):
        from scipy.optimize import linprog
        rng = np.random.default_rng(20261025)
        positive = [0, 0]
        for shared in (False, True):
            for _ in range(120):
                a, b = rng.normal(size=(2, 3, 3))
                if shared:
                    b[0] = a[0]
                equality = np.c_[a[1]-a[0], a[2]-a[0], -(b[1]-b[0]), -(b[2]-b[0]), np.zeros(3)]
                inequality = np.r_[np.c_[-np.eye(4),np.ones(4)], [[1,1,0,0,1],[0,0,1,1,1]]]
                result = linprog([0,0,0,0,-1], A_eq=equality, b_eq=b[0]-a[0], A_ub=inequality,
                                 b_ub=[0,0,0,0,1,1], bounds=[(0,None)]*4+[(0,1/3)], method='highs')
                overlap = result.success and result.x[-1] > 1e-7
                if result.success and 1e-9 < result.x[-1] <= 1e-7:
                    continue  # Keep near-boundary numerical cases separate.
                positive[int(shared)] += int(overlap)
                v = np.r_[a, b[1:] if shared else b]
                faces = [[0,1,2],[0,3,4]] if shared else [[0,1,2],[3,4,5]]
                for scale in (.001, 1., 1000.):
                    self.assertEqual(not measure(v*scale, faces)['passed'], bool(overlap))
        self.assertTrue(all(count > 10 for count in positive))


if __name__ == '__main__':
    unittest.main()
