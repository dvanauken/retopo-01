"""Acceptance contract for one mild connected surface-guide tangent outlier."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'),
                str(ROOT / 'engine/targets/zbrush/experiments/python')]
import numpy as np
from curved_quad import guides_pass, _guide_fit


def rows(*angles, distance=.01):
    return [dict(p95Distance=distance, p95TangentAngleDegrees=angle)
            for angle in angles]


class TangentPolicyTests(unittest.TestCase):
    def test_one_mild_outlier_in_any_position(self):
        self.assertTrue(guides_pass(rows(34, 28, 27, 26), .08))
        self.assertTrue(guides_pass(rows(26, 28, 34, 27), .08))

    def test_two_mild_outliers_reject(self):
        self.assertFalse(guides_pass(rows(31, 34, 27, 26), .08))

    def test_single_angle_above_35_rejects(self):
        self.assertFalse(guides_pass(rows(36, 28, 27, 26), .08))

    def test_distance_bound_stays_independent(self):
        self.assertFalse(guides_pass(rows(26, 28, 34, 27, distance=.017), .08))


    def test_guide_direction_is_compared_over_one_face(self):
        # A straight output edge path under a hand-drawn guide that zig-zags every quarter face.
        positions = np.array([[x, 0., 0.] for x in range(11)])
        path = dict(vertices=list(range(11)), closed=False)
        guide = np.array([[x * .25, .1 * (-1) ** x, 0.] for x in range(41)])
        jagged = _guide_fit(positions, [path], [guide])[0]
        face = _guide_fit(positions, [path], [guide], spacing=1.)[0]
        self.assertGreater(jagged['p95TangentAngleDegrees'], 30)
        self.assertLess(face['p95TangentAngleDegrees'], 15)
        self.assertAlmostEqual(face['p95Distance'], jagged['p95Distance'])


if __name__ == '__main__':
    unittest.main()
