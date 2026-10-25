"""Toilet-specific native browser editing at DPR 1/2 in source/result panes.

Right-pane cases use an explicitly unqualified historical rendering fixture.
They test editing against the original source, not solver acceptance. No job is
fabricated and no fixture is installed in the app or published by the server.
"""
from pathlib import Path
import copy
import argparse
import hashlib
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
OUT=ROOT/'tests/toilet-editing'/args.label; OUT.mkdir(parents=True,exist_ok=True)
checks, errors, scenarios=[],[],[]
hash_files=['app.js','index.html','server.py','tests/verify_toilet_editing.py']+[str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'src').rglob('*.js')]
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in hash_files}
fixture_path=ROOT/'tests/toilet-stress/two-guides-short-1800/mesh.json'
fixture=json.loads(fixture_path.read_text()); fixture['quality']['passed']=False
fixture['quality']['failures']=['Unqualified historical geometry; rendering test fixture only']
with socket.socket() as sock:
    sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'
log=(OUT/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-X','utf8','server.py','--port',str(port)],cwd=ROOT,stdout=log,stderr=log,
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def check(condition,name):
    checks.append(dict(name=name,passed=bool(condition)))
    print(('PASS ' if condition else 'FAIL ')+name,flush=True)


try:
    for _ in range(100):
        try: urllib.request.urlopen(url+'/api/health',timeout=1); break
        except OSError: time.sleep(.1)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        for dpr,pane in ((1,0),(2,0),(1,1),(2,1)):
            label=f'dpr-{dpr}-pane-{pane}'; start_index=len(checks)
            context=browser.new_context(viewport={'width':1700,'height':1050},device_scale_factor=dpr,accept_downloads=True)
            page=context.new_page(); page.on('pageerror',lambda e:errors.append(str(e)))
            def state(): return page.evaluate('window.retopoDemo.getState()')
            def doc(): return state()['guideDocument']
            def screen(p):
                value=page.evaluate('([p,n])=>window.retopoDemo.projectPoint(p,n)',[p,pane]); return {'x':value['x'],'y':value['y']}
            def pick(x,y): return page.evaluate('([x,y,n])=>window.retopoDemo.pickSource(x,y,n)',[x,y,pane])
            def tool(name): page.locator(f'[data-tool={name}]').click()
            def clear():
                page.keyboard.press('Escape')
                if page.locator('#clearButton').is_enabled(): page.locator('#clearButton').click()
            def dismiss():
                if page.locator('#guideErrorDialog').is_visible(): page.locator('#guideErrorDialog button').click()
            def click(p): page.mouse.click(**screen(p))
            def verify(value,name): check(value,label+': '+name)
            try:
                if pane:
                    def source_fixture(route):
                        response=route.fetch(); data=response.json(); data['previewUrl']='/assets/previews/toilet-test.json'
                        route.fulfill(response=response,json=data)
                    page.route('**/api/mesh/toilet',source_fixture)
                    page.route('**/assets/previews/toilet-test.json',lambda route:route.fulfill(json=fixture))
                page.goto(url,wait_until='networkidle'); page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
                page.locator('#meshSelect').select_option('toilet')
                page.wait_for_function('window.retopoDemo.getState().meshId==="toilet"')
                if pane: page.wait_for_function('window.retopoDemo.getState().resultFaces>0')
                page.locator('#topButton').click(); clear()
                # Screen picks are from the real imported lid; they are not
                # invented planar coordinates or synthetic pointer events.
                guesses=[[-.2,-.5,.22],[0,-.55,.22],[.2,-.5,.22]]
                points=[pick(**screen(p)) for p in guesses]
                verify(all(points),'three native rays hit the toilet lid')
                if not all(points): raise AssertionError(points)
                tool('polyline')
                for p in points: click(p)
                page.keyboard.press('Enter'); original=doc()[0]
                verify(len(original['points'])==3 and original['type']=='polyline','Polyline retains three authored lid points')
                history=state()['guideHistory']['index']
                body=[(points[0][i]+points[1][i])/2 for i in range(3)]
                tool('select'); click(body)
                verify(state()['interaction']['selection']['entityIds']==[original['id']],'body selection picks the visible toilet guide')
                verify(state()['guideHistory']['index']==history,'selection adds no document history')
                page.keyboard.press('a')
                a=screen(original['points'][0]['position']); b={'x':a['x']+9,'y':a['y']-12}; expected=pick(**b)
                page.mouse.move(**a); page.mouse.down(); page.mouse.move(**b,steps=8)
                verify(doc()[0]==original and bool(state()['interaction']['candidates']),'point preview leaves the accepted document unchanged')
                page.mouse.up(); edited=doc()[0]
                verify(expected is not None and math.dist(edited['points'][0]['position'],expected)<1e-6,'point release attaches to the actual lid surface')
                verify(edited['id']==original['id'] and [p['id'] for p in edited['points']]==[p['id'] for p in original['points']],'point edit preserves guide and point identities')
                verify(state()['guideHistory']['index']==history+1,'point edit is one history command')
                page.keyboard.press('Control+z'); verify(doc()[0]==original,'Undo restores exact authored values')
                page.keyboard.press('Control+Shift+z'); verify(doc()[0]==edited,'Redo restores exact edited values')
                before=doc(); history=state()['guideHistory']['index']; box=page.locator('#viewport').bounding_box()
                blank={'x':box['x']+box['width']*(.02+pane*.5),'y':box['y']+box['height']*.12}
                verify(pick(**blank) is None,'invalid-release target is empty space')
                page.mouse.move(**screen(edited['points'][0]['position'])); page.mouse.down(); page.mouse.move(**blank,steps=10); page.mouse.up()
                verify(doc()==before and state()['guideHistory']['index']==history,'off-surface release rolls back the whole edit')
                verify(page.locator('#guideErrorDialog').is_visible(),'off-surface rejection has a visible incident'); dismiss()
                # Camera changes must update screen-space picking caches.
                page.locator('#viewport').focus(); page.mouse.move(**screen(points[1])); page.mouse.wheel(0,-180); page.wait_for_timeout(250)
                tool('select'); page.locator('.guide-name').first.click(); page.keyboard.press('a')
                a=screen(doc()[0]['points'][1]['position']); b={'x':a['x'],'y':a['y']+10}; expected=pick(**b)
                page.mouse.move(**a); page.mouse.down(); page.mouse.move(**b,steps=6); page.mouse.up()
                verify(expected is not None and math.dist(doc()[0]['points'][1]['position'],expected)<1e-6,'point picking follows camera zoom')
                page.keyboard.press('Control+z'); page.locator('#topButton').click()
                # Group operations are checked on two real surface guides.
                tool('spline'); second=[pick(**screen([p[0],p[1]+.16,.22])) for p in guesses]
                for p in second: click(p)
                page.keyboard.press('Enter')
                verify(len(doc())==2 and doc()[1]['type']=='spline' and len(state()['guides'][1])>3,'Spline derives a dense curved-surface guide from three fits')
                tool('select'); page.locator('.guide-name').nth(0).click(); page.locator('.guide-name').nth(1).click(modifiers=['Shift'])
                verify(len(state()['interaction']['selection']['entityIds'])==2,'Shift selects both toilet guides')
                before=doc(); page.locator('#reverseGuides').click()
                verify(all(a['points']==list(reversed(b['points'])) for a,b in zip(doc(),before)),'Reverse preserves all selected guide identities')
                page.keyboard.press('Control+z'); verify(doc()==before,'one Undo restores the entire group reversal')
                page.keyboard.press('Delete'); verify(not doc(),'Object Delete removes the selected group')
                page.keyboard.press('Control+z'); verify(doc()==before,'one Undo restores both deleted guides')
                # Native persistence preserves authored records, not only samples.
                with page.expect_download() as download: page.locator('#exportGuides').click()
                saved=OUT/(label+'-guides.json'); download.value.save_as(str(saved)); packet=json.loads(saved.read_text())
                verify(packet['guides']==doc() and packet['schemaVersion']==3,'native export preserves IDs and authored guide records')
                clear(); page.locator('#guideFile').set_input_files(str(saved))
                page.wait_for_function('window.retopoDemo.getState().guideDocument.length===2')
                verify(doc()==packet['guides'],'native import restores exact toilet guides')
                # Rejected imports must be atomic, including duplicated IDs and
                # malformed/foreign source data, without polluting Undo history.
                invalid=[]
                bad=copy.deepcopy(packet); bad['sourceSha256']='foreign'; invalid.append(('foreign source',json.dumps(bad)))
                bad=copy.deepcopy(packet); bad['guides'][1]['id']=bad['guides'][0]['id']; invalid.append(('duplicate identities',json.dumps(bad)))
                bad=copy.deepcopy(packet); bad['schemaVersion']=99; invalid.append(('unknown schema',json.dumps(bad)))
                invalid.extend([('malformed JSON','{"guides":'),('file budget',' '*2000001)])
                for name,payload in invalid:
                    before=doc(); history=state()['guideHistory']['index']; count=len(state()['guideErrors'])
                    page.locator('#guideFile').set_input_files(dict(name='invalid.json',mimeType='application/json',buffer=payload.encode()))
                    page.wait_for_function('(n)=>window.retopoDemo.getState().guideErrors.length>n',arg=count)
                    verify(doc()==before and state()['guideHistory']['index']==history,'rejected '+name+' import preserves document/history'); dismiss()
                page.reload(wait_until='networkidle'); page.wait_for_function('window.retopoDemo?.getState().meshId==="hexagon"')
                page.locator('#meshSelect').select_option('toilet')
                page.wait_for_function('window.retopoDemo.getState().meshId==="toilet" && window.retopoDemo.getState().guideDocument.length===2')
                if pane: page.wait_for_function('window.retopoDemo.getState().resultFaces>0')
                verify(doc()==packet['guides'],'reload and source reselection restore exact authored toilet guides')
                page.locator('#topButton').click(); clear()
                # Closure uses CSS pixels, independently of physical DPR.
                tool('polyline'); square=[[-.16,-.58,.22],[.16,-.58,.22],[.16,-.34,.22],[-.16,-.34,.22]]
                for p in square: click(p)
                first=screen(square[0])
                page.mouse.move(first['x']+5.5,first['y']); verify(state()['interaction']['closureSnap'] is None,'closure remains off beyond five CSS pixels')
                page.mouse.move(first['x']+4.5,first['y']); verify(state()['interaction']['closureSnap'] is not None,'closure snaps inside five CSS pixels')
                page.mouse.click(first['x']+4.5,first['y']); verify(len(doc())==1 and doc()[0]['closed'] and len(doc()[0]['points'])==4,'proximity closure creates no duplicate authored endpoint')
                clear(); tool('circle'); click([0,-.48,.22]); click([.12,-.48,.22])
                verify(len(doc())==1 and doc()[0]['type']=='circle' and doc()[0]['closed'],'Circle projects a closed guide onto the toilet lid')
                page.screenshot(path=str(OUT/(label+'.png')))
                if pane==0:
                    # An empty result viewport must never edit invisible source.
                    clear(); tool('draw'); right=page.evaluate('window.retopoDemo.projectPoint([0,-.48,.22],1)')
                    page.mouse.move(right['x'],right['y']); page.mouse.down(); page.mouse.move(right['x']+20,right['y'],steps=8); page.mouse.up()
                    verify(not doc() and not state()['resultGuideOverlayVisible'],'empty result pane cannot create invisible guides')
                scenarios.append(dict(name=label,complete=True,checks=len(checks)-start_index))
            except Exception:
                errors.append(label+': '+traceback.format_exc()); scenarios.append(dict(name=label,complete=False))
                try: page.screenshot(path=str(OUT/(label+'-failure.png')))
                except Exception: pass
            finally: context.close()
        browser.close()
finally:
    server.terminate(); server.wait(timeout=20); log.close()
result=dict(passed=not errors and all(c['passed'] for c in checks),checks=checks,errors=errors,scenarios=scenarios,sourceHashes=hashes,
            renderingFixture=dict(file=str(fixture_path.relative_to(ROOT)),sha256=hashlib.sha256(fixture_path.read_bytes()).hexdigest(),qualified=False),
            scope='Native Chromium pointer/keyboard/file input on the original toilet at DPR 1/2. Right pane uses an explicitly unqualified historical rendering fixture; this is editor coverage, not solver qualification.')
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(passed=result['passed'],checks=len(checks),errors=errors)),flush=True)
raise SystemExit(0 if result['passed'] else 1)
