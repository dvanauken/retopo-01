from pathlib import Path
import json,sys,unittest
import numpy as np,trimesh
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mesh_parts import extract,plane_split,indices

class Parts(unittest.TestCase):
    def test_plane_conserves_volume_coordinates_and_closed_parts(self):
        mesh=trimesh.creation.box();model=dict(vertices=mesh.vertices.tolist(),faces=mesh.faces.tolist())
        a,b=plane_split(model,2,.1)
        for part in (a,b):
            m=trimesh.Trimesh(part['vertices'],part['faces'],process=False)
            self.assertTrue(m.is_watertight and m.is_winding_consistent);self.assertGreater(part['repair']['capFaces'],0)
        self.assertAlmostEqual(sum(trimesh.Trimesh(p['vertices'],p['faces'],process=False).volume for p in (a,b)),1)
        seam=lambda p:set(tuple(np.round(v,12)) for v in p['vertices'] if abs(v[2]-.1)<1e-9)
        self.assertEqual(seam(a),seam(b))

    def test_invalid_regions_reject(self):
        for value in ([],[True],[0,0],[-1],[3],[.5]):
            with self.assertRaises(ValueError):indices(value,3)
        mesh=trimesh.creation.box();model=dict(vertices=mesh.vertices.tolist(),faces=mesh.faces.tolist())
        with self.assertRaises(ValueError):plane_split(model,2,2)

    def test_toilet_handle_exclusion_and_lid_split(self):
        model=json.loads((ROOT/'assets/models/toilet.json').read_text());v=np.array(model['vertices']);f=np.array(model['faces']);c=v[f].mean(1)
        selected=(c[:,0]>.55)&(c[:,2]>.48)&(c[:,2]<.74)&(c[:,1]>.69)&(c[:,1]<.84)
        handle=extract(v,f,np.flatnonzero(selected).tolist(),open_region=True)
        body=extract(v,f,np.flatnonzero(~selected).tolist())
        self.assertFalse(handle['repair']['closed']);self.assertTrue(body['repair']['closed'])
        self.assertEqual(len(handle['faces']),273);self.assertGreater(body['repair']['capFaces'],0)
        np.testing.assert_array_equal(np.array(body['vertices'])[:len(set(f[~selected].flat))],v[np.unique(f[~selected])])
        a,b=plane_split(body,2,.82)
        self.assertTrue(a['repair']['closed'] and b['repair']['closed'])
        self.assertLess(len(a['faces']),len(b['faces']))

if __name__=='__main__':unittest.main()
