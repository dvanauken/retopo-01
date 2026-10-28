"""Residual repairs add local quads without cutting authored guide edges."""
from pathlib import Path
import sys,unittest
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from feature_repair import refine_failures,failure_points,failure_region,refine_guides,local_surface_samples
from source_features import measure
import curved_quad as cq


class ResidualRepair(unittest.TestCase):
    def setUp(self):
        self.v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],float)
        self.q=np.array([[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]])
        self.f=np.r_[self.q[:,[0,1,2]],self.q[:,[0,2,3]]]
        self.source=trimesh.Trimesh(self.v,self.f,process=False)

    def test_local_refinement_preserves_guides_and_closed_topology(self):
        p=self.v*.85+.075
        report=dict(features=measure(self.v,self.f,p,self.q,24))
        self.assertFalse(report['features']['passed'])
        paths=[dict(vertices=[0,1,2],closed=False)]
        positions,faces,detail=refine_failures(self.source,p,self.q,paths,24,report)
        self.assertGreater(detail['addedFaces'],0)
        self.assertLessEqual(len(faces),int(24*1.15))
        edges={tuple(e) for e in cq._edges(faces)}
        self.assertTrue({(0,1),(1,2)}<=edges)
        output=trimesh.Trimesh(positions,np.r_[faces[:,[0,1,2]],faces[:,[0,2,3]]],process=False)
        self.assertTrue(output.is_watertight);self.assertTrue(output.is_winding_consistent)
        self.assertEqual(output.euler_number,self.source.euler_number)
        np.testing.assert_array_equal(self.source.vertices,self.v)
        np.testing.assert_array_equal(positions[:len(p)],p)

    def test_surface_witness_selects_a_region_without_feature_failure(self):
        report=dict(surface=dict(wholeSurfaceDiagonals={'02':dict(sourceToOutput=dict(passed=False,witness=[.5,.5,0]),outputToSource=dict(passed=True))}))
        np.testing.assert_array_equal(failure_points(self.source,self.v,self.q,24,report),[[.5,.5,0]])
        self.assertGreater(len(failure_region(self.source,self.v,self.q,24,report)),0)

    def test_passing_report_does_not_change_connectivity(self):
        positions,faces,detail=refine_failures(self.source,self.v,self.q,[],24,{})
        np.testing.assert_array_equal(positions,self.v);np.testing.assert_array_equal(faces,self.q)
        self.assertEqual(detail['addedFaces'],0)

    def test_partial_guide_refinement_respects_budget_and_connected_paths(self):
        paths=[dict(vertices=[0,1,2,3,0],closed=True),dict(vertices=[4,5,6,7,4],closed=True)]
        curves=[self.v[path['vertices']] for path in paths]
        p,q,refined,detail=refine_guides(self.v,self.q,paths,12,curves,1.)
        self.assertTrue(detail['budgeted']);self.assertGreater(detail['addedFaces'],0)
        self.assertLessEqual(len(q),int(12*1.15));edges={tuple(e) for e in cq._edges(q)}
        for path in refined:
            ids=path['vertices'];self.assertEqual(ids[0],ids[-1])
            self.assertEqual(len(set(ids[:-1])),len(ids)-1)
            self.assertTrue(all(tuple(sorted(e)) in edges for e in zip(ids[:-1],ids[1:])))
        output=trimesh.Trimesh(p,np.r_[q[:,[0,1,2]],q[:,[0,2,3]]],process=False)
        self.assertTrue(output.is_watertight);self.assertTrue(output.is_winding_consistent)

    def test_local_surface_samples_find_inset_faces_and_ignore_exact_cube(self):
        self.assertEqual(local_surface_samples(self.source,self.v,self.q,600,[0]),[])
        points=local_surface_samples(self.source,self.v*.9+.05,self.q,600,[0])
        self.assertGreater(len(points),3)
        distance=trimesh.proximity.closest_point(self.source,points)[1]
        self.assertTrue(np.all(distance>.042))


if __name__=='__main__':unittest.main()
