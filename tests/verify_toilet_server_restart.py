"""Kill only an isolated test server while its real toilet/Blender tree is live."""
import argparse,hashlib,json,os,socket,subprocess,sys,time,traceback,urllib.error,urllib.request,uuid
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
if not args.label.replace('-','').isalnum():raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-server-restart'/args.label;OUT.mkdir(parents=True,exist_ok=True)
checks,errors,observed,servers=[],[],[],[]
FILES=['server.py','worker.py','tests/verify_toilet_server_restart.py']
if (ROOT/'process_ownership.py').exists():FILES.append('process_ownership.py')
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'
log=(OUT/'server.log').open('w',encoding='utf-8')
def check(value,name,**details):
    checks.append(dict(passed=bool(value),name=name,**details));print(('PASS ' if value else 'FAIL ')+name,flush=True)
def http(path,body=None):
    req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=10) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
def launch():
    p=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'server.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=log,
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));servers.append(p)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        try:
            if http('/api/health')[0]==200:return p
        except OSError:pass
        if p.poll() is not None:raise RuntimeError('Server startup failed')
        time.sleep(.05)
    raise RuntimeError('Server startup deadline')
def survivors():
    live=[]
    for record in observed:
        try:
            p=psutil.Process(record['pid'])
            if p.is_running() and p.create_time()==record['created']:live.append(p.pid)
        except psutil.NoSuchProcess:pass
    return live
try:
    server=launch();request_id=uuid.uuid4().hex
    _,job=http('/api/remesh',dict(requestId=request_id,meshId='toilet',target=1800,guideMode=2,curves=[]))
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        descendants=psutil.Process(server.pid).children(recursive=True)
        workers=[p for p in descendants if 'worker.py' in ' '.join(p.cmdline())]
        if workers and any('blender' in p.name().lower() for p in descendants):
            owned={p.pid:p for worker in workers for p in [worker,*worker.children(recursive=True)]}
            observed.extend(dict(pid=p.pid,created=p.create_time(),name=p.name(),parentPid=p.ppid(),command=p.cmdline()) for p in owned.values());break
        time.sleep(.025)
    if not observed:raise AssertionError('No real toilet worker with Blender child before crash injection')
    check(True,'Server crash is injected only after a real toilet worker and Blender child exist',observed=observed)
    server.kill();server.wait(timeout=10)
    check(server.returncode is not None,'Original server is actually dead before restart')
    deadline=time.monotonic()+7
    while survivors() and time.monotonic()<deadline:time.sleep(.05)
    check(not survivors(),'Abrupt server death leaves no live owned toilet worker or Blender child',survivors=survivors())
    replacement=launch()
    code,data=http('/api/requests/'+request_id+'/cancel',{})
    check(code==200 and data['state']=='cancelled' and not survivors(),'Cancellation on the replacement service corresponds to no old worker running',status=code,survivors=survivors())
    code,data=http('/api/jobs/'+job['id']+'/mesh.json')
    check(code==404,'Replacement service cannot publish an abandoned old result')
    _,retry=http('/api/remesh',dict(requestId=uuid.uuid4().hex,meshId='toilet',target=1800,guideMode=2,curves=[]))
    _,cancelled=http('/api/jobs/'+retry['id']+'/cancel',{})
    check(cancelled['state']=='cancelled' and retry['id']!=job['id'],'Restart admits and cancels a fresh request')
except Exception:
    errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:
    for process in servers:
        if process.poll() is None:
            for child in psutil.Process(process.pid).children(recursive=True):
                try:child.kill()
                except psutil.NoSuchProcess:pass
            process.kill();process.wait(timeout=10)
    for pid in survivors():
        try:psutil.Process(pid).kill()
        except psutil.NoSuchProcess:pass
    log.close()
    report=dict(passed=not errors and all(c['passed'] for c in checks),checks=checks,errors=errors,observedProcesses=observed,sourceHashes=hashes,
        implementationUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),
        scope='Actual isolated server is forcibly killed only after a real toilet worker and Blender child exist. Server restarts on the same port; old-worker liveness and new admission are measured. No live user server is touched.')
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=report['passed'],checks=len(checks))),flush=True)
raise SystemExit(0 if report['passed'] else 1)
