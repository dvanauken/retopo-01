"""Real Generate, exported geometry, changed guides, failure and owned cancellation."""
from pathlib import Path
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request

import numpy as np
import psutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests/toilet-retopology'
OUT.mkdir(exist_ok=True)
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
from measure_geometry import guide_alignment, read_obj, topology
from mesh_validation import validate_closed, links
from quad_quality import measure

checks, errors, jobs = [], [], []


def check(condition, name):
    checks.append({'name': name, 'passed': bool(condition)})
    print(('PASS ' if condition else 'FAIL ') + name, flush=True)
    if not condition:
        raise AssertionError(name)


def get(path):
    return json.load(urllib.request.urlopen(url + path, timeout=10))


def post(path, data):
    request = urllib.request.Request(url + path, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(request, timeout=10))


def solve(curves):
    job = post('/api/remesh', {'meshId': 'toilet', 'target': 1800, 'guideMode': 2, 'curves': curves})
    jobs.append(job['id'])
    for _ in range(600):
        result = get('/api/jobs/' + job['id'])
        if result['state'] in ('complete', 'failed', 'cancelled'):
            return result
        time.sleep(.3)
    raise TimeoutError(job['id'])


def retain(job, name):
    destination = OUT / name
    destination.mkdir(exist_ok=True)
    for filename in ('curves.json', 'settings.json', 'output.obj', 'mesh.json', 'report.json', 'execution.json',
                     'quality.json', 'engine-provenance.json', 'surface-solver.json', 'worker.log', 'quadri-layout-0.log'):
        source = ROOT / 'runs' / job / filename
        if source.exists():
            shutil.copyfile(source, destination / filename)


with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
url = f'http://127.0.0.1:{port}'
log = (OUT / 'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([sys.executable, '-X', 'utf8', str(ROOT / 'server.py'), '--port', str(port)], cwd=ROOT,
                          stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
try:
    for _ in range(100):
        try:
            get('/api/health'); break
        except Exception:
            time.sleep(.1)
    model = get('/api/mesh/toilet')
    curve = model['presets'][0]['curves'][0]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1700, 'height': 1050}, accept_downloads=True)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(url, wait_until='networkidle')
        page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
        page.locator('#meshSelect').select_option('toilet')
        page.wait_for_function('window.retopoDemo.getState().meshId==="toilet"')
        check(page.locator('#targetNumber').input_value() == '1800', 'Toilet retains the requested 1800-quad target')
        check('fails' not in page.locator('#solverNote').inner_text(), 'Toilet exposes its working solver instead of the obsolete failure notice')
        page.locator('#generateButton').click()
        page.wait_for_function('!window.retopoDemo.getState().busy', timeout=240000)
        state = page.evaluate('window.retopoDemo.getState()')
        check(state.get('resultJob') and state.get('resultFaces', 0) > 0, 'Actual browser Generate completes a fresh toilet worker')
        guided_id = state['resultJob']; jobs.append(guided_id)
        folder = ROOT / 'runs' / guided_id
        report = json.loads((folder / 'report.json').read_text())
        output = json.loads((folder / 'mesh.json').read_text())
        submitted = json.loads((folder / 'curves.json').read_text())
        check(report['passed'] and submitted['curves'] == state['guides'], 'Successful worker uses the exact current browser-submitted guide samples')
        check(output['backend'] == 'engineering-guided-surface-quads', 'Generated result identifies the new engineering surface solver')
        check(output['quadPercent'] == 100 and output['quality']['passed'], 'Every exported face is a quad and the unchanged shape limits pass')
        check(abs(output['stats']['faces'] - 1800) / 1800 <= .15, 'Actual face count stays within the existing target tolerance')
        check(page.locator('#resultBadge').inner_text() == 'Generated' and page.locator('#topologyMetric').inner_text() == 'Good', 'UI reports Generated and Good only after measured acceptance')
        check(page.locator('#resultEmpty').is_hidden() and page.locator('#exportMesh').is_enabled(), 'Accepted toilet geometry replaces the empty result and enables export')
        with page.expect_download() as download:
            page.locator('#exportMesh').click()
        exported = OUT / 'downloaded-toilet.obj'
        download.value.save_as(exported)
        check(hashlib.sha256(exported.read_bytes()).hexdigest() == report['outputSha256'], 'Browser OBJ download contains the actual successful worker output')
        page.screenshot(path=str(OUT / 'generated-toilet-light.png'))
        page.locator('#themeButton').click()
        check(page.evaluate('window.retopoDemo.getState().sourceMaterial.color') == 'f5f5f2', 'Original white toilet material survives switching host themes')
        page.screenshot(path=str(OUT / 'generated-toilet-dark.png'))
        page.locator('#themeButton').click()
        browser.close()
    vertices, faces = read_obj(exported)
    stats, _, output_edges = topology(vertices, faces)
    check(stats['faceConnectedComponents'] == 1 and stats['boundaryEdges'] == 0 and stats['eulerCharacteristic'] == 0,
          'Independent OBJ reading confirms one closed component and the original genus')
    stars = links(faces)
    check(not stars['nonmanifoldVertices'] and stars['inconsistentWindingEdges'] == 0, 'Independent vertex-link and winding checks pass')
    quality = measure(vertices, faces, 1800)
    check(quality['passed'] and quality['scaledJacobianMin'] >= .45, 'Independent OBJ shape measurements confirm no failed quad-quality limits')
    source_v, source_f = read_obj(ROOT / 'assets/models/toilet.obj')
    reference_validation = validate_closed(source_v, source_f, vertices, faces, target=1800)
    check(reference_validation['passed'], 'Unmodified reference surface/topology validator independently accepts the exported toilet')
    check(output['surfaceValidation']['checks'] == reference_validation['checks'], 'Indexed surface validation agrees with the original independent validator')
    path = output['guidePaths'][0]['vertices']; actual_edges = {tuple(sorted(edge)) for edge in output_edges}
    check(path[0] == path[-1] and len(set(path[:-1])) == len(path)-1 and all(tuple(sorted(pair)) in actual_edges for pair in zip(path[:-1], path[1:])),
          'Tracked guide is a simple closed chain of actual exported quad edges')
    c = np.asarray(submitted['curves'][0]); arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))]
    samples = np.array([np.interp(np.linspace(0, arc[-1], 257), arc, c[:, i]) for i in range(3)]).T
    fit = guide_alignment(vertices, list(zip(path[:-1], path[1:])), samples)
    spacing = output['surfaceValidation']['sampledSurfaceTolerance'] * 2
    check(fit['p95Distance'] <= .2 * spacing and fit['p95UnsignedTangentAngleDegrees'] <= 30, 'Independent guide-path distance and direction pass the existing acceptance limits')
    retain(guided_id, 'guided')
    baseline = solve([])
    check(baseline['state'] == 'complete', 'The same toilet can also generate without guides')
    base = get(baseline['resultUrl']); baseline_folder = ROOT / 'runs' / baseline['id']
    check(base['faces'] == output['faces'] and base['vertices'] != output['vertices'], 'The guide changes actual exported geometry while retaining the same quad layout')
    base_alignment = guide_alignment(np.asarray(base['vertices']), output_edges, samples)
    check(fit['p95Distance'] < base_alignment['p95Distance'] and fit['p95UnsignedTangentAngleDegrees'] < base_alignment['p95UnsignedTangentAngleDegrees'],
          'Guidance improves measured distance and direction over a same-target unguided solve')
    retain(baseline['id'], 'unguided')
    changed = solve([curve[30:150]])
    check(changed['state'] == 'complete', 'A different open guide completes a fresh solve on the imported source')
    changed_mesh = get(changed['resultUrl'])
    check(changed_mesh['guidePaths'][0]['vertices'][0] != changed_mesh['guidePaths'][0]['vertices'][-1] and changed_mesh['vertices'] != output['vertices'],
          'Open-guide semantics and changed authored input produce a different fitted result')
    retain(changed['id'], 'open-guide')
    rejected = solve([[[10, 10, 10], [10.1, 10, 10]]])
    bad_folder = ROOT / 'runs' / rejected['id']
    check(rejected['state'] == 'failed' and not (bad_folder / 'output.obj').exists() and not (bad_folder / 'mesh.json').exists(),
          'An unresolvable guide still fails without promoting or exporting a candidate')
    retain(rejected['id'], 'rejected-guide')
    cancelling = post('/api/remesh', {'meshId': 'toilet', 'target': 1800, 'guideMode': 2, 'curves': [curve]})
    jobs.append(cancelling['id']); descendants = []
    for _ in range(200):
        descendants = [child for child in psutil.Process(server.pid).children(recursive=True) if 'blender' in child.name().lower()]
        if descendants:
            break
        time.sleep(.05)
    check(bool(descendants), 'Cancellation test observes the actual owned Blender child process')
    cancelled = post('/api/jobs/' + cancelling['id'] + '/cancel', {})
    _, alive = psutil.wait_procs(descendants, timeout=10)
    check(cancelled['state'] == 'cancelled' and not alive, 'Cancelling the calculation terminates its owned layout process')
    check(get('/api/health')['ready'], 'Cancelling the calculation leaves the application server healthy')
    check(not errors, 'No browser JavaScript errors during real generation and export')
    files = ['curved_quad.py', 'scripts/quadriflow_mesh.py', 'server.py', 'worker.py', 'quad_quality.py', 'app.js', 'assets/models/toilet.json', 'assets/models/toilet.obj']
    (OUT / 'result.json').write_text(json.dumps({'passed': True, 'checks': checks, 'browserErrors': errors, 'workerJobs': jobs,
        'guidedFaces': len(faces), 'guideFit': fit, 'unguidedAlignment': base_alignment, 'independentValidation': reference_validation,
        'sourceHashes': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
        'scope': 'Actual Chromium Generate and OBJ download, independently reread output, unmodified reference validation, fresh unguided and changed-open-guide solves, rejected input and owned child cancellation.'}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'checks': len(checks), 'faces': len(faces), 'guideP95': fit['p95Distance']}), flush=True)
except Exception:
    (OUT / 'result.json').write_text(json.dumps({'passed': False, 'checks': checks, 'browserErrors': errors, 'jobs': jobs, 'error': traceback.format_exc()}, indent=2) + '\n', encoding='utf-8')
    raise
finally:
    for job in jobs:
        try:
            post('/api/jobs/' + job + '/cancel', {})
        except Exception:
            pass
    server.terminate(); server.wait(timeout=20); log.close()
