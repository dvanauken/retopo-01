"""Real HTTP contract, queue/cancel lifecycle and accepted-only publication.

Publication races are made deterministic by suspending this test's owned worker
and planting explicitly unaccepted artifacts. These fixtures are never counted
as generated geometry. A separate fresh real solve verifies accepted downloads.
"""
from pathlib import Path
import argparse
import hashlib
import http.client
import json
import os
import socket
import subprocess
import sys
import time
import traceback
import psutil

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--label', default='current')
args = parser.parse_args()
if not args.label.replace('-', '').isalnum():
    raise ValueError('Use a plain evidence label')
OUT = ROOT / 'tests/toilet-api' / args.label
OUT.mkdir(parents=True, exist_ok=True)
checks, jobs, errors, suspended = [], [], [], []


def check(value, name, **details):
    checks.append(dict(name=name, passed=bool(value), **details))
    print(('PASS ' if value else 'FAIL ') + name, flush=True)


def request(path, payload=None, *, body=None, headers=None, method=None):
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=15)
    method = method or ('POST' if payload is not None or body is not None else 'GET')
    raw = body if body is not None else json.dumps(payload).encode() if payload is not None else None
    metadata = {'Content-Type': 'application/json'} if method == 'POST' else {}
    metadata.update(headers or {})
    try:
        connection.request(method, path, body=raw, headers=metadata)
        response = connection.getresponse(); data = response.read()
        try:
            decoded = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            decoded = data
        return response.status, decoded, dict(response.getheaders())
    except (OSError, http.client.HTTPException) as error:
        return None, dict(connectionError=str(error)), {}
    finally:
        connection.close()


def start(curves=None, target=1800):
    status, job, _ = request('/api/remesh', dict(meshId='toilet', target=target, guideMode=2, curves=curves or []))
    if status != 202:
        raise RuntimeError((status, job))
    jobs.append(job['id'])
    return job['id']


def status(job):
    code, value, _ = request('/api/jobs/' + job)
    if code != 200:
        raise RuntimeError((code, value))
    return value


def cancel(job):
    return request('/api/jobs/' + job + '/cancel', {})


def wait_terminal(job):
    # Keep observing this same handle. The production worker owns its timeout.
    while True:
        value = status(job)
        if value['state'] in ('complete', 'cancelled', 'failed'):
            return value
        if server.poll() is not None:
            raise RuntimeError('Owned test server exited while job was active')
        time.sleep(.1)


with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
log = (OUT / 'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([sys.executable, '-X', 'utf8', str(ROOT / 'server.py'), '--port', str(port)], cwd=ROOT,
    env=dict(os.environ, OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', OMP_NUM_THREADS='1'),
    stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
try:
    while request('/api/health')[0] != 200:
        if server.poll() is not None:
            raise RuntimeError('Server exited during startup')
        time.sleep(.1)
    base = dict(meshId='toilet', target=1800, guideMode=2, curves=[])
    point = [0, 0, .1]
    invalid = [
        ('missing mesh', dict(target=1800, curves=[])), ('unknown mesh', dict(base, meshId='missing')),
        ('mesh list', dict(base, meshId=[])), ('mesh null', dict(base, meshId=None)),
        ('target below minimum', dict(base, target=149)), ('target above maximum', dict(base, target=1801)),
        ('target fractional', dict(base, target=150.5)), ('target boolean', dict(base, target=True)),
        ('target string', dict(base, target='1800')), ('target null', dict(base, target=None)),
        ('target absent', {k:v for k,v in base.items() if k != 'target'}),
        ('mode unknown', dict(base, guideMode=3)), ('mode boolean', dict(base, guideMode=True)),
        ('mode unsupported for toilet', dict(base, guideMode=1)), ('mode string', dict(base, guideMode='2')),
        ('curves absent', {k:v for k,v in base.items() if k != 'curves'}),
        ('curves object', dict(base, curves={})), ('curves null', dict(base, curves=None)),
        ('49 guides', dict(base, curves=[[point, point]] * 49)), ('empty guide', dict(base, curves=[[]])),
        ('one sample', dict(base, curves=[[point]])), ('2049 samples', dict(base, curves=[[point] * 2049])),
        ('sample budget 8193', dict(base, curves=[[point] * 2048] * 3 + [[point] * 2047, [point] * 2])),
        ('guide object', dict(base, curves=[{}])), ('point object', dict(base, curves=[[{}, point]])),
        ('XY point', dict(base, curves=[[[0, 0], point]])), ('XYZW point', dict(base, curves=[[[0, 0, 0, 1], point]])),
        ('boolean coordinate', dict(base, curves=[[[True, 0, 0], point]])),
        ('string coordinate', dict(base, curves=[[['0', 0, 0], point]])),
        ('NaN coordinate', dict(base, curves=[[[float('nan'), 0, 0], point]])),
        ('infinite coordinate', dict(base, curves=[[[float('inf'), 0, 0], point]])),
        ('positive coordinate boundary', dict(base, curves=[[[1e6, 0, 0], point]])),
        ('negative coordinate boundary', dict(base, curves=[[[-1e6, 0, 0], point]])),
        ('root list', []), ('root scalar', 1),
    ]
    for name, payload in invalid:
        code, response, _ = request('/api/remesh', payload)
        check(code == 400 and isinstance(response, dict) and isinstance(response.get('error'), str),
              'Reject ' + name + ' with a structured 400 response', status=code)
    for name, body, headers, expected in [
        ('malformed JSON', b'{', {}, 400), ('empty body', b'', {}, 400),
        ('JSON null', b'null', {}, 400), ('invalid UTF8', b'\xff', {}, 400),
        ('too deeply nested JSON', b'[' * 1500 + b'0' + b']' * 1500, {}, 400),
        ('wrong content type', b'{}', {'Content-Type': 'text/plain'}, 400),
        ('oversize declared body', b'{}', {'Content-Length': '2000001'}, 400),
        ('negative body length', b'{}', {'Content-Length': '-1'}, 400),
        ('foreign origin', json.dumps(base).encode(), {'Origin': 'https://example.invalid'}, 403),
    ]:
        code, response, _ = request('/api/remesh', body=body, headers=headers)
        check(code == expected and isinstance(response, dict) and isinstance(response.get('error'), str),
              'Reject ' + name + ' without dropping the connection', status=code)
    check(request('/api/health')[0] == 200, 'Malformed requests leave server healthy')
    for name, payload in [
        ('minimum target', dict(base, target=150)), ('maximum target', base),
        ('48 guides', dict(base, curves=[[point, point]] * 48)),
        ('2048 samples', dict(base, curves=[[point] * 2048])),
        ('8192 samples', dict(base, curves=[[point] * 2048] * 4)),
    ]:
        code, job, _ = request('/api/remesh', payload)
        check(code == 202 and job['state'] in ('queued', 'running'), 'Admit schema boundary: ' + name)
        if code == 202:
            jobs.append(job['id']); cancel(job['id'])
    unknown = '0' * 32
    check(request('/api/jobs/' + unknown)[0] == 404 and cancel(unknown)[0] == 404, 'Unknown jobs and cancellations return 404')

    # Hold one real worker so queue assertions do not depend on machine speed.
    first = start()
    while True:
        children = psutil.Process(server.pid).children(recursive=True)
        workers = [p for p in children if '--job' in p.cmdline() and str(ROOT / 'runs' / first) in p.cmdline()]
        if workers:
            worker = workers[0]; worker.suspend(); suspended.append(worker)
            for child in worker.children(recursive=True):
                try:
                    child.suspend(); suspended.append(child)
                except psutil.NoSuchProcess:
                    pass
            break
        if status(first)['state'] not in ('queued', 'running'):
            raise RuntimeError('Worker ended before deterministic queue observation')
        time.sleep(.02)
    second, third = start(), start()
    check(status(second)['state'] == status(third)['state'] == 'queued', 'Only one worker runs while the next two jobs remain queued')
    check(request('/api/remesh', base)[0] == 400, 'A fourth active request is refused without starting another worker')
    for name, content in [('output.obj', '# deliberately unaccepted publication fixture\n'), ('mesh.json', '{"unacceptedFixture":true}'), ('features.json', '{"unacceptedFixture":true}')]:
        (ROOT / 'runs' / first / name).write_text(content)
        code, _, _ = request('/api/jobs/' + first + '/' + name)
        check(code == 409, 'Running job cannot publish an existing ' + name, status=code)
    for queued in (second, third):
        code, response, _ = cancel(queued)
        check(code == 200 and response['state'] == 'cancelled', 'Queued cancellation is terminal')
        check(not (ROOT / 'runs' / queued / 'worker.log').exists(), 'Cancelled queued job never starts a worker')
    code, response, _ = cancel(first)
    _, alive = psutil.wait_procs(suspended, timeout=10)
    check(code == 200 and response['state'] == 'cancelled' and not alive, 'Running cancellation kills the exact owned suspended process tree')
    check(cancel(first)[1]['state'] == 'cancelled', 'Repeated cancellation is idempotent')
    for name in ('output.obj', 'mesh.json', 'features.json'):
        check(request('/api/jobs/' + first + '/' + name)[0] == 409, 'Cancelled job cannot publish leftover ' + name)
    check(request('/api/jobs/' + first + '/curves.json')[0] == 200, 'Cancelled job retains inspectable submitted guides')
    check(request('/api/health')[0] == 200, 'Queue cancellation leaves the server healthy')

    _, model, _ = request('/api/mesh/toilet')
    fresh = start(model['presets'][0]['curves'])
    completed = wait_terminal(fresh)
    check(completed['state'] == 'complete', 'Fresh real toilet generation succeeds after queue saturation and cancellation')
    if completed['state'] == 'complete':
        code, obj, headers = request('/api/jobs/' + fresh + '/output.obj')
        _, report, _ = request('/api/jobs/' + fresh + '/report.json')
        check(code == 200 and hashlib.sha256(obj).hexdigest() == report['outputSha256'], 'Accepted download matches the actual worker output hash')
        check('attachment' in headers.get('Content-Disposition', ''), 'Accepted OBJ is served as an attachment')
        check(cancel(fresh)[1]['state'] == 'complete', 'Late cancellation cannot undo a completed accepted job')
    failed = start([[[10, 10, 10], [10.1, 10, 10]]])
    check(wait_terminal(failed)['state'] == 'failed', 'A real unresolvable guide fails after the successful job')
    for name in ('mesh.json', 'output.obj', 'features.json'):
        (ROOT / 'runs' / failed / name).write_text('unaccepted failed-worker residue')
        check(request('/api/jobs/' + failed + '/' + name)[0] == 409, 'Failed job cannot publish residual ' + name)
    check(request('/api/jobs/' + failed + '/report.json')[0] == 200, 'Failed job exposes its actual diagnostic report')
except Exception:
    errors.append(traceback.format_exc()); print(errors[-1], flush=True)
finally:
    for job in jobs:
        cancel(job)
    for child in psutil.Process(server.pid).children(recursive=True):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    server.terminate(); server.wait(timeout=20); log.close()
    report = dict(passed=not errors and all(c['passed'] for c in checks), checks=checks, errors=errors, workerJobs=jobs,
                  sourceHashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['server.py', 'worker.py', 'tests/verify_toilet_api.py']},
                  scope='Actual localhost HTTP requests, actual owned worker/queue lifecycle and a fresh toilet solve. Publication race uses explicitly unaccepted planted files in only this test server job directories.')
    (OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=report['passed'], checks=len(checks), failures=[c['name'] for c in checks if not c['passed']])), flush=True)
sys.exit(0 if report['passed'] else 1)
