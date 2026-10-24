"""Original rejected user input -> actual worker -> independently measured quads."""
from pathlib import Path
import sys,json,time,socket,subprocess,urllib.request,hashlib,traceback
import numpy as np,trimesh
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'tests/quality-repair'/(sys.argv[1] if len(sys.argv)>1 else 'validation-'+str(time.time_ns()));OUT.mkdir(exist_ok=False)
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'engine/targets/zbrush/clone'));sys.path.insert(0,str(ROOT/'engine/targets/zbrush/experiments/python'))
from quad_quality import measure as quad_quality
from measure_polygon_geometry import measure
from retopo import read_obj,write_obj
from structured_prism import construct,detect
checks=[];cases=[];jobs=[]
def check(value,name):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
def write(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def get(path):
 with urllib.request.urlopen(URL+path,timeout=15) as r:return json.load(r)
def post(path,data):
 req=urllib.request.Request(URL+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'},method='POST')
 with urllib.request.urlopen(req,timeout=15) as r:return json.load(r)
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
URL=f'http://127.0.0.1:{port}';log=(OUT/'server.log').open('w',encoding='utf-8');server=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'server.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
 for _ in range(100):
  try:get('/api/health');break
  except Exception:time.sleep(.1)
 original=ROOT/'tests/quality-repair/original/user-failed-run';old=json.loads((original/'mesh.json').read_text());user=json.loads((original/'curves.json').read_text())['curves'];spec=json.loads((ROOT/'assets/models/hexagon.json').read_text());old_quality=quad_quality(old['vertices'],old['faces'],450);check(not old_quality['passed'],'User-rejected 620-face output fails the new quality gate');write(OUT/'old-user-quality.json',old_quality)
 for name,curves,target in [('baseline',[],600),('user',user,450),('low-density',user,150),('high-density',user,1200),('loop',spec['presets'][0]['curves'],600),('crossings',spec['presets'][1]['curves'],600)]:
  job=post('/api/remesh',{'meshId':'hexagon','curves':curves,'target':target,'guideMode':2});jobs.append(job['id']);start=time.monotonic()
  while True:
   status=get('/api/jobs/'+job['id'])
   if status['state'] in ('complete','failed','cancelled'):break
   if time.monotonic()-start>180:raise TimeoutError(name+' exceeded 180 seconds')
   time.sleep(.3)
  folder=ROOT/'runs'/job['id'];report=json.loads((folder/'report.json').read_text());check(status['state']=='complete' and report['passed'] and report['qualityPassed'],name+' actually completes through the worker quality gate')
  mesh=json.loads((folder/'mesh.json').read_text());check(json.loads((folder/'curves.json').read_text())['curves']==curves,name+' uses the exact requested guide coordinates')
  check(mesh['backend']=='engineering-structured-prismatic-annulus',name+' uses direct structured quads rather than triangle pairing')
  checked=measure(ROOT/'assets/models/hexagon.obj',folder/'output.obj',curves,True);write(OUT/(name+'-measurements.json'),checked)
  check(max(checked['sourceToOutput']['sampledMax'],checked['outputToSource']['sampledMax'])<2e-6,name+' retains the measured physical surface')
  p,f=read_obj(folder/'output.obj');q=quad_quality(p,f,target);check(q['passed'] and q['irregularVertices']==0,name+' exported quads pass shape, density and continuous-grid valence checks')
  check(mesh['stats']['eulerCharacteristic']==0 and mesh['stats']['boundaryEdges']==0 and mesh['stats']['nonmanifoldEdges']==0 and not mesh['vertexLinks']['nonmanifoldVertices'],name+' preserves the closed connected through-hole')
  edges={tuple(sorted((int(a),int(b)))) for row in f for a,b in zip(row,row[1:]+row[:1])}
  for path in mesh['guidePaths']:
   ids=path['vertexIds'];check(ids[0]==ids[-1] and len(set(ids[:-1]))==len(ids)-1 and all(tuple(sorted((a,b))) in edges for a,b in zip(ids[:-1],ids[1:])),name+' guide path is a real ordered continuous cycle of output edges')
  if name=='user':
   check(q['minimumAngleDegrees']>50 and q['edgeRatioMax']<3.5 and q['scaledJacobianMin']>.75,'The actual rejected stroke receives a material shape improvement')
   check(q['targetRelativeError']<.1 and len(f)<620,'User target 450 stays within 10 percent instead of overshooting by 38 percent')
   check(max(path['p95Distance'] for path in mesh['guidePaths'])<.025,'The coherent guide cycle also fits the actual user stroke')
  cases.append({'name':name,'job':job['id'],'target':target,'faces':len(f),'quality':q,'guidePaths':mesh['guidePaths'],'outputSha256':sha(folder/'output.obj'),'sourceSha256':sha(folder/'source.obj'),'settingsSha256':sha(folder/'settings.json'),'curvesSha256':sha(folder/'curves.json')});print(json.dumps({'name':name,'job':job['id'],'faces':len(f),'qualityPassed':q['passed']}),flush=True)
 # A separately generated, transformed octagonal annulus checks recognition of a
 # geometry class rather than stored output or the hexagon source identifier.
 n=8;vertices=[]
 for z in [-.7,.7]:
  for radius in [.42,1.]:vertices.extend([[radius*np.cos(i*2*np.pi/n),radius*np.sin(i*2*np.pi/n),z] for i in range(n)])
 faces=[]
 for i in range(n):
  k=(i+1)%n;faces.extend([[i,k,n+k,n+i],[2*n+i,3*n+i,3*n+k,2*n+k],[n+i,n+k,3*n+k,3*n+i],[i,2*n+i,2*n+k,k]])
 tri=[[row[0],row[j],row[j+1]] for row in faces for j in range(1,3)];axis=np.array([1.,2.,3.]);axis/=np.linalg.norm(axis);angle=.71;K=np.array([[0,-axis[2],axis[1]],[axis[2],0,-axis[0]],[-axis[1],axis[0],0]]);rotation=np.eye(3)+np.sin(angle)*K+(1-np.cos(angle))*K@K;translation=np.array([3.,-2.,.5]);v=np.array(vertices)@rotation.T*1.7+translation
 curve=np.array([[.67*np.cos(i*2*np.pi/96),.67*np.sin(i*2*np.pi/96),.7] for i in range(97)])@rotation.T*1.7+translation
 p,f,meta=construct(v,np.array(tri),[curve],target=320);write_obj(OUT/'octagonal-source.obj',v,tri);write_obj(OUT/'octagonal-output.obj',p,f);write(OUT/'octagonal-guides.json',{'curves':[curve.tolist()]});measured=measure(OUT/'octagonal-source.obj',OUT/'octagonal-output.obj',[curve],True);write(OUT/'octagonal-measurements.json',measured)
 check(meta['quadQuality']['passed'] and max(measured['sourceToOutput']['sampledMax'],measured['outputToSource']['sampledMax'])<2e-6,'A rotated, scaled, translated octagonal annulus is actually reconstructed from new source geometry')
 result={'passed':True,'checks':checks,'cases':cases,'genericFixture':{'faces':len(f),'quality':meta['quadQuality'],'sourceSha256':sha(OUT/'octagonal-source.obj'),'outputSha256':sha(OUT/'octagonal-output.obj')},'sourceHashes':{name:sha(ROOT/name) for name in ['worker.py','structured_prism.py','quad_quality.py']},'scope':'Actual worker construction from unchanged original source and user guides, independent polygon rereading and a new transformed geometry-class fixture. Engineering class-specific layout, not native/general retopology recovery.'};write(OUT/'result.json',result);print(json.dumps({'passed':True,'checks':len(checks),'cases':len(cases)+1,'output':str(OUT)}),flush=True)
except Exception:
 write(OUT/'result.json',{'passed':False,'checks':checks,'cases':cases,'jobs':jobs,'error':traceback.format_exc()});raise
finally:
 server.terminate();server.wait(timeout=20);log.close()
