"""Original Draco mesh identity, physical coordinates, topology and known solver rejection."""
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
 check(model['displayColor']=='#f5f5f2' and model['experimentalRetopology'],'Fixture declares white presentation and its experimental solver status')
 # The model is intentionally retained as a difficult test case, not a fake success.
 job=ROOT/'runs'/uuid.uuid4().hex;job.mkdir();(job/'settings.json').write_text(json.dumps({'meshId':'toilet','target':1800,'guideMode':2,'sourceSha256':model['sourceSha256']}));(job/'curves.json').write_text(json.dumps({'coordinateFrame':'source','curves':model['presets'][0]['curves']}))
 result=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'worker.py'),'--job',str(job)],capture_output=True,text=True,timeout=180)
 report=json.loads((job/'report.json').read_text());check(result.returncode!=0 and not report['passed'] and not (job/'mesh.json').exists() and not (job/'output.obj').exists(),'Known general-solver failure produces no qualified result or successful export')
 check(report['technicalMessage']=='Degenerate source normal policy' and 'mesh conditioning' in report['message'],'Failure identifies solver conditioning rather than blaming the valid source mesh')
 failure=OUT/'solver-attempt';failure.mkdir(exist_ok=True)
 for name in ['settings.json','curves.json','report.json']:shutil.copyfile(job/name,failure/name)
 (failure/'worker.log').write_text(result.stdout+result.stderr,encoding='utf-8')
 (OUT/'result.json').write_text(json.dumps({'sourceValidationPassed':True,'checks':checks,'qualifiedRetopologyProduced':False,'solverAttempt':job.name,'solverFailure':report['message'],'scope':'Original fixture import and known-failure validation only; not a passing toilet remesh.'},indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'sourceValidationPassed':True,'checks':len(checks),'qualifiedRetopologyProduced':False}),flush=True)
except Exception:
 (OUT/'result.json').write_text(json.dumps({'sourceValidationPassed':False,'checks':checks,'error':traceback.format_exc()},indent=2)+'\n',encoding='utf-8');raise
