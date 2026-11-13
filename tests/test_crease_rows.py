"""Crease rows: every band of parallel source creases needs one connected, ordered output edge row."""
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import crease_rows
from source_features import detect,measure,spacing,admission_length
FIXTURES=ROOT/'tests/fixtures/crease_rows'


def read(path):
    vertices,faces=[],[]
    for line in Path(path).read_text().splitlines():
        if line.startswith('v '):vertices.append([float(x) for x in line.split()[1:4]])
        elif line.startswith('f '):faces.append([int(x.split('/')[0])-1 for x in line.split()[1:]])
    return np.asarray(vertices),faces


def strip(profile,length=8.,steps=8):
    """A profile in (x, z) swept along y: vertices and quads, one quad per profile segment and step."""
    profile=np.asarray(profile,float);n=len(profile)
    vertices=np.array([[x,y,z] for y in np.linspace(0,length,steps+1) for x,z in profile])
    quads=np.array([[r*n+i,r*n+i+1,(r+1)*n+i+1,(r+1)*n+i] for r in range(steps) for i in range(n-1)])
    return vertices,quads


def triangles(quads):
    return np.r_[quads[:,[0,1,2]],quads[:,[0,2,3]]]


# A wide top sheet, a wall 0.3 high and a narrower underside: two parallel creases 0.3 apart.
# Area 62.4, so a target of 62 puts the requested spacing h within half a percent of 1.
LID=[[0,0],[6,0],[6,-.3],[4.5,-.3]]
TARGET=62


class LidBand(unittest.TestCase):
    def setUp(self):
        self.v,quads=strip(LID);self.t=triangles(quads)
        self.h=spacing(self.v,self.t,TARGET);self.edges,_=detect(self.v,self.t,self.h,target=TARGET)

    def rows(self,profile,**kw):
        vertices,quads=strip(profile,**kw)
        return crease_rows.measure(self.v,self.t,self.edges,vertices,quads,self.h),vertices

    def test_the_crease_beside_the_wider_sheet_represents_the_band(self):
        self.assertEqual(len(self.edges),16)
        chains,chosen,absorbed=crease_rows.representatives(self.v,self.t,self.edges,self.h)
        self.assertEqual(len(chains),1);self.assertEqual(int(chosen.sum()),8);self.assertEqual(int(absorbed.sum()),8)
        # The representative is the upper crease (z = 0): the top sheet is 6 wide, the underside 1.5.
        np.testing.assert_allclose(self.v[chains[0]['vertices']][:,[0,2]],np.tile([6.,0.],(9,1)))
        self.assertAlmostEqual(chains[0]['length'],8.)
        widths=crease_rows.sheet_widths(self.v,self.t,self.edges,np.arange(len(self.edges)))
        np.testing.assert_allclose(np.sort(np.unique(np.round(widths,9))),[1.5,6.])

    def test_a_row_on_the_representative_or_anywhere_across_its_band_passes(self):
        for profile in ([[0,0],[3,0],[6,0],[4.5,-.3]],          # row on the upper crease, underside spans the wall
                        [[0,0],[3,0],[6,-.3],[4.5,-.3]],        # row on the lower crease of the same band
                        [[0,0],[3,0],[6,-.15],[4.5,-.3]]):      # row half way down the wall
            report,_=self.rows(profile)
            self.assertTrue(report['passed'],report['chains'][0]);self.assertEqual(report['required'],1)
            self.assertLess(report['chains'][0]['values']['rowP95'],1e-9)

    def test_a_parallel_row_beside_the_band_fails_however_wide_the_band_allowance(self):
        # Edge lines 0.4 h inside the top sheet and on the underside: near the creases, on neither.
        report,_=self.rows([[0,0],[3,0],[5.6,0],[5.2,-.3],[4.5,-.3]])
        chain=report['chains'][0]
        self.assertFalse(report['passed']);self.assertEqual(chain['failures'],['rowP95'])
        self.assertAlmostEqual(chain['values']['rowP95'],.4,places=6)
        # The nearest-edge measure with its band allowance alone accepts the same mesh: this is the gap rows close.
        vertices,quads=strip([[0,0],[3,0],[5.6,0],[5.2,-.3],[4.5,-.3]])
        whole=measure(self.v,self.t,vertices,quads,TARGET)
        self.assertEqual(whole['failures'],['rowsMissing']);self.assertEqual(whole['values']['rowsMissing'],1.)
        self.assertTrue(measure(self.v,self.t,vertices,quads,TARGET,enforce_rows=False)['passed'])

    def test_a_zigzag_across_the_crease_fails_on_direction(self):
        vertices,quads=strip([[0,0],[3,0],[6,0],[4.5,-.3]])
        rim=np.flatnonzero(np.isclose(vertices[:,0],6.));vertices[rim,0]+=np.where(np.arange(len(rim))%2,.45,-.45)
        report=crease_rows.measure(self.v,self.t,self.edges,vertices,quads,self.h)
        self.assertFalse(report['passed']);self.assertIn('rowTangentP95Degrees',report['chains'][0]['failures'])
        self.assertGreater(report['chains'][0]['values']['rowTangentP95Degrees'],crease_rows.ROW_TANGENT_DEGREES)

    def test_no_edge_path_within_a_face_is_a_missing_row(self):
        report,_=self.rows([[0,0],[3,0],[4.5,-.3]])
        self.assertFalse(report['passed']);self.assertEqual(report['chains'][0]['failures'],['rowMissing'])
        self.assertEqual(report['chains'][0]['vertices'],[])

    def test_a_row_must_be_connected(self):
        vertices,quads=strip([[0,0],[3,0],[6,0],[4.5,-.3]])
        # Drop the quads on both sides of the rim in the middle of the strip: the rim edges there go too.
        keep=np.array([not (3<=r<5 and i>=1) for r in range(8) for i in range(3)])
        report=crease_rows.measure(self.v,self.t,self.edges,vertices,quads[keep],self.h)
        self.assertFalse(report['passed'])

    def test_a_chain_under_two_faces_in_extent_needs_no_row(self):
        v,quads=strip(LID,length=1.5,steps=3);t=triangles(quads)
        target=12;h=spacing(v,t,target);self.assertGreater(1.5/h,1.);self.assertLess(1.5/h,crease_rows.ROW_MIN_FACES)
        edges,_=detect(v,t,h,target=target);self.assertEqual(len(edges),6)
        report=crease_rows.measure(v,t,edges,*strip([[0,0],[3,0],[4.5,-.3]],length=1.5,steps=1),h)
        self.assertEqual(report['required'],0);self.assertTrue(report['passed'])

    def test_an_open_row_may_end_within_one_face_of_the_chain_end_but_not_farther(self):
        short,_=self.rows([[0,0],[3,0],[6,0],[4.5,-.3]],length=7.2,steps=8)     # row stops 0.8 h before the chain end
        self.assertTrue(short['passed'],short['chains'][0]);self.assertAlmostEqual(short['chains'][0]['values']['rowEndMax'],.8,places=6)
        shorter,_=self.rows([[0,0],[3,0],[6,0],[4.5,-.3]],length=6.5,steps=8)    # 1.5 h short: more than one face
        self.assertEqual(shorter['chains'][0]['failures'],['rowEndMax'])
        self.assertAlmostEqual(shorter['chains'][0]['values']['rowEndMax'],1.5,places=6)


class ClosedRim(unittest.TestCase):
    """A cylinder wall with a flat cap: the rim is one closed crease chain."""
    def setUp(self):
        n=24;angle=np.linspace(0,2*np.pi,n,endpoint=False);ring=np.c_[2*np.cos(angle),2*np.sin(angle)]
        self.v=np.r_[np.c_[ring,np.zeros(n)],np.c_[ring,np.full(n,2.)],[[0,0,2.]]]
        side=[[i,(i+1)%n,n+(i+1)%n] for i in range(n)]+[[i,n+(i+1)%n,n+i] for i in range(n)]
        self.t=np.array(side+[[n+i,n+(i+1)%n,2*n] for i in range(n)]);self.n=n
        self.target=38;self.h=spacing(self.v,self.t,self.target);self.edges,_=detect(self.v,self.t,self.h,target=self.target)

    def output(self,twist=0.):
        """Twelve rim vertices; `twist` turns every other one around the axis to make the rim zig-zag."""
        m=12;angle=np.linspace(0,2*np.pi,m,endpoint=False);top=angle+np.where(np.arange(m)%2,twist,-twist)
        radius=2+np.where(np.arange(m)%2,twist,-twist)
        vertices=np.r_[np.c_[2*np.cos(angle),2*np.sin(angle),np.zeros(m)],np.c_[radius*np.cos(top),radius*np.sin(top),np.full(m,2.)],[[0,0,2.]]]
        quads=[[i,(i+1)%m,m+(i+1)%m,m+i] for i in range(m)]+[[2*m,m+2*k,m+2*k+1,m+(2*k+2)%m] for k in range(m//2)]
        return vertices,np.array(quads)

    def test_a_closed_chain_is_measured_once_around(self):
        self.assertEqual(len(self.edges),self.n)
        chains,_,_=crease_rows.representatives(self.v,self.t,self.edges,self.h)
        self.assertEqual(len(chains),1);self.assertTrue(chains[0]['closed'])
        report=crease_rows.measure(self.v,self.t,self.edges,*self.output(),self.h)
        chain=report['chains'][0]
        self.assertTrue(report['passed'],chain);self.assertEqual(len(chain['vertices']),13);self.assertEqual(chain['vertices'][0],chain['vertices'][-1])
        self.assertEqual(chain['values']['rowEndMax'],0.)

    def test_a_closed_zigzag_fails(self):
        report=crease_rows.measure(self.v,self.t,self.edges,*self.output(twist=.5),self.h)
        self.assertFalse(report['passed'])


class Chains(unittest.TestCase):
    def test_branches_join_through_a_junction_only_when_they_run_straight_on(self):
        source=np.array([[0,0,0],[1,0,0],[2,0,0],[3,0,0],[2,1,0],[2,2,0]],float)
        found=crease_rows.chains(source,[[0,1],[1,2],[2,3],[2,4],[4,5]],1.)
        self.assertEqual(sorted(map(len,[c[0] for c in found])),[3,4])
        straight=next(c for c,_ in found if len(c)==4)
        self.assertIn(straight,([0,1,2,3],[3,2,1,0]))


class IslandSixRim(unittest.TestCase):
    """The reported part at a request of 200 (fixtures: tests/fixtures/crease_rows/README.md)."""
    @classmethod
    def setUpClass(cls):
        cls.v,t=read(FIXTURES/'island6-source.obj');cls.t=np.asarray(t,int)
        cls.h=spacing(cls.v,cls.t,200);cls.edges,_=detect(cls.v,cls.t,cls.h,angle=30.,target=200)

    def quads(self,name):
        vertices,faces=read(FIXTURES/name)
        return vertices,np.asarray([f for f in faces if len(f)==4],int)

    def test_the_upper_rim_crease_is_the_representative(self):
        chains,chosen,absorbed=crease_rows.representatives(self.v,self.t,self.edges,self.h)
        self.assertEqual([[c['vertices'][0],c['vertices'][-1]] for c in chains],[[613,1321],[489,1202],[724,1426]])
        self.assertAlmostEqual(chains[0]['length']/self.h,34.31,places=2)
        pairs={tuple(sorted(e)) for e in zip(chains[0]['vertices'][:-1],chains[0]['vertices'][1:])}
        self.assertIn((1308,1309),pairs)     # the witness edge of the reported screenshot lies on the representative
        lookup={tuple(sorted(map(int,e))):i for i,e in enumerate(self.edges)}
        self.assertTrue(absorbed[lookup[(1322,1323)]])   # the lower rim crease, a quarter face below, shares the row

    def test_the_accepted_screenshot_mesh_now_fails_on_its_rim(self):
        vertices,quads=self.quads('island6-200-screenshot-188.obj');self.assertEqual(len(quads),188)
        report=crease_rows.measure(self.v,self.t,self.edges,vertices,quads,self.h)
        rim=report['chains'][0]
        self.assertFalse(report['passed']);self.assertEqual(rim['sourceVertices'],[613,1321])
        self.assertIn('rowP95',rim['failures']);self.assertGreater(rim['values']['rowP95'],.3*self.h)
        whole=measure(self.v,self.t,vertices,quads,200,angle=30.)
        # Every nearest-edge limit that accepted this mesh still passes; only the row requirement rejects it.
        self.assertEqual(whole['failures'],['rowsMissing'])

    def test_the_native_keep_creases_mesh_passes(self):
        vertices,quads=self.quads('island6-200-native-374.obj');self.assertEqual(len(quads),364)
        report=crease_rows.measure(self.v,self.t,self.edges,vertices,quads,self.h)
        self.assertTrue(report['passed'],[c['failures'] for c in report['chains']])
        self.assertLess(report['chains'][0]['values']['rowP95'],.25*self.h)


class LocalFaces(unittest.TestCase):
    """'Add faces where the shape needs them': a face is the local face at each crease edge."""
    def polylines(self,lengths,step=.05):
        """Separate straight crease chains of the given lengths, 3 apart: (points, edges)."""
        points,edges=[],[]
        for row,length in enumerate(lengths):
            count=max(2,int(round(length/step))+1);first=len(points)
            points+=[[x,3.*row,0.] for x in np.linspace(0,length,count)]
            edges+=[[first+i,first+i+1] for i in range(count-1)]
        return np.asarray(points),np.asarray(edges)

    def test_a_chain_gets_the_faces_a_row_needs(self):
        lengths=[8.,1.2,.6,.5,.4]
        points,edges=self.polylines(lengths);sizes=crease_rows.local_sizes(points,edges,1.)
        per_chain=[sizes[(points[edges[:,0],1]==3.*row)] for row in range(len(lengths))]
        for values in per_chain:self.assertEqual(len(set(np.round(values,12))),1)
        # extent / 2 faces, never more than the requested face, never less than a quarter of it
        np.testing.assert_allclose([values[0] for values in per_chain],[1.,.6,.3,.25,.25])
        self.assertEqual(crease_rows.SIZE_FLOOR,.25);self.assertEqual(crease_rows.ROW_MIN_FACES,2.)

    def test_a_chain_too_short_for_a_row_asks_for_the_smallest_face_and_no_row(self):
        # A sheet 6 by 0.4 with a wall along one short side: a crease 0.4 long (0.4 requested faces at a target of 18).
        vertices=np.array([[x,y,0.] for y in (0.,.4) for x in (0.,2.,4.,6.)]+[[6.,y,-1.] for y in (0.,.4)])
        tris=np.array([[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,8,9],[3,9,7]])
        h=spacing(vertices,tris,3);self.assertAlmostEqual(h,.966,places=3)
        edges=np.array([[3,7]]);sizes=crease_rows.local_sizes(vertices,edges,h)
        np.testing.assert_allclose(sizes,[.25])
        chains,chosen,absorbed=crease_rows.representatives(vertices,tris,edges,h,sizes)
        self.assertEqual(chains,[]);self.assertTrue(chosen.all())      # 0.41 faces long: under two faces of a quarter size

    def test_no_face_is_asked_smaller_than_half_the_native_minimum_feature_length(self):
        points,edges=self.polylines([8.,1.2,.6,.5,.4])
        chain=lambda sizes,row:sizes[points[edges[:,0],1]==3.*row][0]
        # S = 0.8 of a requested face (a request of 640): the floor is 0.4, and a chain under S gets no smaller face
        sizes=crease_rows.local_sizes(points,edges,1.,.8)
        np.testing.assert_allclose([chain(sizes,row) for row in range(5)],[1.,.6,.4,.4,.4])
        # S = the requested face (a request of 1,000 or more): the floor is a half
        np.testing.assert_allclose([chain(crease_rows.local_sizes(points,edges,1.,1.),row) for row in range(5)],[1.,.6,.5,.5,.5])
        # S under half a requested face (a request under 250): the quarter-face floor stands
        np.testing.assert_allclose(crease_rows.local_sizes(points,edges,1.,.45),crease_rows.local_sizes(points,edges,1.))

    def test_sizes_follow_the_requested_spacing(self):
        points,edges=self.polylines([1.2])
        np.testing.assert_allclose(crease_rows.local_sizes(points,edges,.5),1.)      # 2.4 requested faces long
        np.testing.assert_allclose(crease_rows.local_sizes(points,edges,2.),.3)      # 0.6 requested faces long
        self.assertEqual(len(crease_rows.local_sizes(points,np.zeros((0,2),int),1.)),0)

    def lid(self):
        v,quads=strip(LID);t=triangles(quads);h=spacing(v,t,TARGET);edges,_=detect(v,t,h,target=TARGET)
        return v,t,h,edges

    def test_the_band_reaches_half_a_local_face(self):
        v,t,h,edges=self.lid()
        chains,chosen,absorbed=crease_rows.representatives(v,t,edges,h,np.ones(len(edges)))
        self.assertEqual((len(chains),int(absorbed.sum())),(1,8))      # requested faces: the creases 0.3 apart are one band
        self.assertEqual(chains[0]['sizes'],[1.]*9)
        chains,chosen,absorbed=crease_rows.representatives(v,t,edges,h,np.full(len(edges),.5))
        self.assertEqual((len(chains),int(absorbed.sum()),int(chosen.sum())),(2,0,16))   # faces half the size: 0.3 is over half a local face
        own,partner=crease_rows.band_edges(v,edges,chains[:1],h,np.full(len(edges),.5))
        self.assertEqual((int(own.sum()),int(partner.sum())),(8,0))
        own,partner=crease_rows.band_edges(v,edges,chains[:1],h,np.ones(len(edges)))
        self.assertEqual((int(own.sum()),int(partner.sum())),(8,8))

    def test_limits_are_in_local_faces(self):
        v,t,h,edges=self.lid()
        # One row 0.2 beside the band (on the top sheet at x = 5.8): 0.2 of a requested face, 0.4 of a half-size face.
        vertices,quads=strip([[0,0],[3,0],[5.8,0],[4.5,-.3]])
        plain=crease_rows.measure(v,t,edges,vertices,quads,h)
        self.assertTrue(plain['passed']);self.assertNotIn('localFaces',plain)
        self.assertAlmostEqual(plain['chains'][0]['values']['rowP95']/h,.2,places=2)
        local=crease_rows.measure(v,t,edges,vertices,quads,h,np.full(len(edges),.5))
        self.assertTrue(local['localFaces']);self.assertEqual(local['required'],2)
        upper=next(c for c in local['chains'] if abs(v[c['sourceVertices'][0]][2])<1e-9)
        self.assertEqual(upper['faceSize'],.5);self.assertFalse(upper['passed'])
        self.assertAlmostEqual(upper['values']['rowP95']/h,.4,places=2)      # the same gap, divided by the local face fraction
        self.assertIn('rowP95',upper['failures'])

    def test_a_chord_across_a_bend_is_not_the_row(self):
        # A quarter circle of radius 0.5 (0.79 long, 0.71 across) and an output with edges round it and a chord across it.
        angles=np.linspace(0,np.pi/2,17);curve=np.c_[.5*np.cos(angles),.5*np.sin(angles),np.zeros(17)]
        vertices=np.array([curve[0],curve[8],curve[-1]]);edges=np.array([[0,1],[1,2],[0,2]])
        self.assertEqual(crease_rows.find_row(vertices,edges,curve,False,1.),[0,2])                         # requested faces: ends only
        self.assertEqual(crease_rows.find_row(vertices,edges,curve,False,1.,np.full(17,.35)),[0,1,2])     # local faces: the middle of each edge counts


class IslandSixLocalFaces(unittest.TestCase):
    """The reported part at a request of 200 with extra faces allowed (fixtures: tests/fixtures/corner_zones/README.md)."""
    @classmethod
    def setUpClass(cls):
        cls.v,t=read(FIXTURES/'island6-source.obj');cls.t=np.asarray(t,int)
        cls.h=spacing(cls.v,cls.t,200);cls.edges,_=detect(cls.v,cls.t,cls.h,angle=30.,target=200)
        cls.sizes=crease_rows.local_sizes(cls.v,cls.edges,cls.h,admission_length(cls.v,cls.t,200))

    def quads(self,name):
        vertices,faces=read(ROOT/'tests/fixtures'/name)
        return vertices,np.asarray([f for f in faces if len(f)==4],int)

    def test_the_feet_get_smaller_faces_and_rows_of_their_own(self):
        self.assertEqual((len(self.edges),int((self.sizes<1).sum())),(283,144))
        self.assertEqual(float(self.sizes.min()),.25)
        chains,chosen,absorbed=crease_rows.representatives(self.v,self.t,self.edges,self.h,self.sizes)
        self.assertEqual(len(chains),18)
        short=[c for c in chains if c['length']<2*self.h]
        self.assertEqual(len(short),14)
        # every short chain lies in one of the two feet (behind y = 0.05) and is two local faces or more in extent
        for chain in short:
            self.assertGreater(self.v[chain['vertices']][:,1].min(),.05)
            self.assertGreaterEqual(chain['length'],crease_rows.ROW_MIN_FACES*self.h*min(chain['sizes'])*(1-1e-9))
        # with requested faces nothing changed: the three chains of two faces or more
        self.assertEqual(len(crease_rows.representatives(self.v,self.t,self.edges,self.h)[0]),3)

    def test_at_300_the_step_end_shorter_than_the_native_minimum_gets_no_row(self):
        h=spacing(self.v,self.t,300);edges,_=detect(self.v,self.t,h,angle=30.,target=300);minimum=admission_length(self.v,self.t,300)
        self.assertAlmostEqual(minimum/h,.548,places=3)
        lookup={tuple(sorted(map(int,e))):i for i,e in enumerate(edges)}
        def rows(sizes):
            return {(c['vertices'][0],c['vertices'][-1]) for c in crease_rows.representatives(self.v,self.t,edges,h,sizes)[0]}
        with_minimum=rows(crease_rows.local_sizes(self.v,edges,h,minimum));quarter=rows(crease_rows.local_sizes(self.v,edges,h))
        # The 0.51-face chains at the end of the step behind each foot are 0.034 long, under S = 0.037.
        self.assertEqual(len(quarter)-len(with_minimum),2)
        self.assertEqual({tuple(sorted(pair)) for pair in quarter-with_minimum},{(1426,1428),(724,726)})
        self.assertAlmostEqual(float(crease_rows.local_sizes(self.v,edges,h,minimum).min()),.274,places=3)

    def test_the_rim_wall_is_still_one_band(self):
        lookup={tuple(sorted(map(int,e))):i for i,e in enumerate(self.edges)}
        chains,chosen,absorbed=crease_rows.representatives(self.v,self.t,self.edges,self.h,self.sizes)
        self.assertTrue(chosen[lookup[(1308,1309)]]);self.assertTrue(absorbed[lookup[(1322,1323)]])
        self.assertEqual(self.sizes[lookup[(1308,1309)]],1.)

    def test_zbrush_has_a_row_on_every_chain_that_needs_one(self):
        vertices,quads=self.quads('guide_rows/island6-200-native-guide-532.obj');self.assertEqual(len(quads),455)
        report=crease_rows.measure(self.v,self.t,self.edges,vertices,quads,self.h,self.sizes)
        self.assertEqual((report['required'],report['realized']),(18,18),[(c['sourceVertices'],c['failures']) for c in report['chains'] if not c['passed']])

    def test_the_earlier_results_have_no_rows_on_the_feet(self):
        for name,realized in (('corner_zones/island6-200-guide-strict-204.obj',11),('corner_zones/island6-200-guide-extra-380-before.obj',13)):
            vertices,quads=self.quads(name)
            report=crease_rows.measure(self.v,self.t,self.edges,vertices,quads,self.h,self.sizes)
            self.assertEqual((report['required'],report['realized']),(18,realized),name)
            # ... while the requested-face check, which asks for three rows, still passes them
            self.assertTrue(crease_rows.measure(self.v,self.t,self.edges,vertices,quads,self.h)['passed'],name)
            whole=measure(self.v,self.t,vertices,quads,200,angle=30.,extra_faces=True)
            self.assertIn('rowsMissing',whole['failures']);self.assertTrue(whole['localFaces'])

    def test_the_extra_faces_result_has_them(self):
        vertices,quads=self.quads('corner_zones/island6-200-guide-extra-faces.obj')
        whole=measure(self.v,self.t,vertices,quads,200,angle=30.,extra_faces=True)
        self.assertTrue(whole['passed'],whole['failures'])
        self.assertEqual((whole['rows']['required'],whole['rows']['realized']),(18,18))


class CorneredChain(unittest.TestCase):
    """Direction compares the same stretch of chain and row (island 6 feet: a 95 degree corner at a plain chain vertex)."""
    curve=np.array([[0.,0,0],[4,0,0],[4,4,0]])

    def path(self,offset=0.):
        # Row vertices every half face along the chain, the corner vertex included.
        points=np.array([[x,0,0] for x in np.arange(0,4,.5)]+[[4,y,0] for y in np.arange(0,4.01,.5)])
        side=np.where(np.arange(len(points))%2,offset,-offset)
        points[:8,1]+=side[:8];points[9:,0]+=side[9:]
        return points

    def test_a_row_on_a_cornered_chain_is_not_charged_the_chain_s_own_corner(self):
        points=self.path()
        values,_=crease_rows.measure_path(points,list(range(len(points))),self.curve,False,1.)
        self.assertLess(values['rowP95'],1e-9);self.assertLess(values['rowTangentP95Degrees'],1e-6)

    def test_a_zigzag_along_a_cornered_chain_still_fails_on_direction(self):
        points=self.path(.2)
        values,_=crease_rows.measure_path(points,list(range(len(points))),self.curve,False,1.)
        self.assertGreater(values['rowTangentP95Degrees'],crease_rows.ROW_TANGENT_DEGREES)

    def test_an_edge_across_the_chain_answers_to_the_chain_s_direction(self):
        # A staircase: steps along the chain joined by edges straight across it.
        points=np.array([[0,-.2,0],[1,-.2,0],[1,.2,0],[2,.2,0],[2,-.2,0],[3,-.2,0],[3,.2,0],[4,.2,0]],float)
        values,_=crease_rows.measure_path(points,list(range(len(points))),np.array([[0.,0,0],[4,0,0]]),False,1.)
        self.assertGreater(values['rowTangentP95Degrees'],crease_rows.ROW_TANGENT_DEGREES)


if __name__=='__main__':unittest.main()
