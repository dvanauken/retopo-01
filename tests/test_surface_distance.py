"""Analytic controls for whole-triangle distance bounds and budget failures."""
from pathlib import Path
import sys
import unittest
import numpy as np
import trimesh
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from surface_distance import directed_bound, measure


class SurfaceBounds(unittest.TestCase):
    def setUp(self):
        self.square = trimesh.Trimesh([[0,0,0], [1,0,0], [1,1,0], [0,1,0]], [[0,1,2], [0,2,3]], process=False)

    def test_identical_surfaces(self):
        self.assertTrue(measure(self.square, self.square, .01)['passed'])

    def test_parallel_surfaces_inside_tolerance(self):
        other = self.square.copy(); other.vertices += [0,0,.009]
        self.assertTrue(measure(self.square, other, .01)['passed'])

    def test_parallel_surfaces_outside_tolerance(self):
        other = self.square.copy(); other.vertices += [0,0,.011]
        result = measure(self.square, other, .01)
        self.assertFalse(result['passed'])
        self.assertAlmostEqual(result['sourceToOutput']['sampledMax'], .011)

    def test_equivalent_surface_with_opposite_diagonal(self):
        other = trimesh.Trimesh(self.square.vertices, [[0,1,3], [1,2,3]], process=False)
        result = measure(self.square, other, .01)
        self.assertTrue(result['passed'])
        self.assertGreater(result['sourceToOutput']['subdivisionDepth'], 0)

    def test_vertex_correspondence_does_not_hide_an_interior_gap(self):
        # All three source vertices occur in the target, whose disconnected
        # corner triangles leave most of the interior uncovered.
        a = np.array([[0,0,0], [1,0,0], [0,1,0]], dtype=float)
        target = np.array([p + (a-p)*.1 for p in a]).reshape(-1, 3)
        mesh = trimesh.Trimesh(target, [[0,1,2],[3,4,5],[6,7,8]], process=False)
        self.assertFalse(directed_bound(a[None], mesh, .05)['passed'])

    def test_depth_exhaustion_never_passes(self):
        other = trimesh.Trimesh(self.square.vertices, [[0,1,3], [1,2,3]], process=False)
        result = measure(self.square, other, .01, max_depth=0)
        self.assertFalse(result['passed'])
        self.assertEqual(result['sourceToOutput']['status'], 'unresolved')

    def test_work_exhaustion_never_passes(self):
        result = directed_bound(self.square.triangles, self.square, .01, max_triangles=1)
        self.assertFalse(result['passed'])
        self.assertEqual(result['status'], 'unresolved')

    def test_bad_input_rejects(self):
        for triangles, tolerance in ((np.empty((0,3,3)), .1), (self.square.triangles, 0), (np.full((1,3,3), np.nan), .1)):
            with self.assertRaises(ValueError):
                directed_bound(triangles, self.square, tolerance)


if __name__ == '__main__':
    unittest.main()
