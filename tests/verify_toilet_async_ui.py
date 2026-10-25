"""Deterministic browser races using delayed responses from real workers.

No success/failure response is fabricated. The remesh request reaches an isolated
real server, then only its response delivery to the browser is held.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import traceback
import urllib.request
import psutil
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--label', default='current')
parser.add_argument('--scenarios', nargs='+')
args = parser.parse_args()
if not args.label.replace('-', '').isalnum():
    raise ValueError('Use a plain label')
OUT = ROOT / 'tests/toilet-async-ui' / args.label
OUT.mkdir(parents=True, exist_ok=True)
checks, errors, jobs = [], [], []


def check(value, name, **details):
    checks.append(dict(name=name, passed=bool(value), **details))
    print(('PASS ' if value else 'FAIL ') + name, flush=True)


def http(path, payload=None):
    request = urllib.request.Request(url + path, data=json.dumps(payload).encode() if payload is not None else None,
                                     headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(request, timeout=15))


async def cancel(job):
    return await asyncio.to_thread(http, '/api/jobs/' + job + '/cancel', {})


async def exercise(browser, scenario):
    context = await browser.new_context(viewport={'width': 1700, 'height': 1050})
    page = await context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    reply_ready, release_reply = asyncio.Event(), asyncio.Event()
    preview_ready, release_preview = asyncio.Event(), asyncio.Event()
    captured = {}
    captured_requests = []

    async def hold(route):
        response = await route.fetch()
        captured.update(await response.json())
        captured_requests.append(dict(captured))
        if 'id' not in captured:
            raise RuntimeError(captured)
        jobs.append(captured['id']); reply_ready.set()
        await release_reply.wait()
        try:
            await route.fulfill(response=response)
        except Exception as error:
            if scenario not in ('reset-before-response', 'reset-two-pending'):
                raise
            captured['deliveryError'] = str(error)

    async def state():
        return await page.evaluate('window.retopoDemo.getState()')

    try:
        await page.goto(url, wait_until='networkidle')
        await page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
        await page.locator('#meshSelect').select_option('toilet')
        await page.wait_for_function('window.retopoDemo.getState().meshId==="toilet"')
        if scenario == 'failed-request-context':
            curves = json.loads((ROOT/'tests/toilet-stress/inputs/bowl-and-lid-long/curves.json').read_text())['curves']
            mesh = await asyncio.to_thread(http, '/api/mesh/toilet')
            payload = dict(coordinateFrame='source', sourceSha256=mesh['sourceSha256'], curves=curves)
            await page.locator('#guideFile').set_input_files(dict(name='actual-two-guides.json', mimeType='application/json', buffer=json.dumps(payload).encode()))
            await page.wait_for_function('window.retopoDemo.getState().guides.length===2')
            await page.locator('#targetNumber').fill('150'); await page.locator('#targetNumber').press('Tab')
        if scenario == 'late-source-preview':
            async def hold_preview(route):
                response = await route.fetch(); preview_ready.set()
                await release_preview.wait()
                await route.fulfill(response=response)
            await page.route('**/assets/previews/hexagon.json', hold_preview)
            await page.locator('#meshSelect').select_option('hexagon')
            await preview_ready.wait()
            await page.locator('#meshSelect').select_option('toilet')
            await page.wait_for_function('window.retopoDemo.getState().meshId==="toilet"')
        await page.route('**/api/remesh', hold)
        await page.locator('#generateButton').click()
        await reply_ready.wait()
        check((await state())['busy'], scenario + ': browser is pending a real submitted request')
        if scenario == 'source-switch-before-response':
            await page.locator('#meshSelect').select_option('hexagon')
            await page.wait_for_function('window.retopoDemo.getState().meshId==="hexagon"')
            check(not (await state())['busy'], 'Changing source cancels generation even before its job ID arrives')
            release_reply.set()
            # A delayed delivery must cancel this same real job, not adopt it.
            for _ in range(100):
                value = await asyncio.to_thread(http, '/api/jobs/' + captured['id'])
                if value['state'] == 'cancelled':
                    break
                await page.wait_for_timeout(50)
            check(value['state'] == 'cancelled', 'Late remesh acknowledgement is cancelled after source switch', observed=value['state'])
            s = await state()
            check(s['meshId'] == 'hexagon' and s['resultJob'] != captured['id'] and not s['busy'], 'A stale toilet request cannot own the new source workspace')
        elif scenario == 'cancel-before-response':
            await page.locator('#cancelButton').click()
            check((await state())['lastAttempt']['phase'] == 'cancelling', 'Cancel before acknowledgement reports the request without claiming the worker stopped')
            await page.wait_for_timeout(400)
            check(await page.locator('#processTime').inner_text() == '', 'A cancelled pending request cannot keep updating the calculation timer')
            release_reply.set()
            for _ in range(100):
                value = await asyncio.to_thread(http, '/api/jobs/' + captured['id'])
                if value['state'] == 'cancelled':
                    break
                await page.wait_for_timeout(50)
            check(value['state'] == 'cancelled' and not (await state())['busy'], 'Late acknowledgement after explicit cancellation does not revive a job')
        elif scenario == 'external-cancel':
            value = await cancel(captured['id'])
            check(value['state'] == 'cancelled', 'A second API client cancels the real pending job')
            release_reply.set()
            await page.wait_for_function('!window.retopoDemo.getState().busy')
            check((await state())['lastAttempt']['phase'] == 'cancelled' and await page.locator('#resultEmptyTitle').inner_text() == 'Generation cancelled',
                  'Cancellation observed by polling is reflected in persistent feedback')
        elif scenario in ('reset-before-response', 'reset-two-pending'):
            if scenario == 'reset-two-pending':
                await page.locator('#cancelButton').click()
                reply_ready.clear()
                await page.locator('#generateButton').click()
                await reply_ready.wait()
                check(len(captured_requests) == 2, 'Two real submissions remain pending acknowledgement before Reset')
            await page.evaluate('localStorage.setItem("retopo-1:reset-probe","present")')
            await page.locator('#resetButton').click()
            await page.locator('#confirmReset').click()
            await page.wait_for_timeout(150)
            release_reply.set()
            await page.wait_for_function('window.retopoDemo?.getState().meshId==="hexagon"', timeout=15000)
            for _ in range(100):
                value = await asyncio.to_thread(http, '/api/jobs/' + captured['id'])
                if value['state'] == 'cancelled':
                    break
                await page.wait_for_timeout(50)
            check(value['state'] == 'cancelled', 'Reset cancels the submitted job before discarding its acknowledgement', observed=value['state'])
            for request in captured_requests:
                result = await asyncio.to_thread(http, '/api/jobs/' + request['id'])
                check(result['state'] == 'cancelled', 'Reset cancels each pending request, including earlier cancelled attempts', job=request['id'])
            check(await page.evaluate('localStorage.getItem("retopo-1:reset-probe")') is None, 'Reset clears the saved workspace after cancellation')
            check(not (await state())['busy'], 'Reset leaves the default workspace ready')
        elif scenario == 'late-source-preview':
            check(await page.locator('#generateButton').is_disabled(), 'Current Generate control is disabled while its request is pending')
            release_preview.set()
            await page.wait_for_timeout(200)
            s = await state()
            check(s['meshId'] == 'toilet' and s['busy'] and s['resultJob'] is None and await page.locator('#generateButton').is_disabled(),
                  'Late preview for a previous source cannot replace geometry or re-enable Generate')
            await page.locator('#cancelButton').click(); release_reply.set()
        else:
            await page.locator('#targetNumber').fill('1800'); await page.locator('#targetNumber').press('Tab')
            await page.locator('#clearButton').click()
            release_reply.set()
            # The actual 150-quad two-guide request is rejected by the real solver.
            await page.wait_for_function('!window.retopoDemo.getState().busy', timeout=300000)
            s = await state()
            check(s['target'] == 1800 and len(s['guides']) == 0, 'Edits made while a request is pending remain in the current document')
            check(s['lastAttempt']['phase'] == 'failed' and s['lastAttempt']['target'] == 150 and s['lastAttempt']['guideCount'] == 2,
                  'Failure describes the submitted target and guides, not later edits', attempt=s['lastAttempt'])
            check('150' in await page.locator('#resultEmptyDetail').inner_text(), 'Persistent failure text identifies the actual failed density')
        await page.screenshot(path=str(OUT/(scenario+'.png')))
    finally:
        release_reply.set()
        release_preview.set()
        for request in captured_requests:
            await cancel(request['id'])
        await context.close()


async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for scenario in (args.scenarios or ('source-switch-before-response', 'cancel-before-response', 'external-cancel', 'failed-request-context', 'late-source-preview', 'reset-before-response')):
            await exercise(browser, scenario)
        await browser.close()


with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
url = f'http://127.0.0.1:{port}'
log = (OUT/'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([sys.executable, '-X', 'utf8', str(ROOT/'server.py'), '--port', str(port)], cwd=ROOT,
    env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'), stdout=log, stderr=subprocess.STDOUT,
    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
try:
    while True:
        try:
            http('/api/health'); break
        except OSError:
            if server.poll() is not None:
                raise RuntimeError('Test server failed to start')
            import time
            time.sleep(.1)
    asyncio.run(run())
except Exception:
    errors.append(traceback.format_exc()); print(errors[-1], flush=True)
finally:
    for job in jobs:
        http('/api/jobs/' + job + '/cancel', {})
    for child in psutil.Process(server.pid).children(recursive=True):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    server.terminate(); server.wait(timeout=20); log.close()
    report = dict(passed=not errors and all(c['passed'] for c in checks), checks=checks, errors=errors, workerJobs=jobs,
                  sourceHashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['app.js','server.py','tests/verify_toilet_async_ui.py']},
                  scope='Actual Chromium, delayed delivery of genuine HTTP responses, actual toilet workers and cancellation. No fabricated worker output.')
    (OUT/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'], checks=len(checks), failures=[c['name'] for c in checks if not c['passed']])), flush=True)
sys.exit(0 if report['passed'] else 1)
