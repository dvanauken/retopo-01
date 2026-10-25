"""Generate and download real captured toilet results through the browser."""
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
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from process_ownership import protect_service_tree

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--cases', nargs='+', default=['two-guides-short-1800', 'browser-lid-circle'])
args = parser.parse_args()
if any(not name.replace('-', '').isalnum() for name in [args.label, *args.cases]):
    raise ValueError('Use plain labels')
protect_service_tree()
OUT = ROOT / 'tests/toilet-fallback-browser' / args.label
OUT.mkdir(parents=True, exist_ok=False)
(OUT / 'executed-test.py').write_bytes(Path(__file__).read_bytes())
files = ['app.js', 'server.py', 'worker.py', 'curved_quad.py', 'surface_guide_refine.py', 'surface_guide_repair.py', 'surface_guide_joint.py',
         'surface_distance.py', 'surface_intersections.py', 'quad_quality.py', 'assets/models/toilet.obj',
         'tests/verify_toilet_fallback_browser.py']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
hashes = {name: sha(ROOT / name) for name in files}
checks, cases, errors = [], [], []
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
url = f'http://127.0.0.1:{port}'
pointer = ROOT / 'runs/server.json'
old_pointer = pointer.read_bytes() if pointer.exists() else None
started = time.monotonic()
log = (OUT / 'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([sys.executable, '-X', 'utf8', 'server.py', '--port', str(port)], cwd=ROOT,
                          stdout=log, stderr=log, env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'),
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def check(value, name, **detail):
    checks.append(dict(passed=bool(value), name=name, **detail))
    print(('PASS ' if value else 'FAIL ') + name, flush=True)


def http(path):
    with urllib.request.urlopen(url + path, timeout=15) as response:
        return json.load(response)


def save(complete):
    (OUT / 'result.json').write_text(json.dumps(dict(complete=complete, passed=complete and not errors and all(c['passed'] for c in checks),
        productionResult=True, checks=checks, cases=cases, errors=errors, sourceHashes=hashes,
        implementationUnchanged=all(sha(ROOT / p) == h for p, h in hashes.items()), elapsedSeconds=time.monotonic() - started,
        scope='Fresh real browser imports, Generate actions, HTTP/worker solves, accepted viewport state and native OBJ downloads. No replaced network responses or saved candidate inputs. DPR1 limits software-rendering load.'), indent=2) + '\n', newline='\n')


try:
    deadline = time.monotonic() + 30
    while True:
        try:
            if http('/api/health')['ready']:
                break
        except OSError:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError('Test service startup failed')
        time.sleep(.1)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport=dict(width=1700, height=1050), device_scale_factor=1)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(url, wait_until='networkidle')
        page.wait_for_function('window.retopoDemo?.getState().resultFaces > 0')
        page.locator('#meshSelect').select_option('toilet')
        page.wait_for_function('window.retopoDemo.getState().meshId === "toilet" && !document.getElementById("generateButton").disabled')
        source = http('/api/mesh/toilet')
        for name in args.cases:
            curve_file = (ROOT / 'tests/toilet-paired-variants/sampling-and-density/short-small-perturbation/curves.json'
                          if name == 'short-small-perturbation' else ROOT / 'tests/toilet-stress' / name / 'curves.json')
            curves = json.loads(curve_file.read_text())['curves']
            packet = dict(coordinateFrame='source', sourceSha256=source['sourceSha256'], curves=curves)
            page.locator('#guideFile').set_input_files(dict(name='toilet-guides.json', mimeType='application/json', buffer=json.dumps(packet).encode()))
            page.wait_for_function('(n) => window.retopoDemo.getState().guides.length === n', arg=len(curves))
            page.locator('#targetNumber').fill('1800')
            page.locator('#targetNumber').press('Tab')
            before = page.evaluate('window.retopoDemo.getState().guideDocument')
            page.locator('#generateButton').click()
            deadline = time.monotonic() + 650
            previous = None
            while True:
                state = page.evaluate('window.retopoDemo.getState()')
                stage = page.locator('#processTitle').inner_text()
                if stage != previous:
                    print(name, stage.strip(), flush=True)
                    previous = stage
                if not state['busy']:
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError('Browser did not finish within service timeout allowance')
                page.wait_for_timeout(1000)
            case = dict(name=name, state=state['lastAttempt']['phase'], job=state['resultJob'], resultFaces=state['resultFaces'])
            cases.append(case)
            check(state['lastAttempt']['phase'] == 'complete' and bool(state['resultJob']), name + ' finishes in the browser with an accepted result', lastAttempt=state['lastAttempt'])
            if not state['resultJob'] or not state['resultFaces']:
                raise AssertionError('No accepted mesh in browser: ' + json.dumps(state['lastAttempt']))
            actual = http('/api/jobs/' + state['resultJob'])
            case['state'] = actual['state']
            case['elapsedSeconds'] = actual['finishedAt'] - actual['startedAt']
            check(actual['state'] == 'complete', name + ' viewport references a genuinely completed service job')
            retained = OUT / name
            retained.mkdir()
            job = ROOT / 'runs' / state['resultJob']
            for filename in ('curves.json', 'settings.json', 'report.json', 'output.obj', 'mesh.json', 'surface-solver.json', 'engine-provenance.json', 'worker.log'):
                shutil.copyfile(job / filename, retained / filename)
            for filename in ('sampled-guide-history.json', 'joint-guide-repair.json'):
                if (job / filename).exists():
                    shutil.copyfile(job / filename, retained / filename)
            check(state['guideDocument'] == before and not state['dirty'], name + ' preserves authored guides and clears the update badge')
            check(state['resultGuideOverlayVisible'] and page.locator('#generationFeedback').is_hidden(), name + ' replaces the empty-state panel with generated geometry')
            with page.expect_download() as event:
                page.locator('#exportMesh').click()
            event.value.save_as(str(retained / 'browser-export.obj'))
            check((retained / 'browser-export.obj').read_bytes() == (retained / 'output.obj').read_bytes(), name + ' browser download exactly matches the worker OBJ')
            mesh = json.loads((retained / 'mesh.json').read_text())
            check(mesh['surfaceValidation']['passed'] and mesh['intersectionValidation']['passed'] and mesh['quality']['passed'], name + ' downloaded result retains every geometry gate')
            case['outputSha256'] = sha(retained / 'output.obj')
            page.locator('#fitButton').click()
            page.screenshot(path=str(retained / 'accepted.png'))
            save(False)
        check(all(sha(ROOT / p) == h for p, h in hashes.items()), 'Implementation unchanged through actual browser solves')
        context.close()
        browser.close()
except Exception:
    errors.append(traceback.format_exc())
    print(errors[-1], flush=True)
finally:
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
