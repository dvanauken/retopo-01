"""Toilet regression matrix and real browser failure/retry/IO checks.

The two captured inputs are the user's previously failed requests. Exploratory
density cases report acceptance or rejection; rejection is never called a solve.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request

# Keep numerical tests from oversubscribing this interactive workstation.
for variable in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'
import numpy as np
import psutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tests/toilet-stress'
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj, topology, guide_alignment
from mesh_validation import links
from quad_quality import measure
from curved_quad import validate_surface
from surface_intersections import measure as intersections

parser = argparse.ArgumentParser()
parser.add_argument('--ui-only', action='store_true')
parser.add_argument('--matrix-only', action='store_true')
args = parser.parse_args()
checks, jobs, errors, matrix = [], [], [], []


def check(value, name):
    checks.append(dict(name=name, passed=bool(value)))
    print(('PASS ' if value else 'FAIL ') + name, flush=True)
    return bool(value)


def get(path):
    return json.load(urllib.request.urlopen(url + path, timeout=15))


def post(path, data):
    request = urllib.request.Request(url + path, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(request, timeout=15))


def wait(job):
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        result = get('/api/jobs/' + job)
        if result['state'] in ('complete', 'failed', 'cancelled'):
            return result
        time.sleep(.3)
    raise TimeoutError(job)


def retain(job, name):
    folder = ROOT / 'runs' / job
    destination = OUT / name
    assert destination.resolve().is_relative_to(OUT.resolve())
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ('curves.json', 'settings.json', 'report.json', 'output.obj', 'mesh.json',
                     'surface-solver.json', 'surface-solver-failure.json', 'worker.log'):
        if (folder / filename).exists():
            shutil.copyfile(folder / filename, destination / filename)
        else:
            (destination / filename).unlink(missing_ok=True)


def inspect(job, curves, target, name):
    folder = ROOT / 'runs' / job['id']
    report = json.loads((folder / 'report.json').read_text())
    record = dict(name=name, job=job['id'], target=target, guideCount=len(curves), state=job['state'],
                  elapsedSeconds=report['elapsedSeconds'], message=report.get('message'))
    if job['state'] == 'complete':
        v, f = read_obj(folder / 'output.obj')
        packet = json.loads((folder / 'mesh.json').read_text())
        stats, _, edges = topology(v, f)
        surface = validate_surface(source_v, source_f, v, np.asarray(f), target)
        quality = measure(v, f, target)
        crossing = intersections(v, f)
        check(crossing['passed'] and packet['intersectionValidation']['passed'], name + ': no non-adjacent polygon crossings detected in exported geometry')
        star = links(f)
        valid_edges = {tuple(sorted(e)) for e in edges}
        fits = []
        for curve, path in zip(curves, packet['guidePaths']):
            ids = path['vertices']
            closed = np.linalg.norm(np.asarray(curve[0]) - curve[-1]) < 1e-8
            unique = ids[:-1] if closed else ids
            check((ids[0] == ids[-1]) == closed and len(set(unique)) == len(unique)
                  and all(tuple(sorted(e)) in valid_edges for e in zip(ids[:-1], ids[1:])),
                  name + ': guide tracks a simple actual output-edge path with correct closure')
            c = np.asarray(curve); arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))]
            samples = np.array([np.interp(np.linspace(0, arc[-1], 257), arc, c[:, i]) for i in range(3)]).T
            fit = guide_alignment(v, list(zip(ids[:-1], ids[1:])), samples)
            fits.append(fit)
            check(fit['p95Distance'] <= .4 * surface['sampledSurfaceTolerance']
                  and fit['p95UnsignedTangentAngleDegrees'] <= 30, name + ': independently measured guide distance and tangent pass')
        check(len(packet['guidePaths']) == len(curves), name + ': every submitted guide has a measured path')
        check(quality['passed'] and surface['passed'] and not star['nonmanifoldVertices']
              and not star['inconsistentWindingEdges'] and stats['quadFraction'] == 1,
              name + ': reread OBJ passes unchanged quad, topology and bidirectional surface limits')
        record.update(faces=len(f), guideFit=fits, surface=surface, quality=quality, intersections=crossing, outputSha256=report['outputSha256'])
    else:
        check(not (folder / 'output.obj').exists() and not (folder / 'mesh.json').exists(),
              name + ': rejected candidate is not exported or promoted')
    retain(job['id'], name)
    matrix.append(record)
    print('OUTCOME ' + name + ': ' + job['state'], flush=True)
    return record


def solve(name, curves, target=1800, required=False):
    job = post('/api/remesh', dict(meshId='toilet', target=target, guideMode=2, curves=curves))
    jobs.append(job['id'])
    result = inspect(wait(job['id']), curves, target, name)
    if required:
        check(result['state'] == 'complete', name + ': required regression generates an accepted mesh')
    return result


with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
url = f'http://127.0.0.1:{port}'
log = (OUT / ('ui-server.log' if args.ui_only else 'matrix-server.log')).open('w', encoding='utf-8')
server = subprocess.Popen([sys.executable, '-X', 'utf8', str(ROOT / 'server.py'), '--port', str(port)], cwd=ROOT,
                          stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
try:
    for _ in range(100):
        try:
            get('/api/health'); break
        except Exception:
            time.sleep(.1)
    source_v, source_f = read_obj(ROOT / 'assets/models/toilet.obj')
    source_f = np.asarray(source_f)
    model = get('/api/mesh/toilet')
    short = json.loads((OUT / 'inputs/bowl-and-lid-short/curves.json').read_text())['curves']
    long = json.loads((OUT / 'inputs/bowl-and-lid-long/curves.json').read_text())['curves']
    if not args.ui_only:
        first = solve('two-guides-short-1800', short, required=True)
        solve('two-guides-long-1800', long, required=True)
        repeat = solve('two-guides-short-repeat', short, required=True)
        check(first.get('outputSha256') and first.get('outputSha256') == repeat.get('outputSha256'),
              'Repeated identical input produces the same accepted OBJ')
        solve('bowl-only-1800', [long[0]], required=True)
        solve('lid-only-1800', [long[1]])
        solve('unguided-1800', [], required=True)
        for density in (1200, 600, 150):
            solve(f'two-guides-{density}', long, density)
        solve('off-surface-rejected', [[[10, 10, 10], [10.1, 10, 10]]])
        (OUT / 'matrix.json').write_text(json.dumps(dict(checks=checks, cases=matrix), indent=2) + '\n')
    if not args.matrix_only:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1700, 'height': 1050}, accept_downloads=True)
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(url, wait_until='networkidle')
            page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')

            def state():
                return page.evaluate('window.retopoDemo.getState()')

            def toilet():
                page.locator('#meshSelect').select_option('toilet')
                page.wait_for_function('window.retopoDemo.getState().meshId==="toilet"')

            def upload(curves):
                payload = dict(coordinateFrame='source', sourceSha256=model['sourceSha256'], curves=curves)
                page.locator('#guideFile').set_input_files(dict(name='toilet-guides.json', mimeType='application/json', buffer=json.dumps(payload).encode()))
                page.wait_for_function('(n)=>window.retopoDemo.getState().guides.length===n', arg=len(curves))

            toilet()
            check(not state()['resultGuideOverlayVisible'] and page.locator('#resultEmpty').is_visible(),
                  'Empty toilet result does not display floating guide curves')
            check(all(page.locator('#' + key).is_disabled() for key in ('halfButton', 'sameButton', 'doubleButton')),
                  'Unsupported source-relative densities are disabled instead of clamped')
            for value in ('24000', '149'):
                page.locator('#targetNumber').fill(value); page.locator('#targetNumber').press('Tab')
                check(state()['target'] == 1800 and page.locator('#targetNumber').input_value() == '1800',
                      'Out-of-range target ' + value + ' leaves the actual target unchanged')
            upload(short)
            before = state()['guideDocument']
            with page.expect_download() as download:
                page.locator('#exportGuides').click()
            native = OUT / 'two-guide-roundtrip.json'; download.value.save_as(str(native))
            page.locator('#clearButton').click()
            page.locator('#guideFile').set_input_files(str(native))
            page.wait_for_function('window.retopoDemo.getState().guides.length===2')
            check(state()['guideDocument'] == before, 'Save/load preserves both authored guides and their IDs')
            check(np.allclose(state()['guides'][0], short[0]) and np.allclose(state()['guides'][1], short[1]),
                  'Browser import retains the exact two shorter user-submitted surface paths')

            # A real under-resolved request tests failure, with no mocked API.
            page.locator('#targetNumber').fill('150'); page.locator('#targetNumber').press('Tab')
            page.locator('#generateButton').click()
            page.wait_for_function('!window.retopoDemo.getState().busy', timeout=240000)
            check(state()['lastAttempt']['phase'] == 'failed' and not state()['resultJob']
                  and page.locator('#resultEmptyTitle').inner_text() == 'Last generation failed',
                  'Real worker failure has a persistent explanation in the empty result pane')
            failure = page.locator('#resultEmptyDetail').inner_text()
            page.locator('#targetNumber').fill('1700'); page.locator('#targetNumber').press('Tab')
            page.locator('#guidesToggle').uncheck(); page.locator('#guidesToggle').check()
            page.locator('#themeButton').click()
            check(page.locator('#resultEmptyDetail').inner_text() == failure and not state()['resultGuideOverlayVisible'],
                  'Density, display and theme changes neither erase failure nor create a floating result')
            page.screenshot(path=str(OUT / 'failed-toilet-dark.png'))
            page.locator('[data-view=overlay]').click()
            check(page.locator('#generationFeedback').is_visible(), 'Failure remains visible in overlay view')
            page.locator('[data-view=split]').click()
            page.evaluate('''()=>{const key='retopo-1:toilet',saved=JSON.parse(localStorage.getItem(key));saved.target=24000;localStorage.setItem(key,JSON.stringify(saved));}''')
            page.reload(wait_until='networkidle'); page.wait_for_function('window.retopoDemo?.getState().meshId==="hexagon"')
            toilet()
            check(state()['target'] == 1800, 'Invalid persisted density cannot bypass the supported range')
            check(state()['lastAttempt']['phase'] == 'failed' and page.locator('#resultEmptyDetail').inner_text() == failure,
                  'Reloading and returning to the same source restores its last failure')
            page.locator('#themeButton').click()

            # Retry with actual saved guides, then cancel an owned Blender child.
            page.locator('#guideFile').set_input_files(str(native))
            page.wait_for_function('window.retopoDemo.getState().guides.length===2')
            page.locator('#targetNumber').fill('1800'); page.locator('#targetNumber').press('Tab')
            page.locator('#generateButton').click()
            descendants = []
            cancel_deadline = time.monotonic() + 60
            while time.monotonic() < cancel_deadline:
                descendants = [c for c in psutil.Process(server.pid).children(recursive=True) if 'blender' in c.name().lower()]
                if descendants:
                    break
                page.wait_for_timeout(50)
            check(bool(descendants), 'Browser cancellation observes a real owned Blender process')
            page.locator('#cancelButton').click()
            page.wait_for_function('!window.retopoDemo.getState().busy')
            _, alive = psutil.wait_procs(descendants, timeout=10)
            check(bool(descendants) and not alive and state()['lastAttempt']['phase'] == 'cancelled'
                  and page.locator('#resultEmptyTitle').inner_text() == 'Generation cancelled',
                  'Cancel terminates owned work and clearly labels the result pane')
            page.locator('#generateButton').click()
            page.wait_for_function('!window.retopoDemo.getState().busy', timeout=300000)
            s = state(); accepted = bool(s['resultJob']) and s['lastAttempt']['phase'] == 'complete'
            check(accepted, 'Retry after failure and cancellation accepts both user guides')
            if accepted:
                job = get('/api/jobs/' + s['resultJob']); jobs.append(job['id'])
                inspect(job, s['guides'], 1800, 'browser-two-guides')
                check(s['resultGuideOverlayVisible'] and page.locator('#generationFeedback').is_hidden()
                      and page.locator('#resultEmpty').is_hidden(), 'Success replaces failure feedback and shows guides on an accepted mesh')
                with page.expect_download() as download:
                    page.locator('#exportMesh').click()
                exported = OUT / 'browser-two-guides.obj'; download.value.save_as(str(exported))
                check(hashlib.sha256(exported.read_bytes()).hexdigest() == json.loads((ROOT / 'runs' / job['id'] / 'report.json').read_text())['outputSha256'],
                      'Browser export is the exact accepted two-guide output')
                page.screenshot(path=str(OUT / 'two-guides-generated-light.png'))
                old_job = s['resultJob']
                page.locator('#targetNumber').fill('150'); page.locator('#targetNumber').press('Tab')
                page.locator('#generateButton').click(); page.wait_for_function('!window.retopoDemo.getState().busy', timeout=240000)
                check(state()['resultJob'] == old_job and page.locator('#generationFeedback').is_visible()
                      and 'previous accepted result' in page.locator('#generationFeedback').inner_text(),
                      'A failed replacement retains and explicitly labels the previous accepted result')
                page.screenshot(path=str(OUT / 'failed-replacement-retains-mesh.png'))
            # A different primitive, authored through real canvas clicks on the lid.
            page.locator('#targetNumber').fill('1800'); page.locator('#targetNumber').press('Tab')
            page.locator('#clearButton').click(); page.locator('#topButton').click()
            page.locator('[data-tool=circle]').click()
            for point in ([0, -.55, .22], [.20, -.55, .22]):
                xy = page.evaluate('(p)=>window.retopoDemo.projectPoint(p)', point)
                page.mouse.click(xy['x'], xy['y'])
            check(len(state()['guideDocument']) == 1 and state()['guideDocument'][0]['type'] == 'circle',
                  'A real Circle primitive can be authored on the toilet lid')
            page.locator('#generateButton').click(); page.wait_for_function('!window.retopoDemo.getState().busy', timeout=300000)
            last = state()
            if last['lastAttempt']['phase'] == 'complete':
                job = get('/api/jobs/' + last['resultJob']); jobs.append(job['id'])
                inspect(job, last['guides'], 1800, 'browser-lid-circle')
            else:
                matrix.append(dict(name='browser-lid-circle', target=1800, guideCount=1, state='failed', message=last['lastAttempt']['message']))
                check(page.locator('#generationFeedback').is_visible() or page.locator('#resultEmpty').is_visible(),
                      'Rejected Circle has explicit feedback')
            check(not errors, 'No browser JavaScript errors across toilet workflows')
            browser.close()
except Exception:
    errors.append(traceback.format_exc())
    print(errors[-1], flush=True)
finally:
    for job in jobs:
        try:
            post('/api/jobs/' + job + '/cancel', {})
        except Exception:
            pass
    descendants = psutil.Process(server.pid).children(recursive=True)
    for child in descendants:
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    server.terminate(); server.wait(timeout=20); log.close()
    files = ['app.js', 'index.html', 'index.css', 'curved_quad.py', 'worker.py', 'server.py', 'quad_quality.py',
             'scripts/quadriflow_mesh.py', 'surface_intersections.py', 'assets/models/toilet.obj', 'tests/verify_toilet_stress.py']
    result = dict(passed=all(c['passed'] for c in checks) and not errors, checks=checks, cases=matrix, errors=errors,
                  sourceHashes={f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files},
                  scope='Fresh original toilet geometry and exact saved user inputs. Accepted exports are remeasured; exploratory density rejection is reported separately from successful generation.')
    filename = 'ui-result.json' if args.ui_only else 'matrix-result.json' if args.matrix_only else 'result.json'
    (OUT / filename).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'], checks=len(checks), accepted=sum(c['state'] == 'complete' for c in matrix), rejected=sum(c['state'] == 'failed' for c in matrix))), flush=True)
sys.exit(0 if result['passed'] else 1)
