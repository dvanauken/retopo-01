"""Acceptance and unresolved-bound controls for sampled guide repair."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
import surface_guide_repair as repair


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.mesh = SimpleNamespace(area=4., vertices=np.zeros((4, 3)), faces=np.array([[0, 1, 2], [0, 2, 3]]))
        self.positions = np.zeros((4, 3))
        self.faces = np.array([[0, 1, 2, 3]])
        self.guides = SimpleNamespace(paths=[{}], curves=[np.zeros((2, 3))])

    def assess(self, *, shape=True, distance=.1, angle=20., contacts=True, surface=True, unresolved=False):
        direction = dict(passed=not unresolved, sampledMax=.4, witness=None)
        bounds = {diagonal: dict(passed=not unresolved, sourceToOutput=direction, outputToSource=direction) for diagonal in ('02', '13')}
        with patch.object(repair.cq, 'quad_quality', return_value=dict(passed=shape)), \
             patch.object(repair.cq, '_guide_fit', return_value=[dict(p95Distance=distance, p95TangentAngleDegrees=angle)]), \
             patch.object(repair.cq, 'surface_intersections', return_value=dict(passed=contacts)) as contact_check, \
             patch.object(repair.cq, 'validate_surface', return_value=dict(passed=surface, wholeSurfaceDiagonals=bounds)) as surface_check:
            result = repair._assess(self.mesh, self.positions, self.faces, self.guides, 4)
            return result, contact_check.call_count, surface_check.call_count

    def test_shape_rejection_does_not_claim_unchecked_geometry_passes(self):
        result, contacts, surface = self.assess(shape=False)
        self.assertFalse(result['qualified'])
        self.assertFalse(result['eligibleForRepair'])
        self.assertEqual((contacts, surface), (0, 0))
        self.assertIsNone(result['intersections']['passed'])
        self.assertFalse(result['intersections']['checked'])

    def test_guide_boundaries_reject_before_expensive_checks(self):
        for metrics in (dict(distance=np.nextafter(.2, np.inf)), dict(angle=np.nextafter(35., np.inf))):
            with self.subTest(**metrics):
                result, contacts, surface = self.assess(**metrics)
                self.assertFalse(result['qualified'])
                self.assertFalse(result['eligibleForRepair'])
                self.assertEqual((contacts, surface), (0, 0))

    def test_contact_rejection_cannot_enter_surface_repair(self):
        result, contacts, surface = self.assess(contacts=False)
        self.assertFalse(result['qualified'])
        self.assertFalse(result['eligibleForRepair'])
        self.assertEqual((contacts, surface), (1, 0))

    def test_full_surface_failure_still_rejects_a_repairable_candidate(self):
        result, contacts, surface = self.assess(surface=False, unresolved=True)
        self.assertTrue(result['eligibleForRepair'])
        self.assertFalse(result['qualified'])
        self.assertEqual((contacts, surface), (1, 1))

    def test_limits_are_inclusive_and_all_gates_are_required(self):
        result, contacts, surface = self.assess(distance=.2, angle=35.)
        self.assertTrue(result['qualified'])
        self.assertEqual((contacts, surface), (1, 1))

    def test_single_mild_tangent_outlier_remains_eligible(self):
        result, contacts, surface = self.assess(angle=34.)
        self.assertTrue(result['qualified'])
        self.assertEqual((contacts, surface), (1, 1))

    def test_unresolved_surface_without_witness_cannot_trigger_speculative_repair(self):
        current, _, _ = self.assess(surface=False, unresolved=True)
        record = Mock()
        with patch.object(repair.fitter, 'refine') as refine:
            positions, result = repair._repair(self.mesh, self.positions, self.faces, np.empty((0, 2), int),
                                               self.guides, 4, current, record, ROOT / 'runs')
        self.assertIs(positions, self.positions)
        self.assertIs(result, current)
        self.assertFalse(result['qualified'])
        refine.assert_not_called()
        record.assert_not_called()


if __name__ == '__main__':
    unittest.main()
