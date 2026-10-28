"""Fail-closed controls for guide/surface repair acceptance."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'),
               str(ROOT / 'engine/targets/zbrush/experiments/python')]
import surface_guide_joint as joint


class JointAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.mesh = SimpleNamespace(area=4., vertices=np.zeros((4, 3)), faces=np.array([[0, 1, 2], [0, 2, 3]]))
        self.positions = np.zeros((4, 3))
        self.faces = np.array([[0, 1, 2, 3]])
        self.guides = SimpleNamespace(paths=[{}], curves=[np.zeros((2, 3))])

    def assess(self, *, shape=True, angle=20., distance=.1, contacts=True, topology=True,
               surface=True, unresolved=False, protected=None):
        direction = dict(passed=not unresolved, sampledMax=.4, witness=None)
        bounds = {d: dict(passed=not unresolved, sourceToOutput=direction, outputToSource=direction) for d in ('02', '13')}
        with patch.object(joint.cq, 'quad_quality', return_value=dict(passed=shape)), \
             patch.object(joint.cq, '_guide_fit', return_value=[dict(p95Distance=distance, p95TangentAngleDegrees=angle)]), \
             patch.object(joint.cq, 'surface_intersections', return_value=dict(passed=contacts)) as contact_check, \
             patch.object(joint.cq, 'validate_surface', return_value=dict(passed=surface, checks=dict(topology=topology), wholeSurfaceDiagonals=bounds)) as surface_check, \
             patch.object(joint.cq, 'surface_distance') as fallback_check:
            result = joint.assess(self.mesh, self.positions, self.faces, self.guides, 4, protected)
            return result, contact_check, surface_check, fallback_check

    def test_failing_guide_can_be_repaired_but_cannot_be_accepted(self):
        result, contacts, surface, _ = self.assess(angle=np.nextafter(35., np.inf))
        self.assertTrue(result['eligibleForRepair'])
        self.assertFalse(result['qualified'])
        self.assertGreater(result['violationScore'], 1)
        contacts.assert_called_once_with(self.positions, self.faces, both_quad_diagonals=True)
        surface.assert_called_once()

    def test_protected_guide_cannot_be_sacrificed(self):
        for metrics, key in ((dict(angle=36.), 'guide0Angle'), (dict(distance=.21), 'guide0Distance')):
            with self.subTest(key=key):
                result, contacts, surface, _ = self.assess(**metrics, protected={key: True})
                self.assertFalse(result['eligibleForRepair'])
                self.assertFalse(result['qualified'])
                self.assertIn(key, result['protectedGateFailures'])
                contacts.assert_not_called()
                surface.assert_not_called()

    def test_shape_and_contact_failures_block_repair(self):
        for metrics in (dict(shape=False), dict(contacts=False)):
            with self.subTest(**metrics):
                result, _, surface, _ = self.assess(**metrics)
                self.assertFalse(result['eligibleForRepair'])
                self.assertFalse(result['qualified'])
                surface.assert_not_called()

    def test_invalid_topology_cannot_be_overridden_by_surface_measurement(self):
        result, _, _, fallback = self.assess(topology=False, surface=False)
        self.assertFalse(result['eligibleForRepair'])
        self.assertFalse(result['qualified'])
        fallback.assert_not_called()

    def test_unresolved_bound_never_counts_as_passed_despite_low_samples(self):
        result, _, _, _ = self.assess(surface=False, unresolved=True)
        self.assertTrue(result['eligibleForRepair'])
        self.assertFalse(result['qualified'])
        self.assertGreater(result['violationScore'], 1)
        self.assertFalse(result['gatePassed']['13outputToSource'])

    def test_previously_passing_direction_cannot_be_sacrificed(self):
        result, _, _, _ = self.assess(surface=False, unresolved=True, protected={'13outputToSource': True})
        self.assertFalse(result['eligibleForRepair'])
        self.assertFalse(result['qualified'])
        self.assertIn('13outputToSource', result['protectedGateFailures'])

    def test_boundary_acceptance_requires_surface_validator_as_well(self):
        result, _, _, _ = self.assess(angle=35., distance=.2)
        self.assertTrue(result['qualified'])
        result, _, _, _ = self.assess(angle=35., distance=.2, surface=False)
        self.assertFalse(result['qualified'])

    def test_single_mild_outlier_passes_but_higher_error_does_not(self):
        result, _, _, _ = self.assess(angle=34.)
        self.assertTrue(result['qualified'])
        result, _, _, _ = self.assess(angle=36.)
        self.assertFalse(result['qualified'])


if __name__ == '__main__':
    unittest.main()
