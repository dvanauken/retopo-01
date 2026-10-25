"""Run captured toilet inputs through an isolated real service and worker."""
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
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from process_ownership import protect_service_tree

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--cases', nargs='+', default=['two-guides-short-1800', 'bowl-only-1800'])
args = parser.parse_args()
if any(not x.replace('-', '').isalnum() for x in [args.label, *args.cases]):
    raise ValueError('Use plain labels')
protect_service_tree()
OUT = ROOT / 'tests/toilet-sampled-worker' / args.label
OUT.mkdir(parents=True, exist_ok=False)
(OUT / 'executed-probe.py').write_bytes(Path(__file__).read_bytes())
files = ['server.py', 'worker.py', 'curved_quad.py', 'surface_guide_refine.py', 'surface_guide_repair.py', 'surface_guide_joint.py',
         'surface_distance.py', 'surface_intersections.py', 'quad_quality.py', 'process_ownership.py',
         'assets/models/toilet.obj', 'assets/models/toilet.json', 'scripts/quadriflow_mesh.py',
         'tests/verify_toilet_sampled_worker.py']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
hashes = {p: sha(ROOT / p) for p in files}
checks, cases, errors = [], [], []
started = time.monotonic()
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
url = f'http://127.0.0.1:{port}'
pointer = ROOT / 'runs/server.json'
old_pointer = pointer.read_bytes() if pointer.exists() else None


def check(value, name, **details):
    checks.append(dict(passed=bool(value), name=name, **details))
    print(('PASS ' if value else 'FAIL ') + name, flush=True)


def http(path, body=None, binary=False):
    request = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read() if binary else json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def save(complete):
    unchanged = all(sha(ROOT / p) == h for p, h in hashes.items())
    report = dict(complete=complete, passed=complete and not errors and all(c['passed'] for c in checks),
                  productionResult=True, cases=cases, checks=checks, errors=errors, sourceHashes=hashes,
                  implementationUnchanged=unchanged, elapsedSeconds=time.monotonic() - started,
                  scope='Real HTTP admission, fresh original-source layout, ordinary production worker, export and retrieval. No saved candidate is an input. Geometry qualification comes from the worker; separate exported-OBJ audits are required.')
    (OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n', newline='\n')


log = (OUT / 'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([sys.executable, '-X', 'utf8', 'server.py', '--port', str(port)], cwd=ROOT,
                          stdout=log, stderr=log, env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'),
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
active = None
try:
    deadline = time.monotonic() + 30
    while True:
        try:
            if http('/api/health')[0] == 200:
                break
        except OSError:
            pass
        if time.monotonic() > deadline or server.poll() is not None:
            raise RuntimeError('Test service startup failed')
        time.sleep(.1)
    for name in args.cases:
        fixture = ROOT / 'tests/toilet-stress' / name
        curves = json.loads((fixture / 'curves.json').read_text())['curves']
        settings = json.loads((fixture / 'settings.json').read_text())
        code, job = http('/api/remesh', dict(requestId=uuid.uuid4().hex, meshId='toilet', target=settings['target'], guideMode=2, curves=curves))
        check(code == 202 and bool(job.get('id')), name + ' admitted by the real service')
        active = job['id']
        case = dict(name=name, job=active, state=job['state'], target=settings['target'], guideCount=len(curves))
        cases.append(case)
        deadline = time.monotonic() + 630
        previous = None
        while True:
            _, state = http('/api/jobs/' + active)
            stage = (state['state'], state['stage'])
            if stage != previous:
                print(name, *stage, flush=True)
                previous = stage
            if state['state'] in ('complete', 'failed', 'cancelled'):
                break
            if time.monotonic() > deadline:
                raise TimeoutError('Service did not reach its own terminal deadline')
            time.sleep(1)
        case.update(state=state['state'], elapsedSeconds=state['finishedAt'] - state['startedAt'], error=state.get('error'))
        folder = ROOT / 'runs' / active
        retained = OUT / name
        retained.mkdir()
        for filename in ('curves.json', 'settings.json', 'report.json', 'output.obj', 'mesh.json', 'surface-solver.json',
                         'surface-solver-failure.json', 'sampled-guide-history.json', 'joint-guide-repair.json', 'engine-provenance.json',
                         'worker.log', 'execution.json'):
            if (folder / filename).exists():
                shutil.copyfile(folder / filename, retained / filename)
        check(state['state'] == 'complete', name + ' produces an accepted mesh', state=state)
        if state['state'] == 'complete':
            _, exported = http('/api/jobs/' + active + '/output.obj', binary=True)
            check(exported == (retained / 'output.obj').read_bytes(), name + ' serves the exact accepted OBJ')
            report = json.loads((retained / 'report.json').read_text())
            meta = json.loads((retained / 'engine-provenance.json').read_text())
            mesh = json.loads((retained / 'mesh.json').read_text())
            case.update(outputSha256=sha(retained / 'output.obj'), fittingMethod=meta.get('fittingMethod'), seed=meta['layoutEngine']['seed'])
            check(report['outputSha256'] == case['outputSha256'] and mesh['quality']['passed'] and mesh['surfaceValidation']['passed']
                  and mesh['intersectionValidation']['passed'], name + ' preserves every production acceptance gate')
            check(len(mesh['guidePaths']) == len(curves), name + ' retains a measured output-edge path for every submitted guide')
            check(all(sha(Path(p)) == digest for p, digest in meta['sourceHashes'].items()), name + ' records exact executed numerical code')
        else:
            for filename in ('mesh.json', 'output.obj'):
                check(http('/api/jobs/' + active + '/' + filename)[0] == 409, name + ' rejects access to unqualified ' + filename)
        active = None
        save(False)
    check(all(sha(ROOT / p) == h for p, h in hashes.items()), 'Implementation unchanged throughout production regression')
except Exception:
    errors.append(traceback.format_exc())
    print(errors[-1], flush=True)
finally:
    if active:
        try:
            http('/api/jobs/' + active + '/cancel', {})
        except OSError:
            pass
    if server.poll() is None:
        server.kill()
    server.wait(timeout=15)
    log.close()
    if pointer.exists() and json.loads(pointer.read_text()).get('pid') == server.pid:
        if old_pointer is None:
            pointer.unlink()
        else:
            pointer.write_bytes(old_pointer)
    save(True)
raise SystemExit(0 if not errors and all(c['passed'] for c in checks) else 1)
