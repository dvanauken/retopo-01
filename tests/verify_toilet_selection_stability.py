"""Native toilet occlusion/marquee/group rollback and bounded repeat-use audit."""
from pathlib import Path
import hashlib
import argparse
import json
import math
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(); parser.add_argument('--label',default='current'); args=parser.parse_args()
OUT=ROOT/'tests/toilet-selection-stability'/args.label; OUT.mkdir(parents=True,exist_ok=True)
checks,errors,measurements=[],[],[]
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('app.js','src/view/SurfaceGuides.js','src/view/GuideController.js','tests/verify_toilet_selection_stability.py')}
with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'
log=(OUT/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-X','utf8','server.py','--port',str(port)],cwd=ROOT,stdout=log,stderr=log,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
def check(condition,name):
    checks.append(dict(name=name,passed=bool(condition))); print(('PASS ' if condition else 'FAIL ')+name,flush=True)

try:
    for _ in range(100):
        try: urllib.request.urlopen(url+'/api/health',timeout=1); break
        except OSError: time.sleep(.1)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True); context=browser.new_context(viewport={'width':1700,'height':1050},device_scale_factor=2)
        page=context.new_page(); page.on('pageerror',lambda error:errors.append(str(error)))
        def state(): return page.evaluate('window.retopoDemo.getState()')
        def doc(): return state()['guideDocument']
        def screen(point):
            p=page.evaluate('(p)=>window.retopoDemo.projectPoint(p,0)',point); return {'x':p['x'],'y':p['y']}
        def pick(point):
            p=screen(point); return page.evaluate('([x,y])=>window.retopoDemo.pickSource(x,y,0)',[p['x'],p['y']])
        def tool(name): page.locator(f'[data-tool={name}]').click()
        def draw(points):
            tool('polyline')
            for point in points: page.mouse.click(**screen(point))
            page.keyboard.press('Enter')
        def rectangle(a,b):
            page.mouse.move(**a); page.mouse.down(); page.mouse.move(**b,steps=12); page.mouse.up()
        page.goto(url,wait_until='networkidle'); page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
        page.locator('#meshSelect').select_option('toilet'); page.wait_for_function('window.retopoDemo.getState().meshId==="toilet"')
        page.locator('#clearButton').click(); page.locator('#topButton').click(); tool('select')
        box=page.locator('#viewport').bounding_box(); x=box['x']+box['width']*.25; y=box['y']+box['height']*.7
        page.locator('#viewport').focus()
        page.keyboard.down('Space'); page.mouse.move(x,y); page.mouse.down(); page.mouse.move(x,y-box['height']*.48,steps=24); page.mouse.up(); page.keyboard.up('Space'); page.wait_for_timeout(600)
        guesses=[[-.12,-.5,-.898],[0,-.55,-.898],[.12,-.5,-.898]]
        bottom=[pick(point) for point in guesses]
        check(all(point is not None and point[2]<-.6 for point in bottom),'Native orbit exposes the actual underside of the toilet')
        if not all(point is not None and point[2]<-.6 for point in bottom): raise AssertionError('Underside precondition failed: '+repr(bottom))
        page.screenshot(path=str(OUT/'underside.png'))
        draw(bottom); hidden=doc()[0]
        check(all(point['position'][2]<-.6 for point in hidden['points']),'A native underside guide attaches to the bottom surface')
        page.locator('#topButton').click(); tool('select')
        midpoint=[(bottom[0][i]+bottom[1][i])*.5 for i in range(3)]; visible=pick(midpoint)
        check(visible is not None and math.dist(visible,midpoint)>.1,'Top view occludes the underside guide behind a real surface')
        page.mouse.click(**screen(midpoint))
        check(not state()['interaction']['selection']['entityIds'],'Occluded guide body cannot be selected through the toilet')
        page.locator('.guide-name').first.click(); page.keyboard.press('a'); before=doc(); history=state()['guideHistory']['index']
        a=screen(bottom[0]); page.mouse.move(**a); page.mouse.down(); page.mouse.move(a['x']+15,a['y']+8,steps=8); page.mouse.up()
        check(doc()==before and state()['guideHistory']['index']==history,'An occluded point has no invisible drag handle')
        page.screenshot(path=str(OUT/'occluded-guide.png'))
        first=[[-.2,-.55,.22],[0,-.55,.22],[.2,-.55,.22]]
        second=[[-.2,-.34,.22],[0,-.34,.22],[.2,-.34,.22]]
        draw(first); draw(second); visible_ids=[g['id'] for g in doc()[1:]]
        check(len(doc())==3,'Two visible lid guides coexist with the occluded underside guide')
        projected=[screen(point) for curve in state()['guides'][1:] for point in curve]
        low={'x':min(p['x'] for p in projected)-14,'y':min(p['y'] for p in projected)-14}
        high={'x':max(p['x'] for p in projected)+14,'y':max(p['y'] for p in projected)+14}
        tool('select'); history=state()['guideHistory']['index']
        for reverse in (False,True):
            rectangle(high,low) if reverse else rectangle(low,high)
            check(set(state()['interaction']['selection']['entityIds'])==set(visible_ids),'Toilet marquee uses full containment and excludes hidden geometry '+('right-to-left' if reverse else 'left-to-right'))
        check(state()['guideHistory']['index']==history,'Toilet marquees create no document history')
        q=[screen(point) for point in state()['guides'][1]]
        a={'x':min(p['x'] for p in q)-14,'y':min(p['y'] for p in q)-12}
        b={'x':sum(p['x'] for p in q)/len(q),'y':max(p['y'] for p in q)+12}
        rectangle(a,b)
        check(not state()['interaction']['selection']['entityIds'],'A partially contained lid guide is not marquee-selected')
        page.locator('.guide-name').nth(1).click(); page.locator('.guide-name').nth(2).click(modifiers=['Shift'])
        before=doc(); history=state()['guideHistory']['index']; incidents=len(state()['guideErrors'])
        points=doc()[1]['points']; body=[(points[0]['position'][i]+points[1]['position'][i])*.5 for i in range(3)]
        blank={'x':box['x']+15,'y':box['y']+box['height']*.1}
        page.mouse.move(**screen(body)); page.mouse.down(); page.mouse.move(**blank,steps=16); page.mouse.up()
        check(doc()==before and state()['guideHistory']['index']==history,'Invalid group release preserves every guide and history atomically')
        check(len(state()['guideErrors'])==incidents+1,'Invalid group release produces one incident for the entire group')
        page.locator('#guideErrorDialog button').click()
        page.locator('#guidesToggle').uncheck(); tool('select'); page.mouse.click(**screen(body))
        check(not state()['interaction']['selection']['entityIds'] and doc()==before,'Hidden guide overlays cannot receive body selections')
        page.locator('#guidesToggle').check()
        page.locator('.guide-name').nth(1).click(); history=state()['guideHistory']['index']; selected=state()['tool']
        page.locator('#targetNumber').focus(); page.keyboard.press('Delete'); page.keyboard.press('s')
        check(doc()==before and state()['guideHistory']['index']==history and state()['tool']==selected,'Density-input keyboard ownership prevents guide deletion or tool shortcuts')
        page.locator('#targetNumber').fill('1800'); page.locator('#targetNumber').press('Tab')
        page.screenshot(path=str(OUT/'selection.png'))
        # Camera operations and source reloads add no intentional undo history.
        # Retained heap is measured after GC; GPU/driver allocation is not claimed.
        cdp=context.new_cdp_session(page); cdp.send('Performance.enable')
        def metrics(label):
            cdp.send('HeapProfiler.collectGarbage')
            values={v['name']:v['value'] for v in cdp.send('Performance.getMetrics')['metrics']}
            record=dict(label=label,heapUsed=values['JSHeapUsedSize'],nodes=values['Nodes'],documents=values['Documents'],taskSeconds=values['TaskDuration'])
            measurements.append(record); return record
        baseline=metrics('before-repetition'); durations=[]
        for iteration in range(20):
            start=time.monotonic()
            for mesh in ('hexagon','toilet'):
                page.locator('#meshSelect').select_option(mesh); page.wait_for_function('(id)=>window.retopoDemo.getState().meshId===id',arg=mesh)
                page.locator('#topButton').click()
            page.mouse.move(**screen([0,-.48,.22])); page.mouse.wheel(0,-90); page.locator('#fitButton').click()
            durations.append(time.monotonic()-start)
            if (iteration+1)%5==0: metrics('after-'+str(iteration+1)+'-cycles')
        after=metrics('after-repetition')
        check(doc()==before,'Twenty source/camera-view cycles preserve the exact saved toilet guides')
        check(after['heapUsed']-baseline['heapUsed']<8*1024*1024,'Retained JS heap grows by less than 8 MiB across forty source switches')
        check(after['documents']<=baseline['documents']+1,'Repeated source switches do not accumulate browser documents')
        check(not errors,'Selection and repeat-use tests have no browser JavaScript errors')
        measurements.append(dict(cycles=20,sourceSwitches=40,cycleSeconds=durations))
        page.screenshot(path=str(OUT/'after-repetition.png')); browser.close()
except Exception:
    errors.append(traceback.format_exc()); print(errors[-1],flush=True)
finally:
    server.terminate(); server.wait(timeout=20); log.close()
report=dict(passed=not errors and all(c['passed'] for c in checks),checks=checks,errors=errors,measurements=measurements,sourceHashes=hashes,
    scope='Native underside orbit/drawing, real occlusion, source-pane selection at DPR 2, whole-group rejection, keyboard ownership and forty source switches. JS heap after GC is measured; this is a bounded repeat-use test, not an indefinite GPU-memory guarantee.')
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=report['passed'],checks=len(checks),errors=errors)),flush=True)
raise SystemExit(0 if report['passed'] else 1)
