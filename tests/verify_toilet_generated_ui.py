"""Real toilet generation, exported result editing and late-success UI races.

Only delivery of genuine completed worker responses is delayed. No fabricated
success, cached render fixture or substituted geometry is used.
"""
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

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests/toilet-generated-ui/current'; OUT.mkdir(parents=True,exist_ok=True)
FILES=('app.js','server.py','worker.py','curved_quad.py','tests/verify_toilet_generated_ui.py')
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES}
checks,errors,jobs,cases=[],[],[],[]
with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'

def http(path,body=None):
    req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=20))

def check(value,name,**detail):
    checks.append(dict(passed=bool(value),name=name,**detail)); print(('PASS ' if value else 'FAIL ')+name,flush=True)

async def run():
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(headless=True)
        context=await browser.new_context(viewport={'width':1700,'height':1050},device_scale_factor=2)
        page=await context.new_page(); page.on('pageerror',lambda error:errors.append(str(error)))
        async def state(): return await page.evaluate('window.retopoDemo.getState()')
        async def tool(name): await page.locator(f'[data-tool="{name}"]').click()
        async def number(value):
            await page.locator('#targetNumber').fill(str(value)); await page.locator('#targetNumber').press('Tab')
        async def screen(point):
            p=await page.evaluate('(p)=>window.retopoDemo.projectPoint(p,1)',point)
            return dict(x=p['x'],y=p['y'])
        async def load(curves):
            packet=dict(coordinateFrame='source',sourceSha256=source['sourceSha256'],curves=curves)
            await page.locator('#guideFile').set_input_files(dict(name='toilet-guides.json',mimeType='application/json',buffer=json.dumps(packet).encode()))
            await page.wait_for_function('(n)=>window.retopoDemo.getState().guides.length===n',arg=len(curves))
        await page.goto(url,wait_until='networkidle'); await page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
        await page.locator('#meshSelect').select_option('toilet'); await page.wait_for_function('window.retopoDemo.getState().meshId==="toilet"')
        source=await asyncio.to_thread(http,'/api/mesh/toilet')
        circle=json.loads((ROOT/'tests/toilet-stress/browser-lid-circle/curves.json').read_text())['curves']
        await load(circle); await number(1800)
        ready,release=asyncio.Event(),asyncio.Event(); captured={}
        async def hold(route):
            response=await route.fetch(timeout=30000); data=await response.json()
            if not response.ok: raise AssertionError(data)
            captured.update(data=data,url=route.request.url); ready.set()
            await release.wait(); await route.fulfill(response=response)
        await page.route('**/api/jobs/*/mesh.json',hold)
        try:
            await page.locator('#generateButton').click()
            await asyncio.wait_for(ready.wait(),timeout=650)
            job=captured['url'].split('/')[-2]; jobs.append(job)
            actual=await asyncio.to_thread(http,'/api/jobs/'+job)
            check(actual['state']=='complete' and captured['data']['surfaceValidation']['passed'],'Genuine Circle worker completes before its mesh response is released')
            original=(await state())['guideDocument']; await number(1500)
            await page.locator('#clearButton').click()
            check(not (await state())['guides'] and (await state())['busy'],'Guide and density edits remain available while a completed mesh is in transit')
            release.set(); await page.wait_for_function('!window.retopoDemo.getState().busy')
            s=await state()
            check(s['resultJob']==job and s['dirty'] and not s['guides'] and s['target']==1500,'Late success retains newer edits and labels the actual result as needing update')
            check(s['lastAttempt']['target']==1800 and s['lastAttempt']['guideCount']==1,'Successful attempt records its original parameters')
            check(await page.locator('#resultBadge').inner_text()=='Needs update','Stale successful result has a visible update badge')
            with_job=OUT/'circle-success'; with_job.mkdir(exist_ok=True)
            for name in ('curves.json','settings.json','report.json','mesh.json','output.obj','surface-solver.json'):
                (with_job/name).write_bytes((ROOT/'runs'/job/name).read_bytes())
            cases.append(dict(name='circle-success',state='complete',job=job,target=1800))
            async with page.expect_download() as event: await page.locator('#exportMesh').click()
            download=await event.value; await download.save_as(str(OUT/'browser-export.obj'))
            check((OUT/'browser-export.obj').read_bytes()==(ROOT/'runs'/job/'output.obj').read_bytes(),'Native OBJ download matches the accepted worker output byte for byte')
            # Test direct editing through the actual generated pane, including
            # source projection and atomic undo, without a preview fixture.
            await page.locator('#topButton').click(); await tool('polyline')
            for point in [[-.2,-.55,.22],[0,-.55,.22],[.2,-.5,.22]]:
                await page.mouse.click(**await screen(point))
            await page.keyboard.press('Enter'); s=await state(); guide=s['guideDocument'][0]
            check(len(guide['points'])==3 and s['resultGuideOverlayVisible'],'Native right-pane Polyline is authored over a genuine accepted toilet mesh')
            await tool('select'); await page.locator('.guide-name').first.click(); await page.keyboard.press('a')
            a=await screen(guide['points'][1]['position']); b=dict(x=a['x']+8,y=a['y']-8)
            expected=await page.evaluate('([x,y])=>window.retopoDemo.pickSource(x,y,1)',[b['x'],b['y']])
            history=(await state())['guideHistory']['index']
            await page.mouse.move(**a); await page.mouse.down(); await page.mouse.move(**b,steps=8); await page.mouse.up()
            s=await state(); point=s['guideDocument'][0]['points'][1]['position']
            check(expected is not None and sum((x-y)**2 for x,y in zip(expected,point))<1e-12 and s['guideHistory']['index']==history+1,'Generated-pane point edit snaps to the original source and commits once')
            await page.keyboard.press('Control+z'); check((await state())['guideDocument'][0]==guide,'Undo restores exact values after editing in the generated pane')
            await page.locator('[data-view="overlay"]').click()
            check((await state())['view']=='overlay' and not (await state())['resultGuideOverlayVisible'],'Overlay uses one guide display over the accepted mesh')
            await page.locator('[data-view="split"]').click(); await page.locator('#themeButton').click()
            await page.screenshot(path=str(OUT/'accepted-dark.png')); await page.locator('#themeButton').click()
            # A genuine rejected solve must retain the previous accepted mesh.
            bad=json.loads((ROOT/'tests/toilet-stress/two-guides-long-1800/curves.json').read_text())['curves']
            await load(bad); await number(150)
            await page.locator('#generateButton').click(); await page.wait_for_function('!window.retopoDemo.getState().busy',timeout=650000)
            s=await state()
            check(s['lastAttempt']['phase']=='failed' and s['resultJob']==job and s['resultFaces']==len(captured['data']['faces']),'Actual rejected two-guide solve preserves the previous accepted mesh')
            check(await page.locator('#generationFeedback').is_visible() and 'previous accepted result' in await page.locator('#generationFeedback').inner_text(),'Failure with a prior result is clearly labeled in the viewport')
            await page.screenshot(path=str(OUT/'previous-result-after-failure.png'))
            # Retry through a fresh real solve, then switch sources while the
            # completed mesh response is held. The old response cannot win.
            await load(circle); await number(1800); ready.clear(); release.clear()
            await page.locator('#generateButton').click(); await asyncio.wait_for(ready.wait(),timeout=650)
            second=captured['url'].split('/')[-2]; jobs.append(second)
            check(second!=job and (await asyncio.to_thread(http,'/api/jobs/'+second))['state']=='complete','Retry produces a second genuinely completed toilet job')
            await page.locator('#meshSelect').select_option('hexagon'); await page.wait_for_function('window.retopoDemo.getState().meshId==="hexagon" && window.retopoDemo.getState().resultFaces>0')
            before=await state(); release.set(); await page.wait_for_timeout(600); after=await state()
            check(after['meshId']=='hexagon' and after['resultJob']==before['resultJob'] and after['resultFaces']==before['resultFaces'] and not after['busy'],'Late successful toilet mesh cannot overwrite a different source or its preview')
            check(all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),'Implementation remains fixed through the generated-result workflow')
        finally:
            release.set(); await context.close(); await browser.close()

log=(OUT/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-X','utf8','server.py','--port',str(port)],cwd=ROOT,stdout=log,stderr=log,
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
    import time
    for _ in range(100):
        try: http('/api/health'); break
        except OSError: time.sleep(.1)
    asyncio.run(run())
except Exception:
    errors.append(traceback.format_exc()); print(errors[-1],flush=True)
finally:
    for job in jobs:
        try: http('/api/jobs/'+job+'/cancel',{})
        except OSError: pass
    for child in psutil.Process(server.pid).children(recursive=True):
        try: child.kill()
        except psutil.NoSuchProcess: pass
    server.terminate(); server.wait(timeout=20); log.close()
    report=dict(passed=not errors and all(c['passed'] for c in checks),complete=not errors,checks=checks,errors=errors,cases=cases,sourceHashes=hashes,
        scope='Real browser/HTTP/Blender generations with genuine delayed successful responses; native OBJ download and editing on accepted geometry, stale success and prior-result failure handling. No substituted result fixture.')
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(dict(passed=report['passed'],checks=len(checks))),flush=True)
raise SystemExit(0 if report['passed'] else 1)
