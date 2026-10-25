"""Compare the explicit numerical module with independently qualified artifacts."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import argparse,hashlib,importlib.util,json,sys,time,traceback
from pathlib import Path
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
import surface_guide_refine as fitter
from measure_geometry import read_obj
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);parser.add_argument('--module',type=Path);args=parser.parse_args()
if args.module:
 spec=importlib.util.spec_from_file_location('tested_sampled_fitter',args.module.resolve())
 fitter=importlib.util.module_from_spec(spec);sys.modules[spec.name]=fitter;spec.loader.exec_module(fitter)
if not args.label.replace('-','').isalnum():raise ValueError('Use a plain label')
OUT=ROOT/'tests/surface-guide-refine'/args.label;OUT.mkdir(parents=True,exist_ok=False)
(OUT/'executed-test.py').write_bytes(Path(__file__).read_bytes())
(OUT/'executed-fitter.py').write_bytes(Path(fitter.__file__).read_bytes())
sv,sf=read_obj(ROOT/'assets/models/toilet.obj');source=trimesh.Trimesh(sv,sf,process=False);spacing=np.sqrt(source.area/1800)
folder=ROOT/'tests/toilet-sampled-paths/captured-seed2-401';raw=json.loads((folder/'layout.json').read_text());faces=np.asarray(raw['faces']);edges=cq._edges(faces)
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('surface_guide_refine.py','curved_quad.py','assets/models/toilet.obj','tests/verify_surface_guide_refine.py')}
hashes[str(Path(fitter.__file__).resolve())]=hashlib.sha256(Path(fitter.__file__).read_bytes()).hexdigest()
checks=[];errors=[];started=time.monotonic()
def check(passed,name,**details):
 checks.append(dict(passed=bool(passed),name=name,**details));print(('PASS ' if passed else 'FAIL ')+name,flush=True)
def compare(actual,path,name):
 expected=json.loads(path.read_text());expected_positions=np.asarray(expected['vertices'])
 check(np.array_equal(actual,expected_positions) and np.array_equal(faces,expected['faces']),name,maximumCoordinateDifference=float(np.max(np.abs(actual-expected_positions))),referenceFile=str(path.relative_to(ROOT)),referenceSha256=hashlib.sha256(path.read_bytes()).hexdigest())
def save(complete):
 (OUT/'result.json').write_text(json.dumps(dict(complete=complete,passed=complete and not errors and all(c['passed'] for c in checks),checks=checks,errors=errors,sourceHashes=hashes,
  implementationUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),elapsedSeconds=time.monotonic()-started,
  scope='Actual fitting calls through an explicit geometry/curve/target module, compared coordinate-for-coordinate with retained numerical candidates whose final exports pass independent audits. Includes global and local fitting, fixed input arrays, and untouched vertices outside local patches. This is a refactoring regression; it does not by itself qualify other guide inputs or integrate the module into the production worker.'),indent=2)+'\n',newline='\n')
try:
 for name in ('bowl-only-1800','two-guides-short-1800'):
  curve_file=ROOT/'tests/toilet-stress'/name/'curves.json';curves=json.loads(curve_file.read_text())['curves']
  positions=np.asarray(raw['vertices']);guides=fitter.prepare(positions,edges,curves,spacing)
  for iteration in range(2):
   original=positions.copy();input_positions=positions;frozen_faces=faces.copy();positions,metadata=fitter.refine(source,positions,faces,edges,guides,1800)
   check(np.array_equal(input_positions,original),name+' leaves its input positions unchanged in global pass '+str(iteration))
   check(np.array_equal(faces,frozen_faces),name+' preserves face connectivity in global pass '+str(iteration))
   compare(positions,folder/f'{name}-{iteration}.json',name+' global pass '+str(iteration)+' exactly reproduces measured candidate')
   check(np.array_equal(np.asarray(raw['vertices']) if iteration==0 else np.asarray(json.loads((folder/f'{name}-0.json').read_text())['vertices']),original),name+' input state is the expected prior pass '+str(iteration))
   save(False)
  if name=='two-guides-short-1800':
   repair_folder=ROOT/'tests/toilet-witness-repair/short-seed2-local';repair=json.loads((repair_folder/'result.json').read_text())
   for step in repair['steps']:
    original=positions.copy();patch=set(step['patchVertices']);witness_source=trimesh.proximity.closest_point(source,np.asarray(step['witnesses']))[0]
    proposal,metadata=fitter.refine(source,positions,faces,edges,guides,1800,patch_vertices=patch,witness_source=witness_source)
    check(np.array_equal(positions,original),'Local pass '+str(step['step'])+' leaves its input positions unchanged')
    compare(proposal,repair_folder/f"{name}-{step['trials'][0]}.json",'Local pass '+str(step['step'])+' exactly reproduces full proposal')
    chosen=repair['cases'][0]['attempts'][step['continuedCandidate']];positions=positions+chosen['alpha']*(proposal-positions)
    outside=np.array(sorted(set(range(len(positions)))-patch),dtype=int)
    check(np.array_equal(positions[outside],original[outside]),'Local pass '+str(step['step'])+' keeps every vertex outside its patch fixed')
    compare(positions,repair_folder/f"{name}-{step['continuedCandidate']}.json",'Local pass '+str(step['step'])+' exactly reproduces accepted half step')
    save(False)
   (OUT/'short-final.json').write_text(json.dumps(dict(vertices=positions.tolist(),faces=faces.tolist())))
 check(all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),'Numerical source remains unchanged throughout the comparison')
except Exception:
 errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:save(True)
raise SystemExit(1 if errors or any(not c['passed'] for c in checks) else 0)
