"""Fresh toilet solves after strengthening acceptance; rejection is not success."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
from pathlib import Path
import hashlib
import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
import psutil

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(); parser.add_argument('--label',default='current'); parser.add_argument('--cases',nargs='+'); args=parser.parse_args()
OUT = ROOT/'tests/toilet-strict-generation'/args.label
OUT.mkdir(parents=True,exist_ok=True)
HASH_FILES = ('app.js','server.py','worker.py','curved_quad.py','surface_intersections.py','surface_distance.py','quad_quality.py','assets/models/toilet.obj','tests/verify_toilet_strict_generation.py')
hashes = {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in HASH_FILES}
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
url = f'http://127.0.0.1:{port}'


def http(path, body=None):
    req = urllib.request.Request(url+path, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


cases, checks, errors = [], [], []
jobs = []
def check(condition, name):
    checks.append(dict(name=name, passed=bool(condition)))
    print(('PASS ' if condition else 'FAIL ')+name, flush=True)


def report(complete=False):
    (OUT/'result.json').write_text(json.dumps(dict(complete=complete,
        generationPassed=complete and bool(cases) and all(c['state']=='complete' for c in cases),
        safetyChecksPassed=all(c['passed'] for c in checks) and not errors,
        cases=cases, checks=checks, errors=errors, sourceHashes=hashes,
        scope='Fresh local worker and Blender solves on unchanged source/guide inputs. Rejection checks establish safe failure handling only; generationPassed stays false if a required solve fails.'),indent=2)+'\n')


log = (OUT/'server.log').open('w',encoding='utf-8')
process = subprocess.Popen([sys.executable,'-X','utf8','server.py','--port',str(port)],cwd=ROOT,stdout=log,stderr=log,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
    for _ in range(100):
        try:
            http('/api/health'); break
        except (OSError,urllib.error.URLError):
            if process.poll() is not None: raise RuntimeError('Owned test server exited')
            time.sleep(.1)
    names = args.cases or ('two-guides-short-1800','two-guides-long-1800','bowl-only-1800','lid-only-1800','unguided-1800','browser-lid-circle')
    for name in names:
        packet = json.loads((ROOT/'tests/toilet-stress'/name/'curves.json').read_text())
        curves = packet['curves']
        submitted = http('/api/remesh',dict(meshId='toilet', target=1800, guideMode=2, curves=curves))
        jobs.append(submitted['id']); started=time.monotonic(); stage=None
        while True:
            state=http('/api/jobs/'+submitted['id'])
            if stage != state.get('stage'):
                stage=state.get('stage'); print(name, state['state'], stage, flush=True)
            if state['state'] in ('complete','failed','cancelled'): break
            if time.monotonic()-started > 650: raise TimeoutError(submitted['id'])
            time.sleep(.5)
        folder=ROOT/'runs'/submitted['id']; destination=OUT/name; destination.mkdir(exist_ok=True)
        for filename in ('curves.json','settings.json','report.json','execution.json','surface-solver.json',
                         'surface-solver-failure.json','output.obj','mesh.json','worker.log'):
            if (folder/filename).is_file(): shutil.copyfile(folder/filename,destination/filename)
            else: (destination/filename).unlink(missing_ok=True)
        item=dict(name=name, job=submitted['id'], state=state['state'], message=state.get('error'),
                  elapsedSeconds=time.monotonic()-started, guides=len(curves))
        cases.append(item)
        if state['state']=='complete':
            mesh=http('/api/jobs/'+submitted['id']+'/mesh.json')
            check(mesh['surfaceValidation']['checks'].get('wholeSurface') is True, name+': accepted result carries whole-surface bounds')
            check(set(mesh['surfaceValidation']['wholeSurfaceDiagonals'])=={'02','13'}, name+': both quad diagonals were bounded')
            check(mesh['intersectionValidation']['passed'] and not mesh['intersectionValidation']['adjacentIntersectingFacePairs'], name+': adjacent contacts were checked')
            check(mesh['intersectionValidation'].get('quadDiagonalPolicy')=='all_pairings', name+': contact acceptance checks every mixed quad-diagonal pairing')
            item['faces']=len(mesh['faces'])
        else:
            for resource in ('mesh.json','output.obj','features.json'):
                try: http('/api/jobs/'+submitted['id']+'/'+resource); status=200
                except urllib.error.HTTPError as e: status=e.code
                check(status==409, name+': rejected candidate cannot publish '+resource)
            check((folder/'report.json').is_file(),name+': failure retains a diagnostic report')
        check(json.loads((folder/'curves.json').read_text())['curves']==curves,name+': authored samples preserved')
        report()
    check(hashlib.sha256((ROOT/'assets/models/toilet.obj').read_bytes()).hexdigest()==hashes['assets/models/toilet.obj'],'Original toilet source is unchanged')
    check(all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in hashes.items()),'Implementation stayed fixed throughout this matrix')
except Exception as error:
    errors.append(repr(error)); print(repr(error),flush=True)
finally:
    for job in jobs:
        try: http('/api/jobs/'+job+'/cancel',{})
        except Exception: pass
    try:
        owned=psutil.Process(process.pid); children=owned.children(recursive=True)
        for child in reversed(children):
            try: child.kill()
            except psutil.NoSuchProcess: pass
        process.terminate(); process.wait(timeout=10)
    except psutil.NoSuchProcess: pass
    log.close(); report(complete=not errors)
raise SystemExit(0 if not errors and all(c['state']=='complete' for c in cases) and all(c['passed'] for c in checks) else 1)
