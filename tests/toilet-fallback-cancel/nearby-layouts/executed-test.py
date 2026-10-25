"""Cancel an actual toilet solve after it enters sampled fitting."""
import argparse, hashlib, json, os, socket, subprocess, sys, time, traceback, urllib.error, urllib.request, uuid
from pathlib import Path
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from process_ownership import protect_service_tree
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--stage', choices=['sampled', 'joint', 'nearby'], default='sampled')
args = parser.parse_args()
if not args.label.replace('-', '').isalnum(): raise ValueError('Use a plain label')
protect_service_tree()
OUT = ROOT / 'tests/toilet-fallback-cancel' / args.label
OUT.mkdir(parents=True, exist_ok=False)
(OUT / 'executed-test.py').write_bytes(Path(__file__).read_bytes())
files = ['server.py', 'worker.py', 'curved_quad.py', 'surface_guide_refine.py', 'surface_guide_repair.py', 'surface_guide_joint.py', 'process_ownership.py', 'tests/verify_toilet_fallback_cancel.py']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
hashes = {name: sha(ROOT / name) for name in files}
checks, errors, observed, service_observed = [], [], [], []
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
url = f'http://127.0.0.1:{port}'
pointer = ROOT / 'runs/server.json'; old_pointer = pointer.read_bytes() if pointer.exists() else None

def http(path, body=None):
    request = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response: return response.status, json.load(response)
    except urllib.error.HTTPError as error: return error.code, json.load(error)

def check(value, name, **detail):
    checks.append(dict(passed=bool(value), name=name, **detail)); print(('PASS ' if value else 'FAIL ') + name, flush=True)

def survivors():
    live = []
    for row in observed:
        try:
            p = psutil.Process(row['pid'])
            if p.is_running() and p.create_time() == row['created']: live.append(p.pid)
        except psutil.NoSuchProcess: pass
    return live

log = (OUT / 'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([sys.executable, '-X', 'utf8', 'server.py', '--port', str(port)], cwd=ROOT, stdout=log, stderr=log,
    env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'), creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
job = None
started = time.monotonic()
try:
    deadline = time.monotonic() + 30
    while True:
        try:
            if http('/api/health')[0] == 200: break
        except OSError: pass
        if time.monotonic() > deadline: raise RuntimeError('Test service startup failed')
        time.sleep(.1)
    case_name = 'two-guides-long-1800' if args.stage == 'joint' else 'two-guides-short-1800'
    stage_prefix = 'Refining guide alignment and surface accuracy' if args.stage == 'joint' else 'Fitting sampled guide paths'
    curves = json.loads((ROOT / 'tests/toilet-stress' / case_name / 'curves.json').read_text())['curves']
    target = 1799 if args.stage == 'nearby' else 1800
    code, job = http('/api/remesh', dict(requestId=uuid.uuid4().hex, meshId='toilet', target=target, guideMode=2, curves=curves))
    check(code == 202, 'Captured two-guide request admitted')
    deadline = time.monotonic() + 600; previous = None
    while True:
        _, state = http('/api/jobs/' + job['id'])
        if state['stage'] != previous: print(state['stage'], flush=True); previous = state['stage']
        ready = state['stage'].startswith(stage_prefix)
        if args.stage == 'nearby':
            manifest = ROOT / 'runs' / job['id'] / 'nearby-layout-attempts.json'
            try:
                attempts = json.loads(manifest.read_text())['attempts']
            except (OSError, ValueError):
                attempts = []
            ready = ready and len(attempts) == 1 and attempts[0]['layoutTarget'] == 1799 and not attempts[0]['accepted']
        if ready: break
        if state['state'] not in ('queued', 'running') or time.monotonic() > deadline: raise AssertionError('Did not observe actual sampled fitting: ' + json.dumps(state))
        time.sleep(.2)
    check(state['state'] == 'running', 'Real worker reached the new fallback before cancellation', state=state)
    if args.stage == 'nearby':
        check((ROOT / 'runs' / job['id'] / 'sampled-layout-1799/failed-sampled-guide-candidate.json').exists(),
              'The first rejected layout was archived before cancelling fitting of the second layout', attempts=attempts)
    worker = None
    for p in psutil.Process(server.pid).children(recursive=True):
        try:
            command = p.cmdline()
            service_observed.append(dict(pid=p.pid, parentPid=p.ppid(), created=p.create_time(), name=p.name(), command=command))
            if any(Path(arg).name == 'worker.py' for arg in command) and any(Path(arg).name == job['id'] for arg in command): worker = p
        except psutil.NoSuchProcess: pass
    if worker is None: raise AssertionError('The running job has no identifiable live worker')
    for p in [worker, *worker.children(recursive=True)]:
        try: observed.append(dict(pid=p.pid, parentPid=p.ppid(), created=p.create_time(), name=p.name(), command=p.cmdline(), ownerWorker=worker.pid))
        except psutil.NoSuchProcess: pass
    check(any(p['pid'] == worker.pid for p in observed), 'An actual worker and its own descendants are identified before cancellation')
    begin = time.monotonic(); _, cancelled = http('/api/jobs/' + job['id'] + '/cancel', {})
    check(cancelled['state'] == 'cancelled', 'Service confirms cancellation of the fitting job', responseSeconds=time.monotonic() - begin)
    deadline = time.monotonic() + 10
    while survivors() and time.monotonic() < deadline: time.sleep(.1)
    check(not survivors(), 'No owned fitting process survives cancellation', survivors=survivors())
    for filename in ('mesh.json', 'output.obj', 'features.json'):
        check(http('/api/jobs/' + job['id'] + '/' + filename)[0] == 409, 'Cancelled fitting cannot serve ' + filename)
    check(http('/api/health')[0] == 200, 'Service stays responsive after fallback cancellation')
    _, retry = http('/api/remesh', dict(requestId=uuid.uuid4().hex, meshId='toilet', target=target, guideMode=2, curves=curves))
    _, retry_state = http('/api/jobs/' + retry['id'] + '/cancel', {})
    check(retry['id'] != job['id'] and retry_state['state'] == 'cancelled', 'A fresh request can be admitted and cancelled afterward')
    check(all(sha(ROOT / p) == h for p, h in hashes.items()), 'Implementation fixed through real fallback cancellation')
except Exception:
    errors.append(traceback.format_exc()); print(errors[-1], flush=True)
finally:
    if job:
        try: http('/api/jobs/' + job['id'] + '/cancel', {})
        except OSError: pass
        for filename in ('worker.log', 'settings.json', 'curves.json', 'execution.json', 'cancel-request.json', 'nearby-layout-attempts.json'):
            path = ROOT / 'runs' / job['id'] / filename
            if path.exists(): (OUT / filename).write_bytes(path.read_bytes())
    if server.poll() is None: server.kill()
    server.wait(timeout=15); log.close()
    if pointer.exists() and json.loads(pointer.read_text()).get('pid') == server.pid:
        if old_pointer is None: pointer.unlink()
        else: pointer.write_bytes(old_pointer)
    (OUT / 'result.json').write_text(json.dumps(dict(complete=True, passed=not errors and all(c['passed'] for c in checks), checks=checks,
        errors=errors, observedProcesses=observed, serviceDescendantsBeforeCancellation=service_observed, job=job, sourceHashes=hashes, elapsedSeconds=time.monotonic()-started,
        requestedStage=args.stage,
        scope='Real production two-guide solve observed in the requested fitting stage, then cancelled through HTTP. No injected successful geometry or suspended worker.'), indent=2) + '\n', newline='\n')
raise SystemExit(0 if not errors and all(c['passed'] for c in checks) else 1)
