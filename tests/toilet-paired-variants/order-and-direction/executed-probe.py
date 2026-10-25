"""Production bowl/paired-guide input-equivalence and density regression matrix.

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
sys.path.insert(0,str(ROOT))
from process_ownership import protect_service_tree
protect_service_tree()
parser=argparse.ArgumentParser(); parser.add_argument('--label',default='current'); parser.add_argument('--cases',nargs='+'); args=parser.parse_args()
if not args.label.replace('-','').isalnum():raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-paired-variants'/args.label; OUT.mkdir(parents=True,exist_ok=False)
(OUT/'executed-probe.py').write_bytes(Path(__file__).read_bytes())
FILES=('app.js','server.py','worker.py','curved_quad.py','surface_intersections.py','surface_distance.py','quad_quality.py','assets/models/toilet.obj','surface_guide_refine.py','surface_guide_repair.py','tests/verify_toilet_paired_variants.py')
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}
def saved(name): return json.loads((ROOT/'tests/toilet-stress'/name/'curves.json').read_text())['curves']
short=saved('two-guides-short-1800'); bowl=saved('bowl-only-1800')[0]
def densified(curve):
    result=[]
    for a,b in zip(curve[:-1],curve[1:]):result.extend([a,((np.asarray(a)+b)*.5).tolist()])
    return result+[curve[-1]]
unique=bowl[:-1];offset=len(unique)//3;cyclic=unique[offset:]+unique[:offset];cyclic.append(cyclic[0])
source=trimesh.load(ROOT/'assets/models/toilet.obj',process=False,force='mesh')
rng=np.random.default_rng(20261025)
perturbed=[]
for curve in short:
    closed=curve[0]==curve[-1];unique=curve[:-1] if closed else curve
    moved=np.asarray(unique)+rng.normal(0,.001,(len(unique),3))
    points=trimesh.proximity.closest_point(source,moved)[0].tolist()
    dedup=[points[0]]
    for point in points[1:]:
        if point!=dedup[-1]:dedup.append(point)
    if closed:
        if dedup[-1]==dedup[0]:dedup.pop()
        dedup.append(dedup[0])
    perturbed.append(dedup)
specs=[('short-reordered',1800,short[::-1]),('short-reversed',1800,[c[::-1] for c in short]),
       ('short-densified',1800,[densified(c) for c in short]),('bowl-cyclic-start',1800,[cyclic]),
       ('short-small-perturbation',1800,perturbed),('short-1799',1799,short)]
if args.cases:
    unknown=set(args.cases)-{s[0] for s in specs}
    if unknown:raise ValueError('Unknown requested cases: '+', '.join(sorted(unknown)))
    specs=[s for s in specs if s[0] in args.cases]
if not specs: raise ValueError('No requested matrix cases')
with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'; checks,cases,errors,jobs=[],[],[],[]
pointer=ROOT/'runs/server.json';old_pointer=pointer.read_bytes() if pointer.exists() else None
def http(path,body=None):
    req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=20))
def check(value,name):
    checks.append(dict(name=name,passed=bool(value))); print(('PASS ' if value else 'FAIL ')+name,flush=True)
def report(complete=False):
    result=dict(complete=complete,generationPassed=complete and bool(cases) and all(c['state']=='complete' for c in cases),
        safetyChecksPassed=all(c['passed'] for c in checks) and not errors,cases=cases,checks=checks,errors=errors,sourceHashes=hashes,
        scope='Fresh Blender layouts and actual worker requests for the named cases. Available partitions cover equivalent representations, 0.001-unit Gaussian paired-guide perturbation projected to source (consecutive duplicate points removed), and the adjacent target1799 boundary. Additional module hashes cover the production sampled fallback. Failed geometry remains unsolved; does not prove all continuous inputs.')
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
        for filename in ('curves.json','settings.json','report.json','execution.json','surface-solver.json','surface-solver-failure.json','sampled-guide-history.json','output.obj','mesh.json','worker.log'):
            if (folder/filename).exists(): shutil.copyfile(folder/filename,dest/filename)
        item=dict(name=name,target=target,job=submitted['id'],state=status['state'],message=status.get('error'),elapsedSeconds=time.monotonic()-started)
        if status['state']=='complete':
            mesh=http('/api/jobs/'+submitted['id']+'/mesh.json')
            check(mesh['surfaceValidation']['passed'] and set(mesh['surfaceValidation']['wholeSurfaceDiagonals'])=={'02','13'} and mesh['intersectionValidation']['passed'],name+': accepted geometry includes both diagonal bounds and contact checks')
            check(mesh['intersectionValidation'].get('quadDiagonalPolicy')=='all_pairings',name+': all mixed diagonal contact pairings were checked')
            item.update(faces=len(mesh['faces']),outputSha256=hashlib.sha256((dest/'output.obj').read_bytes()).hexdigest())
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
    server.terminate(); server.wait(timeout=20); log.close()
    if pointer.exists() and json.loads(pointer.read_text()).get('pid')==server.pid:
        if old_pointer is None:pointer.unlink()
        else:pointer.write_bytes(old_pointer)
    report(not errors)
raise SystemExit(0 if not errors and all(c['passed'] for c in checks) and all(c['state']=='complete' for c in cases) else 1)
