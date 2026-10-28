from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone')]
import source_features
from source_features import measure,segment_distances,detect,branches,band_widths,spacing,admission_length


def chamfer(width):
    """A 100-degree corner cut by a chamfer strip: two parallel 50-degree creases width apart."""
    turn=np.radians(50);p1=np.array([1.,0]);p2=p1+width*np.array([np.cos(turn),np.sin(turn)])
    profile=[np.array([0.,0]),p1,p2,p2+np.array([np.cos(2*turn),np.sin(2*turn)])]
    # The sharp corner the chamfer replaced: where the outer faces' lines meet.
    run=(p2[1]-0)/np.sin(2*turn)*np.cos(2*turn);corner=np.array([p2[0]-run,0.])
    return profile,corner


def extrude(profile,length=4.):
    vertices=np.array([[x,y,z] for y in (0,length) for x,z in profile],float);n=len(profile)
    quads=np.array([[i,i+1,n+i+1,n+i] for i in range(n-1)]);return vertices,quads


class SourceFeatures(unittest.TestCase):
    def setUp(self):
        self.v=np.array([[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]],float)
        self.q=np.array([[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]])
        self.f=np.r_[self.q[:,[0,1,2]],self.q[:,[0,2,3]]]

    def test_retained_cube_creases_pass_and_inset_cube_fails(self):
        # Target 600 gives 0.1-unit faces, so a 0.07 inset is more than half a face.
        exact=measure(self.v,self.f,self.v,self.q,600)
        self.assertTrue(exact['passed']);self.assertEqual(exact['sourceFeatureEdges'],12)
        inset=measure(self.v,self.f,self.v*.9+.05,self.q,600)
        self.assertFalse(inset['passed']);self.assertIn('edgeMax',inset['failures'])

    def test_long_segment_is_not_lost_by_midpoint_search(self):
        result=segment_distances([[0,.1,0]],[[-1,0,0],[0,1,0]],[[1000,0,0],[.1,1,0]])
        self.assertAlmostEqual(result[0],.1)

    def test_subspacing_components_are_reported_separately(self):
        v=np.r_[self.v,self.v*.01+3];f=np.r_[self.f,self.f+8]
        # Summed length decides: the unit cube's creases total 12, the 1 % cube's 0.12.
        edges,report=detect(v,f,1.)
        self.assertEqual(len(edges),12);self.assertEqual(report['rawEdges'],24)
        self.assertEqual(report['fragmentEdges'],12)

    def test_branches_split_at_junctions_and_keep_loops_whole(self):
        # A Y junction (three branches; one passes through a degree-2 node) and a separate loop.
        label=branches([[0,1],[0,2],[2,5],[0,3],[10,11],[11,12],[12,10]])
        self.assertEqual(len(set(label)),4);self.assertEqual(label[1],label[2])
        self.assertEqual(len({label[4],label[5],label[6]}),1)

    def test_band_width_counts_only_close_parallel_other_branches(self):
        v=np.array([[0,0,0],[4,0,0],[0,.2,0],[4,.2,0],[0,.7,0],[4,.7,0],[2,-.1,0],[2,-.3,0]],float)
        samples=np.array([[1,0,0],[3,0,0]],float)
        # Parallel crease .2 away, a farther one at .7, and a perpendicular stub just below.
        width=band_widths(v,[[0,1],[2,3],[4,5],[6,7]],samples,[0,0],1.)
        np.testing.assert_allclose(width,[.2,.2])
        self.assertEqual(band_widths(v,[[0,1],[4,5],[6,7]],samples,[0,0],1.).tolist(),[0,0])

    def test_one_edge_loop_represents_a_chamfer_narrower_than_half_a_quad(self):
        profile,corner=chamfer(.02);v,q=extrude(profile);f=np.r_[q[:,[0,1,2]],q[:,[0,2,3]]];target=3000
        h=spacing(v,f,target);self.assertLess(.02/h,source_features.BAND_REACH)
        sharp,quads=extrude([profile[0],corner,profile[3]])
        result=measure(v,f,sharp,quads,target)
        self.assertTrue(result['passed'],result['failures']);self.assertEqual(result['sourceFeatureEdges'],2)
        self.assertEqual(result['bandSamples'],result['samples'])
        reach=source_features.BAND_REACH
        try:
            source_features.BAND_REACH=0
            self.assertIn('edgeP95',measure(v,f,sharp,quads,target)['failures'])
        finally:source_features.BAND_REACH=reach
        moved,quads=extrude([profile[0],corner-[1.5*h,0],profile[3]])
        self.assertIn('edgeMax',measure(v,f,moved,quads,target)['failures'])


if __name__=='__main__':unittest.main()
