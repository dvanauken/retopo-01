"""Force the actual toilet worker to exit while its actual Blender child exists.

Blender is suspended only after it is observed as this worker's descendant, so
its natural completion cannot be mistaken for crash cleanup. The service stays
alive. No job success or geometry is substituted.
"""
import argparse,hashlib,json,os,socket,subprocess,sys,time,traceback,urllib.error,urllib.request,uuid
from pathlib import Path
import psutil

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
if not args.label.replace('-','').isalnum():raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-worker-crash'/args.label;OUT.mkdir(parents=True,exist_ok=True)
checks,errors,observed,jobs=[],[],[],[]
files=['server.py','worker.py','process_ownership.py','tests/verify_toilet_worker_crash.py']
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files}
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'

def check(value,name,**details):
    checks.append(dict(passed=bool(value),name=name,**details));print(('PASS ' if value else 'FAIL ')+name,flush=True)

def http(path,body=None):
    req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=10) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:return error.code,json.load(error)

def survivors():
    live=[]
    for record in observed:
        try:
            process=psutil.Process(record['pid'])
            if process.is_running() and process.create_time()==record['created']:live.append(process)
        except psutil.NoSuchProcess:pass
    return live

log=(OUT/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-X','utf8','server.py','--port',str(port)],cwd=ROOT,stdout=log,stderr=log,
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
    deadline=time.monotonic()+30
    while True:
        try:
            if http('/api/health')[0]==200:break
        except OSError:pass
        if time.monotonic()>deadline or server.poll() is not None:raise RuntimeError('Isolated test service startup failed')
        time.sleep(.05)
    _,job=http('/api/remesh',dict(requestId=uuid.uuid4().hex,meshId='toilet',target=1800,guideMode=2,curves=[]));jobs.append(job['id'])
    deadline=time.monotonic()+45;worker=None
    while time.monotonic()<deadline:
        for candidate in psutil.Process(server.pid).children(recursive=True):
            try:
                if not any(Path(arg).name=='worker.py' for arg in candidate.cmdline()):continue
                children=candidate.children(recursive=True)
                blenders=[child for child in children if 'blender' in child.name().lower()]
                if not blenders:continue
                for blender in blenders:blender.suspend()
                worker=candidate
                observed=[dict(pid=p.pid,created=p.create_time(),parentPid=p.ppid(),name=p.name(),command=p.cmdline(),suspended=p in blenders) for p in [worker,*children]]
                break
            except psutil.NoSuchProcess:continue
        if worker:break
        time.sleep(.025)
    if worker is None:raise AssertionError('No real toilet worker with Blender child before the crash injection')
    check(True,'Actual Blender child is held alive before killing only the actual toilet worker',observed=observed)
    worker.kill();worker.wait(timeout=10)
    check(not worker.is_running(),'Toilet worker is actually dead while its service remains alive')
    deadline=time.monotonic()+10
    while True:
        _,state=http('/api/jobs/'+job['id'])
        if state['state'] not in ('queued','running') or time.monotonic()>deadline:break
        time.sleep(.05)
    check(state['state']=='failed','Worker death becomes a structured failed job',state=state)
    check(server.poll() is None and http('/api/health')[0]==200,'Original service stays healthy through worker death')
    deadline=time.monotonic()+7
    while survivors() and time.monotonic()<deadline:time.sleep(.05)
    check(not survivors(),'Worker death leaves no owned Blender or other descendant alive',survivors=[p.pid for p in survivors()])
    for name in ('mesh.json','output.obj','features.json'):
        code,_=http('/api/jobs/'+job['id']+'/'+name)
        check(code==409,'Failed worker cannot publish '+name)
    _,cancelled=http('/api/jobs/'+job['id']+'/cancel',{})
    check(cancelled['state']=='failed','Late cancellation preserves the actual failed state')
    _,retry=http('/api/remesh',dict(requestId=uuid.uuid4().hex,meshId='toilet',target=1800,guideMode=2,curves=[]));jobs.append(retry['id'])
    _,cancelled=http('/api/jobs/'+retry['id']+'/cancel',{})
    check(retry['id']!=job['id'] and cancelled['state']=='cancelled','Service admits and cancels a fresh request after worker death')
    check(all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==value for p,value in hashes.items()),'Implementation remains fixed through the real worker-crash test')
except Exception:
    errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:
    for job_id in jobs:
        try:http('/api/jobs/'+job_id+'/cancel',{})
        except OSError:pass
    for process in survivors():
        try:process.kill()
        except psutil.NoSuchProcess:pass
    if server.poll() is None:server.kill()
    server.wait(timeout=15);log.close()
    report=dict(passed=not errors and all(c['passed'] for c in checks),checks=checks,errors=errors,observedProcesses=observed,sourceHashes=hashes,
                scope='Actual worker-only abrupt exit, with its real Blender child suspended to prevent natural exit from masquerading as cleanup. Original isolated service remains alive; failure, publication denial and recovery admission are measured.')
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=report['passed'],checks=len(checks))),flush=True)
raise SystemExit(0 if report['passed'] else 1)
