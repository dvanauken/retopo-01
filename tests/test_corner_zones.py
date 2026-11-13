"""Corner zones: the source against the output where crease branches meet, in requested faces."""
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import corner_zones
from source_features import detect,spacing
FIXTURES=ROOT/'tests/fixtures'


def read(path):
    vertices,faces=[],[]
    for line in Path(path).read_text().splitlines():
        if line.startswith('v '):vertices.append([float(x) for x in line.split()[1:4]])
        elif line.startswith('f '):faces.append([int(x.split('/')[0])-1 for x in line.split()[1:]])
    return np.asarray(vertices),faces


def grid(n=21,size=4.):
    """A flat square source of n x n vertices, `size` across, in z = 0."""
    axis=np.linspace(0,size,n)
    return np.array([[x,y,0.] for y in axis for x in axis])


class Zones(unittest.TestCase):
    def star(self,centre,n=21):
        """Three crease edges meeting at one grid vertex: a junction."""
        row,column=centre;at=lambda r,c:r*n+c
        return [[at(row,column),at(row,column+1)],[at(row,column),at(row+1,column)],[at(row,column),at(row,column-1)]]

    def test_a_junction_of_three_creases_makes_one_zone_within_one_face(self):
        source=grid();edges=self.star((10,10))
        zones=corner_zones.zones(source,edges,1.05)     # 1.05, so no grid vertex lies exactly on the reach
        self.assertEqual(len(zones),1);self.assertEqual(zones[0]['junctions'],[10*21+10])
        distance=np.linalg.norm(source-source[10*21+10],axis=1)
        # every source vertex within one face is in the zone, and no other
        self.assertEqual(sorted(zones[0]['vertices'].tolist()),np.flatnonzero(distance<=1.05).tolist())
        self.assertEqual(len(zones[0]['vertices']),89)

    def test_a_crease_without_a_junction_has_no_zone(self):
        source=grid();edges=[[10*21+c,10*21+c+1] for c in range(4,16)]
        self.assertEqual(corner_zones.zones(source,edges,1.),[])
        self.assertEqual(corner_zones.zones(source,[],1.),[])

    def test_junctions_closer_than_two_faces_form_one_corner(self):
        source=grid()
        near=self.star((10,6))+self.star((10,14))      # 1.6 apart
        self.assertEqual(len(corner_zones.zones(source,near,1.)),1)
        self.assertEqual(len(corner_zones.zones(source,near,.5)),2)   # the same junctions are 3.2 faces apart at half the spacing

    def test_a_zone_needs_enough_source_vertices(self):
        coarse=grid(n=5)        # one grid step is a whole face: 5 vertices within reach
        edges=[[12,13],[12,17],[12,11]]
        self.assertLess(int((np.linalg.norm(coarse-coarse[12],axis=1)<=1.).sum()),corner_zones.ZONE_MIN_VERTICES)
        self.assertEqual(corner_zones.zones(coarse,edges,1.),[])


class Measure(unittest.TestCase):
    def setUp(self):
        self.source=grid();n=21
        self.triangles=np.array([[r*n+c,r*n+c+1,(r+1)*n+c+1] for r in range(n-1) for c in range(n-1)]+[[r*n+c,(r+1)*n+c+1,(r+1)*n+c] for r in range(n-1) for c in range(n-1)])
        self.edges=Zones().star((10,10))

    def plane(self,height):
        return np.array([[-1,-1,height],[5,-1,height],[5,5,height],[-1,5,height]],float),[[0,1,2,3]]

    def test_distances_are_reported_in_requested_faces(self):
        vertices,faces=self.plane(.2)
        report=corner_zones.measure(self.source,self.triangles,self.edges,vertices,faces,1.)
        self.assertEqual(len(report['zones']),1)
        self.assertAlmostEqual(report['zones'][0]['p95InFaces'],.2);self.assertAlmostEqual(report['zones'][0]['maxInFaces'],.2)
        self.assertTrue(report['passed'])
        half=corner_zones.measure(self.source,self.triangles,self.edges,vertices,faces,.5)   # the same gap is 0.4 of a smaller face
        self.assertAlmostEqual(half['zones'][0]['maxInFaces'],.4);self.assertFalse(half['passed'])
        self.assertEqual(half['failures'],['zone 1: p95InFaces'])

    def test_a_folded_face_over_the_corner_fails_the_maximum(self):
        # A tent over the junction: on the surface at the zone's rim, 0.6 of a face above it at the junction.
        centre=self.source[10*21+10]
        vertices=np.array([[-2,-2,-.6*4/2+.6],[6,-2,-.6*4/2+.6],[6,6,-.6*4/2+.6],[-2,6,-.6*4/2+.6],[centre[0],centre[1],.6]])
        faces=[[0,1,4],[1,2,4],[2,3,4],[3,0,4]]
        report=corner_zones.measure(self.source,self.triangles,self.edges,vertices,faces,1.)
        self.assertFalse(report['passed']);self.assertIn('zone 1: maxInFaces',report['failures'])
        self.assertEqual(report['zones'][0]['worstSourceVertex'],10*21+10)

    def test_a_mask_measures_any_named_zone(self):
        vertices,faces=self.plane(.1)
        zone=corner_zones.measure_zone(self.source,vertices,faces,1.,self.source[:,1]>3.)
        self.assertEqual(zone['sourceVertices'],int((self.source[:,1]>3.).sum()));self.assertAlmostEqual(zone['maxInFaces'],.1)
        self.assertEqual(corner_zones.measure_zone(self.source,vertices,faces,1.,np.zeros(len(self.source),bool))['sourceVertices'],0)


class IslandSixCorners(unittest.TestCase):
    """The reported part at a request of 200 with the guide of job 483afe83 (fixtures: tests/fixtures/corner_zones/README.md)."""
    @classmethod
    def setUpClass(cls):
        cls.v,t=read(FIXTURES/'crease_rows/island6-source.obj');cls.t=np.asarray(t,int)
        cls.h=spacing(cls.v,cls.t,200);cls.edges,_=detect(cls.v,cls.t,cls.h,angle=30.,target=200)

    def fixed(self,name):
        """The zone the corners were first compared in: source vertices with y > 0.05 (both feet and the back of the lip)."""
        vertices,faces=read(FIXTURES/name)
        return corner_zones.measure_zone(self.v,vertices,faces,self.h,self.v[:,1]>.05),vertices,faces

    def test_the_part_has_three_corners_the_two_feet_and_the_front_lip(self):
        zones=corner_zones.zones(self.v,self.edges,self.h)
        self.assertEqual([len(z['vertices']) for z in zones],[280,278,135])
        centres=[self.v[z['junctions']].mean(0) for z in zones]
        self.assertGreater(centres[0][0],.2);self.assertGreater(centres[0][1],.1)     # right foot
        self.assertLess(centres[1][0],-.2);self.assertGreater(centres[1][1],.1)       # left foot
        self.assertLess(centres[2][1],-.9)                                             # front lip

    def test_the_reported_numbers_are_reproduced(self):
        for name,p95,worst in (('corner_zones/island6-200-guide-strict-204.obj',.273,.414),
                               ('corner_zones/island6-200-guide-extra-380-before.obj',.279,.407),
                               ('guide_rows/island6-200-native-guide-532.obj',.246,.304)):
            zone,_,_=self.fixed(name)
            self.assertEqual(zone['sourceVertices'],633)
            self.assertAlmostEqual(zone['p95InFaces'],p95,places=3);self.assertAlmostEqual(zone['maxInFaces'],worst,places=3)

    def test_the_chunky_corners_are_named(self):
        for name,zone in (('corner_zones/island6-200-guide-strict-204.obj',2),('corner_zones/island6-200-guide-extra-380-before.obj',1)):
            vertices,faces=read(FIXTURES/name)
            report=corner_zones.measure(self.v,self.t,self.edges,vertices,faces,self.h)
            self.assertFalse(report['passed'],name)
            self.assertEqual(report['failures'],[f'zone {zone}: p95InFaces'])
            self.assertGreater(report['worstP95InFaces'],.33)

    def test_the_extra_faces_result_follows_its_corners_at_least_as_well_as_zbrush(self):
        ours,vertices,faces=self.fixed('corner_zones/island6-200-guide-extra-faces.obj')
        native,_,_=self.fixed('guide_rows/island6-200-native-guide-532.obj')
        self.assertLessEqual(ours['p95InFaces'],native['p95InFaces']);self.assertLessEqual(ours['maxInFaces'],native['maxInFaces'])
        report=corner_zones.measure(self.v,self.t,self.edges,vertices,faces,self.h)
        self.assertTrue(report['passed'],report['failures'])


if __name__=='__main__':unittest.main()
