"""Exercise actual coarse Generate/export in the isolated proposed service."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
import psutil
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from process_ownership import protect_service_tree
protect_service_tree()
SERVICE=ROOT/'runs/frozen-boundary-service'
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
if not args.label.replace('-','').isalnum():raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-coarse-browser'/args.label
OUT.mkdir(parents=True,exist_ok=False)
(OUT/'executed-test.py').write_bytes(Path(__file__).read_bytes())
snapshot=json.loads((SERVICE/'snapshot.json').read_text())
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
assert all(sha(SERVICE/name)==digest for name,digest in snapshot['files'].items())
(OUT/'frozen-service-snapshot.json').write_bytes((SERVICE/'snapshot.json').read_bytes())
(OUT/'unguided-dispatch.patch').write_bytes((SERVICE/'unguided-dispatch.patch').read_bytes())
for name in ('curved_quad.py','worker.py','surface_guide_refine.py','surface_guide_repair.py','surface_boundary_repair.py','surface_guide_joint.py','server.py'):
    destination=OUT/'executed-source'/name;destination.parent.mkdir(exist_ok=True)
    shutil.copyfile(SERVICE/name,destination)
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'
checks,cases,errors,observed=[],[],[],{}
start=time.monotonic();main_pointer=ROOT/'runs/server.json';old_pointer=main_pointer.read_bytes()
log=(OUT/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-X','utf8',str(SERVICE/'server.py'),'--port',str(port)],cwd=SERVICE,stdout=log,stderr=log,
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
def http(path):
    with urllib.request.urlopen(url+path,timeout=15) as response:return json.load(response)
def check(value,name,**details):
    checks.append(dict(passed=bool(value),name=name,**details));print(('PASS ' if value else 'FAIL ')+name,flush=True)
def observe():
    for p in psutil.Process().children(recursive=True):
        try:observed[(p.pid,p.create_time())]=dict(pid=p.pid,createdAt=p.create_time(),name=p.name(),parentPid=p.ppid())
        except psutil.NoSuchProcess:pass
def save(complete):
    unchanged=all(sha(SERVICE/name)==digest for name,digest in snapshot['files'].items())
    (OUT/'result.json').write_text(json.dumps(dict(complete=complete,passed=complete and not errors and all(c['passed'] for c in checks),
        productionResult=False,isolatedRealWorker=True,checks=checks,cases=cases,errors=errors,
        sourceHashes={'tests/verify_toilet_coarse_browser.py':sha(Path(__file__))},
        frozenImplementationUnchanged=unchanged,elapsedSeconds=time.monotonic()-start,
        scope='Native Chromium Generate and OBJ downloads from an isolated frozen real HTTP/worker service. The reviewed guard-removal patch enables unguided fallback only in that copy. No mocked results or retained output geometry are inputs. This does not claim the shared live application dispatch has been changed.'),indent=2)+'\n')
try:
    deadline=time.monotonic()+30
    while True:
        try:
            if http('/api/health')['ready']:break
        except OSError:pass
        if time.monotonic()>deadline:raise RuntimeError('Isolated service startup failed')
        time.sleep(.1)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(viewport=dict(width=1700,height=1050),device_scale_factor=1)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(url,wait_until='networkidle')
        page.wait_for_function('window.retopoDemo?.getState().resultFaces > 0')
        page.locator('#meshSelect').select_option('toilet')
        page.wait_for_function('window.retopoDemo.getState().meshId === "toilet" && !document.getElementById("generateButton").disabled')
        if page.locator('#clearButton').is_enabled():page.locator('#clearButton').click()
        page.wait_for_function('window.retopoDemo.getState().guides.length === 0')
        check(http('/api/mesh/toilet')['sourceSha256']==snapshot['originalSourceSha256'],'Isolated service serves the unchanged original toilet')
        for target in (150,600):
            name='unguided-'+str(target)
            page.locator('#targetNumber').fill(str(target));page.locator('#targetNumber').press('Tab')
            before=page.evaluate('window.retopoDemo.getState().guideDocument')
            empty=len(page.evaluate('window.retopoDemo.getState().guides'))==0
            check(empty,name+' has no guides')
            if not empty:raise AssertionError('Clear-guide setup failed before Generate')
            page.locator('#generateButton').click();deadline=time.monotonic()+650;previous=None
            while True:
                state=page.evaluate('window.retopoDemo.getState()');stage=page.locator('#processTitle').inner_text()
                if stage!=previous:
                    print(name,stage.strip(),flush=True);previous=stage;observe()
                if not state['busy']:break
                if time.monotonic()>deadline:raise TimeoutError('Isolated browser solve exceeded service timeout allowance')
                page.wait_for_timeout(1000)
            case=dict(name=name,target=target,state=state['lastAttempt']['phase'],job=state['resultJob'],producerKind='isolated-real-worker-browser')
            cases.append(case)
            check(case['state']=='complete' and bool(case['job']),name+' completes through the real worker',lastAttempt=state['lastAttempt'])
            if case['state']!='complete' or not case['job']:raise AssertionError('No accepted result: '+json.dumps(state['lastAttempt']))
            job=http('/api/jobs/'+case['job']);case['elapsedSeconds']=job['finishedAt']-job['startedAt']
            retained=OUT/name;shutil.copytree(SERVICE/'runs'/case['job'],retained)
            case['faces']=state['resultFaces'];case['outputSha256']=sha(retained/'output.obj')
            check(job['state']=='complete' and abs(case['faces']-target)<=.15*target,name+' honors requested density tolerance')
            check(state['guideDocument']==before and not state['dirty'],name+' preserves the document and clears the update badge')
            check(page.locator('#generationFeedback').is_hidden(),name+' replaces the empty or previous result with generated geometry')
            with page.expect_download() as event:page.locator('#exportMesh').click()
            event.value.save_as(str(retained/'browser-export.obj'))
            check((retained/'browser-export.obj').read_bytes()==(retained/'output.obj').read_bytes(),name+' downloads exactly the accepted worker OBJ')
            mesh=json.loads((retained/'mesh.json').read_text())
            check(all(mesh[key]['passed'] for key in ('surfaceValidation','intersectionValidation','quality')),name+' retains all geometry gates')
            page.locator('#fitButton').click();page.screenshot(path=str(retained/'accepted.png'))
            save(False)
        context.close();browser.close()
    check(all(sha(SERVICE/name)==digest for name,digest in snapshot['files'].items()),'Frozen implementation remains unchanged through both browser jobs')
    check(main_pointer.read_bytes()==old_pointer,'Shared live-service pointer stays untouched')
except Exception:
    errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:
    if server.poll() is None:server.kill()
    server.wait(timeout=15);log.close()
    live=[]
    for row in observed.values():
        try:
            p=psutil.Process(row['pid'])
            if p.is_running() and p.create_time()==row['createdAt']:live.append(row)
        except psutil.NoSuchProcess:pass
    check(not live,'Observed test processes exit',survivors=live,observedProcesses=len(observed))
    (OUT/'process-observation.json').write_text(json.dumps(dict(complete=True,passed=not live,observed=list(observed.values()),survivors=live),indent=2)+'\n')
    save(True)
raise SystemExit(0 if not errors and all(c['passed'] for c in checks) else 1)
