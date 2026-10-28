from pathlib import Path
import sys
import unittest
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from quad_connectivity import dissolve_double_edges,split_vertex_stars,split_vertex_cut,corner_scores,polychords,collapse_polychords,vertex_stars,clean_slivers,weld_pinched_quads,fill_triangle_holes
from boundary_geometry import loops


class Connectivity(unittest.TestCase):
    def test_every_cube_vertex_cut_stays_closed_and_consistently_wound(self):
        v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],float)
        q=np.array([[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]])
        for mask in range(256):
            selected=[i for i in range(8) if mask&(1<<i)]
            p,f,_=split_vertex_cut(v,q,selected)
            mesh=trimesh.Trimesh(p,np.r_[f[:,[0,1,2]],f[:,[0,2,3]]],process=False)
            self.assertTrue(mesh.is_watertight,mask)
            self.assertTrue(mesh.is_winding_consistent,mask)
            self.assertEqual(mesh.euler_number,2,mask)
            self.assertGreater(corner_scores(p,f).min(),.7,mask)
            np.testing.assert_array_equal(p[:8],v)

    def test_degree_two_quad_disk_becomes_one_quad(self):
        v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[.5,.5,.2]])
        p,q,info=dissolve_double_edges(v,[[0,1,4,3],[2,3,4,1]])
        self.assertEqual(info['dissolvedVertices'],1)
        self.assertEqual(q.shape,(1,4));self.assertEqual(len(p),4)
        self.assertGreater(corner_scores(p,q).min(),.99)

    def test_local_star_preserves_closed_cube_winding_and_euler(self):
        v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],float)
        q=np.array([[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]])
        p,f,info=split_vertex_stars(v,q,[0],12)
        self.assertEqual(info['addedFaces'],6)
        self.assertGreater(corner_scores(p,f).min(),.7)
        mesh=trimesh.Trimesh(p,np.r_[f[:,[0,1,2]],f[:,[0,2,3]]],process=False)
        self.assertTrue(mesh.is_watertight);self.assertTrue(mesh.is_winding_consistent)
        self.assertEqual(mesh.euler_number,2)
        np.testing.assert_array_equal(p[:len(v)],v)
        p2,f2,info2=split_vertex_stars(v,q,[0],11)
        np.testing.assert_array_equal(f2,q);self.assertEqual(info2['addedFaces'],0)

    @staticmethod
    def grid(columns,rows):
        v=np.array([[x,y,0] for y in range(rows+1) for x in range(columns+1)],float)
        q=np.array([[y*(columns+1)+x,y*(columns+1)+x+1,(y+1)*(columns+1)+x+1,(y+1)*(columns+1)+x] for y in range(rows) for x in range(columns)])
        return v,q

    def test_open_grid_has_one_strip_per_row_and_column(self):
        v,q=self.grid(6,4);chords=polychords(q)
        self.assertEqual(len(chords),10);self.assertFalse(any(closed for _,_,closed in chords))
        self.assertEqual(sorted(len(strip) for strip,_,_ in chords),[4]*6+[6]*4)

    def test_strip_collapse_keeps_a_regular_open_grid_and_protected_loops(self):
        v,q=self.grid(6,4)
        # Treat the middle column line as a crease loop: protected and kept apart from other loops.
        crease=[i for i in range(len(v)) if v[i,0]==3]
        p,f,info=collapse_polychords(v,q,12,protected=crease,keep_apart=crease,spacing=1.)
        self.assertLessEqual(len(f),12*1.05);self.assertGreaterEqual(len(f),12*.85);self.assertGreater(info['collapsedStrips'],0)
        mesh=trimesh.Trimesh(np.c_[p[:,:2],np.zeros(len(p))],np.r_[f[:,[0,1,2]],f[:,[0,2,3]]],process=False)
        self.assertTrue(mesh.is_winding_consistent);self.assertEqual(mesh.euler_number,1)
        self.assertEqual(len(loops(f)),1)
        valence=np.bincount(f.ravel());interior=np.setdiff1d(np.arange(len(p)),np.concatenate(loops(f)))
        self.assertTrue(np.all(valence[interior]==4))
        # The protected line is still one edge path at x=3 from the bottom boundary to the top.
        line=set(np.flatnonzero(np.isclose(p[:,0],3)).tolist())
        path={tuple(sorted((int(a),int(b)))) for face in f for a,b in zip(face,np.roll(face,-1)) if a in line and b in line}
        self.assertEqual(len(path),len(line)-1);self.assertEqual({p[i,1] for i in line}>={0.,4.},True)

    def test_vertex_stars_are_cyclic_and_open_only_on_the_boundary(self):
        v,q=self.grid(3,3);stars=vertex_stars(q)
        ring,closed=stars[5]
        self.assertTrue(closed);self.assertEqual(sorted(ring),[1,4,6,9]);self.assertEqual({ring[0],ring[2]}|{ring[1],ring[3]},{1,4,6,9})
        self.assertIn({ring[0],ring[2]},({1,9},{4,6}))
        ring,closed=stars[0];self.assertFalse(closed);self.assertEqual(len(ring),2)
        ring,closed=stars[1];self.assertFalse(closed);self.assertEqual(len(ring),3);self.assertEqual(ring[1],5)

    def test_sliver_cleanup_collapses_a_needle_and_leaves_a_clean_grid_alone(self):
        v,q=self.grid(2,2);v[4]=[1.5,.01,0]   # the center vertex nearly on the bottom edge: a 1-degree corner at vertex 1
        p,f,info=clean_slivers(v,q)
        self.assertEqual(info['collapsedSlivers'],1);self.assertEqual(len(f),2);self.assertEqual(len(loops(f)),1)
        self.assertTrue(all(len(set(face))==4 for face in f))
        P=p[f];a=P-np.roll(P,1,1);b=np.roll(P,-1,1)-P
        angles=np.degrees(np.arccos(np.clip(-(a*b).sum(2)/(np.linalg.norm(a,axis=2)*np.linalg.norm(b,axis=2)),-1,1)))
        self.assertGreater(angles.min(),15)
        self.assertTrue(any(np.allclose(row,[1,0,0]) for row in p))   # the boundary vertex kept its position
        v,q=self.grid(3,2);p,f,info=clean_slivers(v,q)
        self.assertEqual(info['collapsedSlivers'],0);np.testing.assert_array_equal(f,q);np.testing.assert_array_equal(p,v)


    def test_pinched_quad_between_vertex_copies_is_welded_away(self):
        # A 2x2 grid whose centre vertex was split into two copies, with a zero-area quad pinched between them.
        v=np.array([[0,0,0],[1,0,0],[2,0,0],[0,1,0],[1,1,0],[2,1,0],[0,2,0],[1,2,0],[2,2,0],[1,1,0]],float)
        q=np.array([[0,1,4,3],[1,2,5,4],[3,9,7,6],[9,5,8,7],[4,5,9,3]])   # last quad: 4 and 9 coincide
        p,f,info=weld_pinched_quads(v,q)
        self.assertEqual(info['weldedVertices'],1);self.assertEqual(info['droppedPinchedQuads'],1)
        self.assertEqual(len(f),4);self.assertEqual(len(p),9)
        self.assertEqual(len(loops(f)),1)
        self.assertGreater(corner_scores(p,f).min(),.99)

    def test_triangle_hole_is_closed_by_a_conforming_chord(self):
        # A triangular hole ringed by six quads (three on its edges, three at its corners) and a second ring of nine.
        import math
        def ring(radius,angles):return [[radius*math.cos(math.radians(a)),radius*math.sin(math.radians(a)),0.] for a in angles]
        theta=[90,210,330];outer=[t+d for t in theta for d in (-30,0,30)]
        v=np.array(ring(1,theta)+ring(2.5,outer)+ring(4,outer))
        q=[[(i+1)%3,i,5+3*i,3+3*((i+1)%3)] for i in range(3)]+[[i,3+3*i,4+3*i,5+3*i] for i in range(3)]
        q+=[[3+(k+1)%9,3+k,12+k,12+(k+1)%9] for k in range(9)]
        self.assertEqual(sorted(len(r) for r in loops(np.asarray(q))),[3,9])
        p,f,info=fill_triangle_holes(v,q,keep_loops=1)
        self.assertEqual(info['filledTriangleHoles'],1);self.assertEqual(info['addedQuads'],2)
        self.assertEqual(len(loops(f)),1);self.assertEqual(len(f),17)
        self.assertEqual(f.shape[1],4);self.assertTrue(all(len(set(face))==4 for face in f.tolist()))
        mesh=trimesh.Trimesh(p,np.r_[f[:,[0,1,2]],f[:,[0,2,3]]],process=False)
        self.assertTrue(mesh.is_winding_consistent)
        edges=np.sort(np.stack([f,np.roll(f,-1,1)],axis=2).reshape(-1,2),axis=1)
        _,counts=np.unique(edges,axis=0,return_counts=True);self.assertLessEqual(counts.max(),2)
        self.assertGreater(corner_scores(p,f).min(),.1)   # a topological repair; the fit and relaxation shape the new quads


if __name__=='__main__':unittest.main()
