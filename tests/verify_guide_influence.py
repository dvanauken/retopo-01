"""Exact reported guide -> real worker -> independent surface/edge measurements."""
from pathlib import Path
import hashlib,json,subprocess,sys,uuid,shutil,traceback
import numpy as np
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'tests/guide-influence';OUT.mkdir(exist_ok=True)
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj,topology,guide_alignment
from measure_polygon_geometry import measure
from structured_prism import detect,_radius
checks=[];jobs=[]
def check(value,name):
 checks.append({'name':name,'passed':bool(value)});print(('PASS ' if value else 'FAIL ')+name,flush=True)
 if not value:raise AssertionError(name)
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(name,curves,negative=False):
 job=ROOT/'runs'/uuid.uuid4().hex;job.mkdir();jobs.append(job.name)
 (job/'settings.json').write_bytes((OUT/'original/settings.json').read_bytes());(job/'curves.json').write_text(json.dumps({'coordinateFrame':'source','curves':curves}))
 if negative:
  code="import sys,worker;original=worker.construct_structured\ndef replaced(*a,**k):\n v,f,m=original(*a,**k);m['guidePaths']=[];return v,f,m\nworker.construct_structured=replaced;sys.argv=['worker.py','--job',sys.argv[1]];raise SystemExit(worker.main())"
  args=[sys.executable,'-X','utf8','-c',code,str(job)]
 else:args=[sys.executable,'-X','utf8',str(ROOT/'worker.py'),'--job',str(job)]
 result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=180)
 destination=OUT/name;destination.mkdir(exist_ok=True)
 for file in ['curves.json','settings.json','report.json','mesh.json','output.obj','engine-provenance.json','quality.json','failed-mesh.json']:
  if (job/file).exists():shutil.copyfile(job/file,destination/file)
 (destination/'worker.log').write_text(result.stdout+result.stderr,encoding='utf-8')
 return job,result.returncode
try:
 original=read(OUT/'original/mesh.json');curves=read(OUT/'original/curves.json')['curves'];old=original['guideAlignment'][0]
 check(not original['guidePaths'] and old['p95Distance']>.06,'Original reported Good result had no measured path and weak guide fit')
 baseline,code=run('baseline',[]);check(code==0,'Unguided baseline completes through the actual worker')
 guided,code=run('repaired',curves);check(code==0,'Exact reported curve completes through the repaired worker')
 mesh=read(guided/'mesh.json');check(read(guided/'curves.json')['curves']==curves,'Submitted user positions are retained exactly')
 check(len(mesh['guidePaths'])==1 and mesh['guidePaths'][0]['curve']==0,'Every submitted guide has a measured output-edge path')
 vertices,faces=read_obj(guided/'output.obj');stats,_,edges=topology(vertices,faces);edge_set={tuple(sorted(e)) for e in edges}
 path=mesh['guidePaths'][0];ids=path['vertexIds'];check(all(tuple(sorted((a,b))) in edge_set for a,b in zip(ids,ids[1:])),'Tracked guide path consists of actual connected exported edges')
 independent=guide_alignment(vertices,edges,np.asarray(curves[0]));check(independent['p95Distance']<.025 and independent['p95Distance']<old['p95Distance']/3,'Independent guide distance improves by more than three times')
 check(independent['p95UnsignedTangentAngleDegrees']<20 and independent['p95UnsignedTangentAngleDegrees']<old['p95UnsignedTangentAngleDegrees']/3,'Independent edge direction follows the guide instead of crossing it')
 check(stats['quadFraction']==1 and stats['boundaryEdges']==0 and stats['nonmanifoldEdges']==0 and stats['eulerCharacteristic']==0,'Repaired output remains all-quads, closed and genus one')
 check(sha(guided/'output.obj')!=sha(baseline/'output.obj'),'Guidance changes the actual exported geometry from the same-target baseline')
 surface=measure(ROOT/'assets/models/hexagon.obj',guided/'output.obj',curves,True)
 check(max(surface['sourceToOutput']['sampledMax'],surface['outputToSource']['sampledMax'])<2e-6,'Independent sampling confirms the original physical surface is retained')
 # A genuinely radial guide remains a spoke and also has a measured open chain.
 source_v,source_f=read_obj(ROOT/'assets/models/hexagon.obj');d=detect(source_v,source_f);angle=.9;inner=float(_radius(d['inner'],np.array([angle]))[0]);outer=float(_radius(d['outer'],np.array([angle]))[0]);radial=[]
 for t in np.linspace(.1,.9,25):
  r=inner+t*(outer-inner);radial.append((d['base']+r*np.cos(angle)*d['u']+r*np.sin(angle)*d['v']+d['height']*d['normal']).tolist())
 spoke,code=run('radial-spoke',[radial]);check(code==0,'True radial-spoke guidance still completes through the worker')
 check(read(spoke/'mesh.json')['guidePaths'] and not read(spoke/'mesh.json')['guidePaths'][0]['closedCycle'],'Radial guidance has an explicit measured open output-edge chain')
 negative,code=run('missing-path-control',curves,True);check(code!=0 and not (negative/'mesh.json').exists() and 'No measured output edge path' in read(negative/'report.json')['message'],'A solver result with missing guide-path evidence is rejected before successful export')
 result={'passed':True,'checks':checks,'jobs':jobs,'before':old,'after':independent,'trackedPath':path,'surface':surface,'sourceHashes':{name:sha(ROOT/name) for name in ['worker.py','structured_prism.py','quad_quality.py']}}
 (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({'passed':True,'checks':len(checks),'p95Before':old['p95Distance'],'p95After':independent['p95Distance']}),flush=True)
except Exception:
 (OUT/'result.json').write_text(json.dumps({'passed':False,'checks':checks,'jobs':jobs,'error':traceback.format_exc()},indent=2)+'\n',encoding='utf-8');raise
