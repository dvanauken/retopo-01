"""Real browser/worker cancellation with deliberately broken HTTP transport.

Only delivery of cancellation requests is interrupted. No job state or geometry
is fabricated. Failed retries retain their original negative evidence.
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
import time
import traceback
import urllib.request

import psutil
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--scenarios', nargs='+', default=['cancel-failure', 'reset-failure', 'cancel-response-lost', 'stale-ack-cancel-failure', 'reset-during-cancel', 'source-switch-after-cancel-failure', 'poll-and-cancel-failure'])
args = parser.parse_args()
if not args.label.replace('-', '').isalnum():
    raise ValueError('Use a plain label')
OUT = ROOT / 'tests/toilet-cancel-transport' / args.label
OUT.mkdir(parents=True, exist_ok=True)
checks, errors, records, jobs = [], [], [], []


def check(value, name, **details):
    checks.append(dict(name=name, passed=bool(value), **details))
    print(('PASS ' if value else 'FAIL ') + name, flush=True)


def http(path, payload=None):
    request = urllib.request.Request(url + path, data=None if payload is None else json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(request, timeout=15))


async def exercise(browser, scenario):
    context = await browser.new_context(viewport={'width': 1700, 'height': 1050})
    page = await context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    captured = {}
    admitted, interrupted = asyncio.Event(), asyncio.Event()
    release_submit, release_cancel = asyncio.Event(), asyncio.Event()

    async def submit(route):
        response = await route.fetch()
        captured.update(await response.json())
        jobs.append(captured['id'])
        admitted.set()
        if scenario == 'stale-ack-cancel-failure':
            await release_submit.wait()
        await route.fulfill(response=response)

    async def abort_cancel(route):
        if scenario == 'reset-during-cancel':
            interrupted.set()
            await release_cancel.wait()
            response = await route.fetch()
            await route.fulfill(response=response)
            return
        if scenario == 'cancel-response-lost':
            await route.fetch()
        await route.abort('connectionreset')
        interrupted.set()

    async def state():
        return await page.evaluate('window.retopoDemo.getState()')

    try:
        await page.goto(url, wait_until='networkidle')
        await page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
        await page.locator('#meshSelect').select_option('toilet')
        await page.wait_for_function('window.retopoDemo.getState().meshId==="toilet"')
        before = await state()
        await page.evaluate('localStorage.setItem("retopo-1:transport-probe", "preserve me")')
        await page.route('**/api/remesh', submit)
        await page.locator('#generateButton').click()
        await asyncio.wait_for(admitted.wait(), timeout=15)
        # Wait for a real worker, and allow the genuine acknowledgement to reach
        # the app before interrupting the subsequent cancellation request.
        deadline = time.monotonic() + 30
        observed = []
        while time.monotonic() < deadline:
            observed = [p for p in psutil.Process(server.pid).children(recursive=True)
                        if 'worker.py' in ' '.join(p.cmdline())]
            if observed:
                break
            await asyncio.sleep(.05)
        await page.wait_for_timeout(150)
        check(bool(observed), scenario + ': a genuine toilet worker is alive before interruption')
        worker = [dict(pid=p.pid, created=p.create_time()) for p in observed]
        await page.route('**/api/requests/*/cancel', abort_cancel)
        if scenario == 'reset-failure':
            await page.locator('#resetButton').click()
            await page.locator('#confirmReset').click()
        elif scenario == 'poll-and-cancel-failure':
            async def abort_poll(route):
                if route.request.method == 'GET':
                    await route.abort('connectionreset')
                else:
                    await route.continue_()
            await page.route('**/api/jobs/*', abort_poll)
        else:
            await page.locator('#cancelButton').click()
        release_submit.set()
        await asyncio.wait_for(interrupted.wait(), timeout=15)
        if scenario == 'reset-during-cancel':
            await page.locator('#resetButton').click()
            await page.locator('#confirmReset').click()
            await page.wait_for_timeout(200)
            check((await state())['meshId']=='toilet' and await page.evaluate('localStorage.getItem("retopo-1:transport-probe")')=='preserve me',
                  scenario + ': Reset waits for an acknowledged job whose cancellation is still in flight')
            release_cancel.set()
            await page.wait_for_function('window.retopoDemo?.getState().meshId==="hexagon"', timeout=15000)
        else:
            await page.wait_for_function('!document.querySelector("#notice").hidden')
        after = await state()
        actual = await asyncio.to_thread(http, '/api/jobs/' + captured['id'])
        if scenario != 'reset-during-cancel':
            expected = ('cancelled',) if scenario=='cancel-response-lost' else ('queued', 'running')
            check(actual['state'] in expected, scenario + ': actual server state matches the injected transport boundary', observed=actual['state'])
            check(after['lastAttempt']['phase'] != 'cancelled', scenario + ': UI does not claim cancellation before confirmation', attempt=after['lastAttempt'])
            check(after['guides'] == before['guides'] and after['meshId'] == 'toilet'
                  and await page.evaluate('localStorage.getItem("retopo-1:transport-probe")') == 'preserve me',
                  scenario + ': failed cancellation preserves the current workspace')
        await page.screenshot(path=str(OUT/(scenario+'-interrupted.png')))
        await page.unroute('**/api/requests/*/cancel', abort_cancel)
        if scenario == 'poll-and-cancel-failure':
            await page.unroute('**/api/jobs/*', abort_poll)
        if scenario == 'source-switch-after-cancel-failure':
            await page.locator('#meshSelect').select_option('hexagon')
            await page.wait_for_function('window.retopoDemo?.getState().meshId==="hexagon"')
            check(await page.locator('#cancelButton').is_visible(), scenario + ': outstanding cancellation remains visible after changing source')
        if scenario in ('reset-failure', 'source-switch-after-cancel-failure'):
            await page.locator('#resetButton').click()
            await page.locator('#confirmReset').click()
        elif scenario != 'reset-during-cancel':
            retry_visible = await page.locator('#cancelButton').is_visible()
            check(retry_visible, scenario + ': cancellation remains available to retry')
            if retry_visible:
                await page.locator('#cancelButton').click()
            else:
                # A Reset must also recover ownership if Cancel has lost it.
                await page.locator('#resetButton').click()
                await page.locator('#confirmReset').click()
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            actual = await asyncio.to_thread(http, '/api/jobs/' + captured['id'])
            if actual['state'] == 'cancelled':
                break
            await asyncio.sleep(.05)
        check(actual['state'] == 'cancelled', scenario + ': retry cancels the same real job', observed=actual['state'])
        def alive():
            result = []
            for record in worker:
                try:
                    p = psutil.Process(record['pid'])
                    if p.is_running() and p.create_time() == record['created']:
                        result.append(p.pid)
                except psutil.NoSuchProcess:
                    pass
            return result
        deadline = time.monotonic() + 5
        while alive() and actual['state'] == 'cancelled' and time.monotonic() < deadline:
            await asyncio.sleep(.05)
        check(not alive(), scenario + ': retry leaves no observed toilet worker alive', survivors=alive())
        if scenario in ('reset-failure', 'reset-during-cancel', 'source-switch-after-cancel-failure'):
            await page.wait_for_function('window.retopoDemo?.getState().meshId==="hexagon"', timeout=15000)
            check(actual['state']=='cancelled' and await page.evaluate('localStorage.getItem("retopo-1:transport-probe")') is None,
                  scenario + ': successful retry clears workspace only after cancellation')
        if scenario not in ('reset-failure', 'reset-during-cancel', 'source-switch-after-cancel-failure'):
            await page.wait_for_timeout(150)
            check(await page.locator('#processing').is_hidden() and (await page.locator('#notice').is_hidden() or 'not confirmed' not in await page.locator('#noticeText').inner_text()),
                  scenario + ': confirmed retry clears the obsolete cancellation error')
        records.append(dict(scenario=scenario, job=captured['id'], observedWorkers=worker,
                            interruptedState=after, retriedServerState=actual))
        await page.screenshot(path=str(OUT/(scenario+'-retried.png')))
    finally:
        release_submit.set(); release_cancel.set()
        if captured:
            await asyncio.to_thread(http, '/api/jobs/' + captured['id'] + '/cancel', {})
        await context.close()


async def run():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            for scenario in args.scenarios:
                await exercise(browser, scenario)
        finally:
            await browser.close()


with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
url = f'http://127.0.0.1:{port}'
log = (OUT/'server.log').open('w', encoding='utf-8')
server = subprocess.Popen([sys.executable, '-X', 'utf8', str(ROOT/'server.py'), '--port', str(port)], cwd=ROOT,
    env=dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1'),
    stdout=log, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
try:
    deadline = time.monotonic() + 30
    while True:
        try:
            http('/api/health')
            break
        except OSError:
            if server.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Test server failed to start')
            time.sleep(.1)
    asyncio.run(run())
except Exception:
    errors.append(traceback.format_exc())
    print(errors[-1], flush=True)
finally:
    for job in jobs:
        try:
            http('/api/jobs/'+job+'/cancel', {})
        except Exception as error:
            errors.append('Cleanup: '+str(error))
    for child in psutil.Process(server.pid).children(recursive=True):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    server.terminate()
    server.wait(timeout=20)
    log.close()
    report = dict(passed=not errors and all(c['passed'] for c in checks), checks=checks, errors=errors,
        scenarios=records, jobs=jobs,
        sourceHashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                      for name in ('app.js', 'server.py', 'tests/verify_toilet_cancel_transport.py')},
        scope='Actual Chromium, real admitted toilet workers. Only cancellation HTTP transport is interrupted; no fabricated job states or meshes.')
    (OUT/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'], checks=len(checks), failures=[c['name'] for c in checks if not c['passed']])), flush=True)
raise SystemExit(0 if report['passed'] else 1)
