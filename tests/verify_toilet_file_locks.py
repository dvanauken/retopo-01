"""Actual Windows exclusive file handles against a real toilet worker and HTTP API."""
import argparse
import contextlib
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid
import psutil

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
args = parser.parse_args()
if os.name != 'nt' or not args.label.replace('-', '').isalnum():
    raise ValueError('Windows and a plain evidence label are required')
OUT = ROOT / 'tests/toilet-file-locks' / args.label
OUT.mkdir(parents=True, exist_ok=True)
files = ['server.py', 'worker.py', 'process_ownership.py', 'tests/verify_toilet_file_locks.py']
hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in files}
checks, errors, observed, jobs = [], [], [], []
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
url = f'http://127.0.0.1:{port}'


def http(path, body=None):
    req = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def check(value, name, **details):
    checks.append(dict(passed=bool(value), name=name, **details))
    print(('PASS ' if value else 'FAIL ') + name, flush=True)


@contextlib.contextmanager
def exclusive(path):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    deadline = time.monotonic() + 10
    while True:
        # GENERIC_READ | GENERIC_WRITE, no sharing, OPEN_ALWAYS.
        handle = kernel.CreateFileW(str(path), 0xC0000000, 0, None, 4, 0x80, None)
        if handle != ctypes.c_void_p(-1).value:
            break
        if time.monotonic() >= deadline:
            raise ctypes.WinError(ctypes.get_last_error())
        time.sleep(.02)
    try:
        yield
    finally:
        kernel.CloseHandle(handle)


def survivors():
    remaining = []
    for record in observed:
        try:
            process = psutil.Process(record['pid'])
            if process.is_running() and process.create_time() == record['created']:
                remaining.append(process.pid)
        except psutil.NoSuchProcess:
            pass
    return remaining


log = (OUT / 'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([sys.executable, '-X', 'utf8', 'server.py', '--port', str(port)], cwd=ROOT,
                          stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW,
                          env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'))
try:
    deadline = time.monotonic() + 30
    while True:
        try:
            if http('/api/health')[0] == 200:
                break
        except OSError:
            pass
        if time.monotonic() >= deadline or server.poll() is not None:
            raise RuntimeError('Isolated server did not start')
        time.sleep(.05)
    payload = dict(meshId='toilet', target=1800, guideMode=2, curves=[])
    request_id = uuid.uuid4().hex
    _, active = http('/api/remesh', dict(payload, requestId=request_id))
    jobs.append(active['id'])
    deadline = time.monotonic() + 50
    while time.monotonic() < deadline:
        children = psutil.Process(server.pid).children(recursive=True)
        workers = [p for p in children if 'worker.py' in ' '.join(p.cmdline())]
        if workers and any('blender' in p.name().lower() for p in children):
            owned = {p.pid: p for worker in workers for p in [worker, *worker.children(recursive=True)]}
            observed = [dict(pid=p.pid, created=p.create_time(), command=p.cmdline()) for p in owned.values()]
            break
        time.sleep(.025)
    if not observed:
        raise AssertionError('No live real toilet worker and Blender child')
    check(True, 'File locks are injected only after the actual toilet worker and Blender child exist', processes=observed)
    folder = ROOT / 'runs' / active['id']
    with exclusive(folder / 'progress.json'):
        for _ in range(3):
            status, current = http('/api/jobs/' + active['id'])
            check(status == 200 and current['state'] == 'running' and bool(current['stage']),
                  'Exclusive progress lock preserves structured running status', response=current)
    _, queued = http('/api/remesh', dict(payload, requestId=uuid.uuid4().hex))
    jobs.append(queued['id'])
    if queued['state'] != 'queued':
        raise AssertionError('Queued cancellation precondition did not hold')
    with exclusive(ROOT / 'runs' / queued['id'] / 'cancel-request.json'), exclusive(ROOT / 'runs' / queued['id'] / 'execution.json'):
        status, cancelled = http('/api/jobs/' + queued['id'] + '/cancel', {})
        check(status == 200 and cancelled['state'] == 'cancelled', 'Locked queued diagnostics do not prevent cancellation')
    with exclusive(folder / 'cancel-request.json'):
        status, cancelled = http('/api/requests/' + request_id + '/cancel', {})
        check(status == 200 and cancelled['state'] == 'cancelled', 'Locked cancellation log does not prevent running request cancellation')
    deadline = time.monotonic() + 10
    while survivors() and time.monotonic() < deadline:
        time.sleep(.05)
    check(not survivors(), 'Real worker and Blender exit despite the diagnostic write lock', survivors=survivors())
    time.sleep(.3)
    check(not (ROOT / 'runs' / queued['id'] / 'worker.log').exists(), 'Cancelled queued work never launches after the active worker exits')
    for name in ('mesh.json', 'output.obj', 'features.json'):
        status, _ = http('/api/jobs/' + active['id'] + '/' + name)
        check(status == 409, 'Cancelled job cannot publish ' + name)
    status, response = http('/api/remesh', dict(payload, curves=[[[10 ** 4000, 0, 0], [0, 0, 0]]]))
    check(status == 400 and 'finite XYZ' in response['error'], 'Huge JSON integer coordinate is rejected with structured HTTP 400')
    check(all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in hashes.items()), 'Implementation remains fixed during real file-lock testing')
except Exception:
    errors.append(traceback.format_exc())
    print(errors[-1], flush=True)
finally:
    for job in jobs:
        try:
            http('/api/jobs/' + job + '/cancel', {})
        except OSError:
            pass
    if server.poll() is None:
        server.kill()
    server.wait(timeout=15)
    log.close()
    report = dict(passed=not errors and all(c['passed'] for c in checks), checks=checks, errors=errors,
                  sourceHashes=hashes, observedProcesses=observed,
                  scope='Actual Windows exclusive handles against progress and cancellation files during real HTTP/worker execution. No mocked server, process or geometry result.')
    (OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(passed=report['passed'], checks=len(checks))), flush=True)
raise SystemExit(0 if report['passed'] else 1)
