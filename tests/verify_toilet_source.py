"""Independent original Draco identity, physical coordinates and source topology."""
from pathlib import Path
import json,hashlib,tempfile,subprocess,sys,uuid,shutil,traceback
import numpy as np,trimesh
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'tests/toilet-source';OUT.mkdir(exist_ok=True)
checks=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(value,name):
 checks.append({'name':name,'passed':bool(value)});print(('PASS ' if value else 'FAIL ')+name,flush=True)
 if not value:raise AssertionError(name)
try:
 provenance=json.loads((ROOT/'assets/raw/toilet/preparation.json').read_text());source=ROOT/'assets/raw/toilet/SW_Toilet.closed.web.glb';model=json.loads((ROOT/'assets/models/toilet.json').read_text())
 check(sha(source)==provenance['sourceSha256'],'Archived plain source GLB matches recorded original bytes')
 check(sha(ROOT/'assets/models/toilet.obj')==provenance['preparedObjSha256'] and sha(ROOT/'assets/models/toilet.json')==provenance['preparedMeshJsonSha256'],'Prepared mesh files match their recorded hashes')
 with tempfile.TemporaryDirectory(prefix='verify-white-toilet-') as scratch:
  decoded=Path(scratch)/'mesh.json';r=subprocess.run([r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe','--background','--python',str(ROOT/'scripts/extract_blender_mesh.py'),'--',str(source),str(decoded)],capture_output=True,text=True,check=True)
  raw=json.loads(decoded.read_text());(OUT/'decoder.log').write_text(r.stdout+r.stderr,encoding='utf-8')
 v=np.asarray(model['vertices']);f=np.asarray(model['faces']);original=np.asarray(raw['vertices']);transform=provenance['conversion'];expected=(original-transform['center'])*np.array([-1, -1, 1])*transform['uniformScale']
 check(len(v)==len(original)==12000 and len(f)==len(raw['faces'])==24000,'Original vertex and triangle counts are retained')
 check(float(np.max(np.abs(v-expected)))<1e-11,'Every prepared vertex is the original vertex under the recorded similarity')
 mesh=trimesh.Trimesh(v,f,process=False);check(mesh.is_watertight and mesh.is_winding_consistent and mesh.euler_number==0 and len(mesh.split(only_watertight=False))==1,'Prepared source is one closed consistently wound genus-one component')
 area=np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)
 check(bool(np.all(area>1e-14)),'Local conformity repair leaves no collapsed source triangle')
 check(model['displayColor']=='#f5f5f2' and model['solver']=='surface-quads','Fixture retains white presentation and selects the measured surface solver')
 (OUT/'result.json').write_text(json.dumps({'sourceValidationPassed':True,'checks':checks,'retopologyEvidence':'tests/toilet-retopology/result.json','priorFailureArchive':'tests/toilet-source/solver-attempt','scope':'Original fixture identity and source validation; live generated output is verified separately.'},indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'sourceValidationPassed':True,'checks':len(checks)}),flush=True)
except Exception:
 (OUT/'result.json').write_text(json.dumps({'sourceValidationPassed':False,'checks':checks,'error':traceback.format_exc()},indent=2)+'\n',encoding='utf-8');raise
