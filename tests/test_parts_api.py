from pathlib import Path
import io,json,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import server
from mesh_parts import split,load_part

class PartsAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=server.MESHES['toilet'];cls.parts=split(spec,dict(sourceSha256=spec['sourceSha256'],plane=dict(axis=2,value=.82)))
    def request(self,data,path='/api/remesh'):
        h=server.Handler.__new__(server.Handler);h.path=path;body=json.dumps(data).encode();h.headers={'Content-Type':'application/json','Content-Length':str(len(body))};h.rfile=io.BytesIO(body);h.respond=lambda data,status=200:(data,status)
        return h.do_POST()
    def test_part_source_identity_and_replay_conflict(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as tmp:
            root=Path(tmp);(root/'runs').mkdir()
            with patch.object(server,'ROOT',root),patch.dict(server.JOBS,{},clear=True),patch.dict(server.REQUESTS,{},clear=True),patch.object(server.QUEUE,'submit') as submit:
                packet=dict(meshId='toilet',target=800,curves=[],guideMode=2,requestId='b'*32,partSource=self.parts['selected']['partSource'])
                result,status=self.request(packet);self.assertEqual(status,202);settings=json.loads((root/'runs'/result['id']/'settings.json').read_text())
                self.assertEqual(settings['sourceSha256'],self.parts['selected']['sourceSha256']);self.assertEqual(settings['originalSourceSha256'],server.MESHES['toilet']['sourceSha256'])
                self.assertEqual(self.request(packet)[0]['id'],result['id']);self.assertEqual(submit.call_count,1)
                packet['partSource']=self.parts['remainder']['partSource'];self.assertEqual(self.request(packet)[1],409)
    def test_invalid_or_foreign_part_does_not_queue(self):
        with patch.object(server.QUEUE,'submit') as submit:
            for value in ('../server.py',None,'',True,'0'*64):
                self.assertEqual(self.request(dict(meshId='toilet',target=800,curves=[],partSource=value))[1],400)
            self.assertEqual(self.request(dict(meshId='hexagon',target=800,curves=[],partSource=self.parts['selected']['partSource']))[1],400)
            submit.assert_not_called()
    def test_original_assembly_requires_a_part_but_original_open_part_is_admitted(self):
        with patch.object(server.QUEUE,'submit') as submit:
            self.assertEqual(self.request(dict(meshId='toilet-skp',target=500,curves=[]))[1],400)
            submit.assert_not_called()
        original=json.loads((ROOT/'assets/models/toilet-skp.json').read_text())
        node=next(n for n in original['initialParts'] if n['id']=='skp-2')
        model,_=load_part(node['partSource']);self.assertTrue(model['canRemesh']);self.assertEqual(model['solver'],'open-surface-quads')
        with tempfile.TemporaryDirectory(dir=ROOT/'runs') as tmp:
            root=Path(tmp);(root/'runs').mkdir()
            with patch.object(server,'ROOT',root),patch.dict(server.JOBS,{},clear=True),patch.dict(server.REQUESTS,{},clear=True),patch.object(server.QUEUE,'submit') as submit:
                packet=dict(meshId='toilet-skp',target=500,curves=[],partSource=node['partSource'])
                result,status=self.request(packet);self.assertEqual(status,202);submit.assert_called_once()
    def test_stale_source_bad_selection_and_parent_reject(self):
        base=dict(meshId='toilet',sourceSha256=server.MESHES['toilet']['sourceSha256'],selectedFaces=[0])
        for changes in (dict(sourceSha256='wrong'),dict(partSource=''),dict(selectedFaces=[True]),dict(plane=dict(axis=True,value=.82))):
            self.assertEqual(self.request(dict(base,**changes),'/api/parts/split')[1],400)

if __name__=='__main__':unittest.main()
