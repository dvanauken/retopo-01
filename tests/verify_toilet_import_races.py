"""Native toilet-file reads delayed at File.text, without fabricating contents."""
from pathlib import Path
import hashlib
import json
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'tests/toilet-import-races'; OUT.mkdir(exist_ok=True)
checks,errors=[],[]
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('app.js','src/io/GuideSerializer.js','src/domain/GuideDocument.js','tests/verify_toilet_import_races.py')}
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
    source=json.load(urllib.request.urlopen(url+'/api/mesh/toilet'))
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for scenario in ('source-change','edit-during-read','latest-import-wins','stale-invalid-read','construction-during-read','legacy'):
            context=browser.new_context(viewport={'width':1700,'height':1050}); page=context.new_page()
            page.on('pageerror',lambda error:errors.append(str(error)))
            def state(): return page.evaluate('window.retopoDemo.getState()')
            def upload(payload,name='held-import.json'):
                page.locator('#guideFile').set_input_files(dict(name=name,mimeType='application/json',buffer=payload.encode()))
            def release(index,completed):
                page.evaluate('(i)=>{const r=window.__heldReads[i];r.resolve(r.text)}',index)
                page.wait_for_function('(n)=>window.__completedReads===n',arg=completed)
                page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(resolve))')
            try:
                page.goto(url,wait_until='networkidle'); page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
                page.locator('#meshSelect').select_option('toilet'); page.wait_for_function('window.retopoDemo.getState().meshId==="toilet" && window.retopoDemo.getState().guideDocument.length===1')
                original=state(); packet=dict(format='retopo-guides',schemaVersion=3,coordinateFrame='source',sourceSha256=source['sourceSha256'],guides=original['guideDocument'],curves=original['guides'])
                (OUT/(scenario+'-input.json')).write_text(json.dumps(packet)+'\n')
                page.evaluate('''()=>{
                    const native=File.prototype.text; window.__heldReads=[]; window.__completedReads=0;
                    File.prototype.text=async function(){
                        const text=await native.call(this);
                        if(!this.name.startsWith('held-import'))return text;
                        return new Promise(resolve=>window.__heldReads.push({text,resolve})).then(value=>{window.__completedReads++;return value;});
                    };
                }''')
                if scenario=='legacy':
                    for closed in (True,False):
                        curve=original['guides'][0] if closed else original['guides'][0][:3]
                        before=state()['guideHistory']['index']
                        upload(json.dumps(dict(coordinateFrame='source',sourceSha256=source['sourceSha256'],curves=[curve])),'legacy.json')
                        page.wait_for_function('(i)=>window.retopoDemo.getState().guideHistory.index>i',arg=before)
                        guide=state()['guideDocument'][0]
                        check(guide['type']=='polyline' and guide['closed']==closed,'Legacy '+('closed' if closed else 'open')+' toilet guide retains its path semantics')
                        expected=curve[:-1] if closed else curve
                        check([point['position'] for point in guide['points']]==expected,'Legacy import preserves every authored source coordinate without a duplicate closing point')
                    continue
                upload('{broken-json' if scenario=='stale-invalid-read' else json.dumps(packet))
                page.wait_for_function('window.__heldReads.length===1')
                if scenario=='source-change':
                    page.locator('#meshSelect').select_option('hexagon'); page.wait_for_function('window.retopoDemo.getState().meshId==="hexagon"')
                    before=state(); release(0,1); after=state()
                    check(after['meshId']=='hexagon' and after['guideDocument']==before['guideDocument'],'Late toilet file cannot replace another source document')
                    check(after['guideHistory']==before['guideHistory'] and after['guideErrors']==before['guideErrors'],'Stale source import creates no history or irrelevant error')
                elif scenario=='edit-during-read':
                    page.locator('#clearButton').click(); before=state(); release(0,1)
                    page.wait_for_function('(n)=>window.retopoDemo.getState().guideErrors.length===n+1',arg=len(before['guideErrors']))
                    after=state()
                    check(after['guideDocument']==before['guideDocument'] and after['guideHistory']==before['guideHistory'],'Edit made during file read is preserved atomically')
                    check('changed while the file was loading' in page.locator('#guideErrorMessage').inner_text(),'Conflicting import explains why it was rejected')
                elif scenario in ('latest-import-wins','stale-invalid-read'):
                    empty=dict(packet,guides=[],curves=[]); upload(json.dumps(empty),'held-import-newer.json')
                    page.wait_for_function('window.__heldReads.length===2'); release(1,1)
                    page.wait_for_function('window.retopoDemo.getState().guideDocument.length===0'); before=state(); release(0,2); after=state()
                    check(not after['guideDocument'] and after['guideHistory']==before['guideHistory'],scenario+': an earlier read cannot override the newer accepted import')
                    check(after['guideErrors']==before['guideErrors'],scenario+': stale file completion cannot display an obsolete error')
                elif scenario=='construction-during-read':
                    page.locator('#topButton').click(); page.locator('[data-tool=polyline]').click()
                    for point in ([-.15,-.5,.22],[.15,-.5,.22]):
                        q=page.evaluate('(p)=>window.retopoDemo.projectPoint(p,0)',point); page.mouse.click(q['x'],q['y'])
                    before=state(); check(before['interaction']['activityId'] is not None,'A real clicked construction starts while the file read is pending')
                    release(0,1); page.wait_for_function('(n)=>window.retopoDemo.getState().guideErrors.length===n+1',arg=len(before['guideErrors'])); after=state()
                    check(after['guideDocument']==before['guideDocument'] and after['interaction']['activityId']==before['interaction']['activityId'],'Import cannot discard an unfinished native construction')
                    check('Finish or cancel' in page.locator('#guideErrorMessage').inner_text(),'Construction conflict asks for a deliberate finish or cancel')
                page.screenshot(path=str(OUT/(scenario+'.png')))
            except Exception:
                errors.append(scenario+': '+traceback.format_exc())
            finally: context.close()
        browser.close()
finally:
    server.terminate(); server.wait(timeout=20); log.close()
report=dict(passed=not errors and all(c['passed'] for c in checks),checks=checks,errors=errors,sourceHashes=hashes,
            scope='Native Chromium file input; exact File.text payloads held and released out of order. Real source switches, edits, clicked construction and legacy toilet guide files. No manufactured solver result.')
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=report['passed'],checks=len(checks),errors=errors)),flush=True)
raise SystemExit(0 if report['passed'] else 1)
