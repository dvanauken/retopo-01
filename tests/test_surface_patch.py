"""Local curved-surface repair preserves the surrounding mesh and topology."""
from pathlib import Path
import sys,unittest
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from surface_patch import repair
from surface_intersections import measure


class LocalPatch(unittest.TestCase):
    def setUp(self):
        n,m=24,16
        self.p=np.array([[(2+.6*np.cos(v))*np.cos(u),(2+.6*np.cos(v))*np.sin(u),.6*np.sin(v)]
                         for u in np.arange(n)*2*np.pi/n for v in np.arange(m)*2*np.pi/m])
        self.q=np.array([[i*m+j,((i+1)%n)*m+j,((i+1)%n)*m+(j+1)%m,i*m+(j+1)%m]
                         for i in range(n) for j in range(m)])
        self.source=trimesh.Trimesh(self.p,np.r_[self.q[:,[0,1,2]],self.q[:,[0,2,3]]],process=False)
        self.face=5*m+4;self.vertex=self.q[self.face,0]

    def test_curved_disk_repair_keeps_source_and_surrounding_vertices(self):
        broken=self.p.copy();broken[self.vertex]+=[0.,0.,.3]
        p,q,detail=repair(self.source,broken,self.q,[self.face],rings=1)
        self.assertTrue(detail['applied'],detail)
        changed=np.flatnonzero(np.linalg.norm(p-broken,axis=1)>1e-12)
        self.assertIn(self.vertex,changed)
        self.assertLess(len(changed),len(self.p)//10)
        self.assertLess(trimesh.proximity.closest_point(self.source,p[changed])[1].max(),1e-8)
        mesh=trimesh.Trimesh(p,np.r_[q[:,[0,1,2]],q[:,[0,2,3]]],process=False)
        self.assertTrue(mesh.is_watertight);self.assertTrue(mesh.is_winding_consistent)
        self.assertEqual(mesh.euler_number,0)
        self.assertTrue(measure(p,q,both_quad_diagonals=True)['passed'])
        np.testing.assert_array_equal(self.source.vertices,self.p)

    def test_protected_guide_vertex_rejects_without_mutating_the_input(self):
        broken=self.p.copy();broken[self.vertex]+=[0.,0.,.3]
        p,q,detail=repair(self.source,broken,self.q,[self.face],[self.vertex],rings=1)
        self.assertFalse(detail['applied'])
        np.testing.assert_array_equal(p,broken);np.testing.assert_array_equal(q,self.q)

    def test_guide_edge_is_preserved_when_its_vertices_can_be_refitted(self):
        broken=self.p.copy();broken[self.vertex]+=[0.,0.,.3]
        edge=tuple(sorted(map(int,self.q[self.face,:2])))
        p,q,detail=repair(self.source,broken,self.q,[self.face],edge,rings=1,protected_edges=[edge],allow_guide_vertices=True)
        self.assertTrue(detail['applied'],detail)
        edges={tuple(sorted((int(a),int(b)))) for face in q for a,b in zip(face,np.roll(face,-1))}
        self.assertIn(edge,edges)
        mesh=trimesh.Trimesh(p,np.r_[q[:,[0,1,2]],q[:,[0,2,3]]],process=False)
        self.assertTrue(mesh.is_watertight);self.assertTrue(mesh.is_winding_consistent)


if __name__=='__main__':unittest.main()
