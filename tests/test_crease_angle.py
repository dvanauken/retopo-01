from pathlib import Path
import json, sys, threading, unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone')]
import source_features
from source_features import detect,measure,use_crease_angle
from crease_angle import DEFAULT, check
import server


def tent(bend_degrees):
    """Two long flat panels meeting at a ridge; the surface turns by bend_degrees there."""
    t=np.radians(bend_degrees)
    v=np.array([[0,0,0],[0,10,0],[1,0,0],[1,10,0],[1+np.cos(t),0,np.sin(t)],[1+np.cos(t),10,np.sin(t)]],float)
    return v,np.array([[0,2,1],[1,2,3],[2,4,3],[3,4,5]])


class CreaseAngle(unittest.TestCase):
    def tearDown(self):use_crease_angle(DEFAULT)

    def test_only_finite_degrees_in_range_are_accepted(self):
        self.assertEqual(check(45),45.);self.assertEqual(check(10),10.);self.assertEqual(check(120),120.)
        for bad in (9.9,120.1,float('nan'),float('inf'),True,'45',None):
            with self.subTest(bad=bad):self.assertRaises(ValueError,check,bad)

    def test_the_angle_decides_which_bends_are_creases(self):
        v,f=tent(50)
        edges,report=detect(v,f,1.,angle=45)
        self.assertEqual(report['angleDegrees'],45.);self.assertEqual(len(edges),1);self.assertEqual(report['chains'],1)
        edges,report=detect(v,f,1.,angle=60)
        self.assertEqual(len(edges),0);self.assertEqual(report['chains'],0);self.assertEqual(report['resolvedEdges'],0)

    def test_process_setting_reaches_detection_and_measurement(self):
        v,f=tent(50);q=np.array([[0,2,3,1],[2,4,5,3]])
        self.assertEqual(len(detect(v,f,1.)[0]),1)
        use_crease_angle(60)
        edges,report=detect(v,f,1.)
        self.assertEqual(len(edges),0);self.assertEqual(report['angleDegrees'],60.)
        result=measure(v,f,v,q,2)
        self.assertEqual(result['detection']['angleDegrees'],60.);self.assertIn('60-degree',result['scope'])
        self.assertEqual(measure(v,f,v,q,2,angle=45)['sourceFeatureEdges'],1)
        self.assertRaises(ValueError,use_crease_angle,5)
        self.assertEqual(source_features._angle,60.)

    def test_fragments_smaller_than_the_spacing_are_still_counted_apart(self):
        v,f=tent(50)
        edges,report=detect(v,f,100.,angle=45)
        self.assertEqual(len(edges),0);self.assertEqual(report['fragmentEdges'],1);self.assertEqual(report['chains'],0)


class CreaseApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=server.LocalHTTPServer(('127.0.0.1',0),server.Handler)
        cls.url=f'http://127.0.0.1:{cls.http.server_port}'
        threading.Thread(target=cls.http.serve_forever,daemon=True).start()

    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close()

    def get(self,path):
        try:
            with urlopen(self.url+path) as response:return response.status,json.load(response)
        except HTTPError as error:return error.code,json.load(error)

    def test_creases_endpoint_returns_the_edges_the_solver_would_use(self):
        status,loose=self.get('/api/mesh/hexagon/creases?angle=45&target=500')
        self.assertEqual(status,200);self.assertEqual(loose['angleDegrees'],45.);self.assertEqual(loose['target'],500)
        self.assertGreater(loose['resolvedEdges'],0);self.assertEqual(len(loose['edges']),loose['resolvedEdges'])
        mesh=json.loads((ROOT/'assets/models/hexagon.json').read_text(encoding='utf-8'))
        self.assertTrue(all(0<=i<len(mesh['vertices']) and 0<=j<len(mesh['vertices']) for i,j in loose['edges']))
        status,strict=self.get('/api/mesh/hexagon/creases?angle=120&target=500')
        self.assertEqual(status,200);self.assertLess(strict['resolvedEdges'],loose['resolvedEdges'])

    def test_creases_endpoint_rejects_unusable_requests(self):
        for path,message in (('/api/mesh/hexagon/creases?angle=5&target=500','Crease angle'),('/api/mesh/hexagon/creases?angle=abc&target=500','Crease angle'),
                             ('/api/mesh/hexagon/creases?angle=45&target=20','Target'),('/api/mesh/hexagon/creases?angle=45','Target')):
            with self.subTest(path=path):
                status,body=self.get(path);self.assertEqual(status,400);self.assertIn(message,body['error'])
        self.assertEqual(self.get('/api/mesh/nothing/creases?angle=45&target=500')[0],404)
        self.assertEqual(self.get('/api/parts/'+'0'*64+'/creases?angle=45&target=500')[0],400)

    def test_generation_rejects_a_bad_angle_before_creating_a_job(self):
        before=set((ROOT/'runs').iterdir())
        for angle in (5,121,True,'45'):
            with self.subTest(angle=angle):
                request=Request(self.url+'/api/remesh',json.dumps(dict(meshId='hexagon',target=500,curves=[],guideMode=2,creaseAngle=angle)).encode(),{'Content-Type':'application/json'})
                with self.assertRaises(HTTPError) as caught:urlopen(request)
                self.assertEqual(caught.exception.code,400);self.assertIn('Crease angle',json.load(caught.exception)['error'])
        self.assertEqual(set((ROOT/'runs').iterdir()),before)


if __name__=='__main__':unittest.main()
