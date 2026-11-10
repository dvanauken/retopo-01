"""Crease rows: every band of parallel source creases needs one connected, ordered output edge row."""
from pathlib import Path
import sys
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import crease_rows
from source_features import detect,measure,spacing
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


if __name__=='__main__':unittest.main()
