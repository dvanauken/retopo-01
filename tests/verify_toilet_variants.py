"""Fresh finite density, repeatability, guide-equivalence and perturbation matrix.

Equivalent traces need not produce identical connectivity, but each should meet
the same acceptance requirements. Safe rejection is recorded as an unsolved
case. All actual submitted coordinates and worker diagnostics are retained.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
import urllib.error
import numpy as np
import psutil
import trimesh

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(); parser.add_argument('--label',default='current'); parser.add_argument('--cases',nargs='+'); args=parser.parse_args()
OUT=ROOT/'tests/toilet-variants'/args.label; OUT.mkdir(parents=True,exist_ok=True)
FILES=('app.js','server.py','worker.py','curved_quad.py','surface_intersections.py','surface_distance.py','quad_quality.py','assets/models/toilet.obj','tests/verify_toilet_variants.py')
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}
def saved(name): return json.loads((ROOT/'tests/toilet-stress'/name/'curves.json').read_text())['curves']
circle=saved('browser-lid-circle')[0]; lid=saved('lid-only-1800')[0]; combined=saved('two-guides-long-1800')
unique=circle[:-1]; offset=len(unique)//3; cyclic=unique[offset:]+unique[:offset]; cyclic.append(cyclic[0])
dense=[]
for a,b in zip(circle[:-1],circle[1:]): dense.extend([a,((np.asarray(a)+b)*.5).tolist()])
dense.append(circle[-1])
source=trimesh.load(ROOT/'assets/models/toilet.obj',process=False,force='mesh')
rng=np.random.default_rng(20261024); moved=np.asarray(unique)+rng.normal(0,.001,(len(unique),3))
jitter=trimesh.proximity.closest_point(source,moved)[0].tolist(); jitter.append(jitter[0])
specs=[('circle-repeat',1800,[circle]),('circle-reversed',1800,[circle[::-1]]),('circle-cyclic-start',1800,[cyclic]),
       ('circle-densified',1800,[dense]),('lid-reversed',1800,[lid[::-1]]),('combined-reordered',1800,combined[::-1]),
       ('circle-small-perturbation',1800,[jitter])]+[(f'unguided-{n}',n,[]) for n in (150,600,1200,1799)]
if args.cases: specs=[s for s in specs if s[0] in args.cases]
if not specs: raise ValueError('No requested matrix cases')
with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'; checks,cases,errors,jobs=[],[],[],[]
def http(path,body=None):
    req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=20))
def check(value,name):
    checks.append(dict(name=name,passed=bool(value))); print(('PASS ' if value else 'FAIL ')+name,flush=True)
def report(complete=False):
    result=dict(complete=complete,generationPassed=complete and bool(cases) and all(c['state']=='complete' for c in cases),
        safetyChecksPassed=all(c['passed'] for c in checks) and not errors,cases=cases,checks=checks,errors=errors,sourceHashes=hashes,
        scope='Fresh Blender layouts and actual worker requests. Tests finite equivalent representations, deterministic repeat, 0.001-unit Gaussian perturbation projected to source, and supported density partitions. Failed geometry remains unsolved; does not prove all continuous inputs.')
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')

log=(OUT/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-X','utf8','server.py','--port',str(port)],cwd=ROOT,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
    for _ in range(100):
        try: http('/api/health'); break
        except OSError: time.sleep(.1)
    for name,target,curves in specs:
        payload=dict(meshId='toilet',target=target,guideMode=2,curves=curves)
        dest=OUT/name; dest.mkdir(exist_ok=True); (dest/'request.json').write_text(json.dumps(payload))
        submitted=http('/api/remesh',payload); jobs.append(submitted['id']); started=time.monotonic(); stage=None
        while True:
            status=http('/api/jobs/'+submitted['id'])
            if status.get('stage')!=stage:
                stage=status.get('stage'); print(name,status['state'],stage,flush=True)
            if status['state'] in ('complete','failed','cancelled'): break
            if time.monotonic()-started>650: raise TimeoutError(submitted['id'])
            time.sleep(.5)
        folder=ROOT/'runs'/submitted['id']
        for filename in ('curves.json','settings.json','report.json','execution.json','surface-solver.json','surface-solver-failure.json','output.obj','mesh.json','worker.log'):
            if (folder/filename).exists(): shutil.copyfile(folder/filename,dest/filename)
        item=dict(name=name,target=target,job=submitted['id'],state=status['state'],message=status.get('error'),elapsedSeconds=time.monotonic()-started)
        if status['state']=='complete':
            mesh=http('/api/jobs/'+submitted['id']+'/mesh.json')
            check(mesh['surfaceValidation']['passed'] and set(mesh['surfaceValidation']['wholeSurfaceDiagonals'])=={'02','13'} and mesh['intersectionValidation']['passed'],name+': accepted geometry includes both diagonal bounds and contact checks')
            check(mesh['intersectionValidation'].get('quadDiagonalPolicy')=='all_pairings',name+': all mixed diagonal contact pairings were checked')
            item.update(faces=len(mesh['faces']),outputSha256=hashlib.sha256((dest/'output.obj').read_bytes()).hexdigest())
            if name=='circle-repeat':
                original=json.loads((ROOT/'tests/toilet-strict-generation/warpage-guided/browser-lid-circle/mesh.json').read_text())
                same=mesh['faces']==original['faces'] and np.allclose(mesh['vertices'],original['vertices'],rtol=0,atol=1e-9)
                check(same,'Repeated identical Circle input reproduces faces and coordinates within 1e-9'); item['repeatWithin1e9']=bool(same)
        else:
            for resource in ('mesh.json','output.obj','features.json'):
                try: http('/api/jobs/'+submitted['id']+'/'+resource); code=200
                except urllib.error.HTTPError as error: code=error.code
                check(code==409,name+': unaccepted '+resource+' is unavailable')
        check(json.loads((folder/'curves.json').read_text())['curves']==curves,name+': authored samples are unchanged')
        cases.append(item); report()
    check(all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in hashes.items()),'Source and implementation remain fixed through the matrix')
except Exception:
    errors.append(traceback.format_exc()); print(errors[-1],flush=True)
finally:
    for job in jobs:
        try: http('/api/jobs/'+job+'/cancel',{})
        except OSError: pass
    for child in psutil.Process(server.pid).children(recursive=True):
        try: child.kill()
        except psutil.NoSuchProcess: pass
    server.terminate(); server.wait(timeout=20); log.close(); report(not errors)
raise SystemExit(0 if not errors and all(c['passed'] for c in checks) and all(c['state']=='complete' for c in cases) else 1)
