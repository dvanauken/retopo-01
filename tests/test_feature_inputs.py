"""Reject invalid geometry before starting the native field process."""
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import feature_quad


class FeatureInputChecks(unittest.TestCase):
    def reject(self,vertices,faces,curves,pattern):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(ROOT/'runs'))
            with patch.object(feature_quad,'runtime') as runtime:
                with self.assertRaisesRegex(ValueError,pattern):
                    feature_quad.construct(vertices,faces,curves,target=150,job=folder)
                runtime.assert_not_called()

    def test_invalid_guides_do_not_launch_native_processes(self):
        cube=trimesh.creation.box()
        for curve in ([[0,0,0],[0,0,0]],[[0,0,0],[np.nan,0,0]],[[0,0],[1,0]],[[0,0,0]]):
            with self.subTest(curve=curve):self.reject(cube.vertices,cube.faces,[curve],'distinct consecutive finite')

    def test_open_and_collapsed_sources_do_not_launch_native_processes(self):
        cube=trimesh.creation.box()
        self.reject(cube.vertices,cube.faces[1:],[],'nondegenerate source')
        self.reject(np.zeros_like(cube.vertices),cube.faces,[],'nondegenerate source')

    def test_invalid_targets_do_not_create_jobs(self):
        for target in (True,0,149,12001,7200.5):
            with self.subTest(target=target),self.assertRaisesRegex(ValueError,'target must be an integer'):
                feature_quad.construct([],[],[],target=target,job=None)


if __name__=='__main__':unittest.main()
