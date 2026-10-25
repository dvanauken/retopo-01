"""Geometric controls for the additional non-adjacent crossing screen."""
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

    def test_topological_neighbors_are_excluded(self):
        self.assertTrue(measure([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], [[0, 1, 2], [0, 2, 3]])['passed'])


if __name__ == '__main__':
    unittest.main()
