"""Exercise timeout cleanup on an actual toilet worker and its Blender child.

The timeout event is injected once the real child exists, without waiting ten
minutes. Process creation, original source, solver startup, kill and reap are
real. This does not test a ten-minute wall-clock duration or invent a mesh.
"""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time
import traceback
from unittest.mock import patch
import uuid
import psutil

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import server
OUT=ROOT/'tests/toilet-process-timeout'; OUT.mkdir(exist_ok=True)
folder=ROOT/'runs'/uuid.uuid4().hex; folder.mkdir()
source=json.loads((ROOT/'assets/models/toilet.json').read_text())
server.write(folder/'settings.json',dict(meshId='toilet',target=1800,guideMode=2,sourceSha256=source['sourceSha256']))
server.write(folder/'curves.json',json.loads((ROOT/'tests/toilet-stress/browser-lid-circle/curves.json').read_text()))
job=dict(id=folder.name,meshId='toilet',target=1800,state='queued',stage='Waiting for solver',directory=folder)
real_spawn=subprocess.Popen; owned=[]; observed=[]; checks=[]; errors=[]
def check(value,name):
    checks.append(dict(passed=bool(value),name=name)); print(('PASS ' if value else 'FAIL ')+name,flush=True)

class ControlledTimeout:
    def __init__(self,*args,**kwargs):
        self.process=real_spawn(*args,**kwargs); self.first=True; owned.append(self.process)
    def __getattr__(self,name): return getattr(self.process,name)
    def wait(self,timeout=None):
        if not self.first: return self.process.wait(timeout=timeout)
        self.first=False; deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            if self.process.poll() is not None: raise AssertionError('Worker exited before the child-timeout precondition')
            descendants=psutil.Process(self.process.pid).children(recursive=True)
            if any('blender' in p.name().lower() for p in descendants):
                for p in [psutil.Process(self.process.pid)]+descendants:
                    observed.append(dict(pid=p.pid,created=p.create_time(),name=p.name(),command=p.cmdline()))
                check(timeout==600,'Production execute uses its unchanged 600-second timeout')
                raise subprocess.TimeoutExpired('actual toilet worker',timeout)
            time.sleep(.03)
        raise AssertionError('No actual Blender descendant was observed before the bounded test deadline')

try:
    with patch.object(server.subprocess,'Popen',ControlledTimeout): server.execute(job)
    check(any('blender' in p['name'].lower() for p in observed),'Timeout was injected only after a real Blender child started')
    check(job['state']=='failed' and 'ten-minute limit' in job.get('error',''),'Timeout produces a failed job with the specific limit message')
    check(job.get('actualExitCode') not in (0,None),'Killed worker has a real nonzero exit code')
    deadline=time.monotonic()+10
    def survivors():
        live=[]
        for record in observed:
            try:
                p=psutil.Process(record['pid'])
                if p.is_running() and p.create_time()==record['created']: live.append(record['pid'])
            except psutil.NoSuchProcess: pass
        return live
    while survivors() and time.monotonic()<deadline: time.sleep(.05)
    check(not survivors(),'Actual worker and observed Blender descendants are gone after timeout cleanup')
    check(not (folder/'mesh.json').exists() and not (folder/'output.obj').exists(),'Timed-out worker publishes no output geometry')
    execution=json.loads((folder/'execution.json').read_text())
    check(execution['state']=='failed' and execution['actualExitCode']==job['actualExitCode'],'Retained execution record matches actual process failure')
except Exception:
    errors.append(traceback.format_exc()); print(errors[-1],flush=True)
finally:
    for process in owned:
        if process.poll() is None: server.terminate_worker(process)
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: errors.append('Owned worker did not exit during final cleanup')
    for name in ('curves.json','settings.json','execution.json','worker.log'):
        if (folder/name).exists(): (OUT/name).write_bytes((folder/name).read_bytes())
    result=dict(passed=not errors and all(c['passed'] for c in checks),checks=checks,errors=errors,observedProcesses=observed,
        sourceHashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('server.py','worker.py','assets/models/toilet.obj','tests/verify_toilet_process_timeout.py')},
        scope='Actual toilet worker and Blender subprocess; one timeout event injected at the production wait boundary after observing the real child. Does not wait ten wall-clock minutes or substitute generated geometry.')
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
raise SystemExit(0 if result['passed'] else 1)
