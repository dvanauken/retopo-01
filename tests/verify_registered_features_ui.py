"""Verify actual browser Generate, worker gates, download identity and reload.

A fresh browser context is used for each matrix case. There are no network
stubs, injected geometry or manual job completion messages.
"""
from pathlib import Path
import argparse, json, os, sys, threading, time, traceback
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from verify_registered_features import CASES, GUIDE, read, write, sha, code_identity, engine_identity

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--case',action='append',choices=[c[0] for c in CASES]);ap.add_argument('--guide',type=Path,default=GUIDE)
    ap.add_argument('--crease-angle',type=float,default=30.);ap.add_argument('--timeout',type=float,default=720.)
    ap.add_argument('--expect-rejection',action='store_true');ap.add_argument('--url');ap.add_argument('--env',action='append',default=[],metavar='NAME=VALUE');a=ap.parse_args()
    out=a.out.resolve()
    if not out.is_relative_to(ROOT):ap.error('Evidence must remain in workspace')
    out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    (out/'worker-matrix-helper.py').write_bytes((ROOT/'tests/verify_registered_features.py').read_bytes())
    overrides={k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}
    for item in a.env:
        if '=' not in item:ap.error('--env must be NAME=VALUE')
        k,v=item.split('=',1);overrides[k]=v
    os.environ.update(overrides)
    import server
    from playwright.sync_api import sync_playwright
    http=None
    if a.url:url=a.url.rstrip('/')
    else:
        http=server.LocalHTTPServer(('127.0.0.1',0),server.Handler)
        server.Handler.log_message=lambda *args:None
        threading.Thread(target=http.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{http.server_port}'
    model=read(ROOT/'assets/models/toilet-skp.json');before=code_identity(ROOT);packet=read(a.guide)
    result=dict(url=url,command=sys.argv,environmentOverrides=overrides,codeBefore=before,
                guideSha256=sha(a.guide),engineBefore=engine_identity(ROOT,os.environ),expectRejection=a.expect_rejection,cases=[],scope='Actual browser controls, HTTP admission, worker, export and reload; no mocked responses.')
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            try:
                for case in CASES:
                    if a.case and case[0] not in a.case:continue
                    name,part_id,target,guided=case;folder=out/name;folder.mkdir()
                    context=browser.new_context(viewport=dict(width=1700,height=1100),device_scale_factor=1)
                    page=context.new_page();errors=[];network=[];console=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('requestfailed',lambda r:network.append(dict(url=r.url,failure=r.failure)))
                    page.on('response',lambda r:network.append(dict(url=r.url,status=r.status)) if r.status>=400 else None)
                    page.on('console',lambda m:console.append(dict(type=m.type,text=m.text)) if m.type in ('error','warning') else None)
                    row=dict(case=name,part=part_id,target=target,guided=guided,passed=False);job=None;finished=False;started=time.monotonic()
                    try:
                        page.goto(url,wait_until='networkidle');page.locator('#meshSelect').select_option('toilet-skp')
                        page.wait_for_function('retopoDemo.getPartsState()?.visibleParts.length===11')
                        page.locator(f'[data-part-id="{part_id}"] .part-name').click();page.locator('#partsWork').click()
                        page.wait_for_function('(part)=>retopoDemo.getPartsState().active===part && !document.getElementById("generateButton").disabled',arg=part_id)
                        part=next(p for p in model['initialParts'] if p['id']==part_id)
                        source=page.request.get(url+'/api/parts/'+part['partSource']).json()
                        if guided:
                            upload=dict(coordinateFrame='source',sourceSha256=source['sourceSha256'],curves=packet['curves'])
                            page.locator('#guideFile').set_input_files(dict(name='authored-guide.json',mimeType='application/json',buffer=json.dumps(upload).encode()))
                            page.wait_for_function('(n)=>retopoDemo.getState().guides.length===n',arg=len(packet['curves']))
                        page.locator('#targetNumber').fill(str(target));page.locator('#targetNumber').press('Tab')
                        page.locator('#creaseAngle').fill(str(a.crease_angle));page.locator('#creaseAngle').press('Tab')
                        with page.expect_response(lambda r:r.url.endswith('/api/remesh') and r.request.method=='POST') as admission:
                            page.locator('#generateButton').click()
                        response=admission.value;assert response.status==202,response.text();job=response.json()['id'];row['job']=job
                        submitted=json.loads(response.request.post_data);write(folder/'submitted.json',submitted)
                        assert submitted['target']==target and submitted['partSource']==part['partSource'],submitted
                        assert submitted['creaseAngle']==a.crease_angle,submitted
                        assert len(submitted['curves'])==(len(packet['curves']) if guided else 0),submitted
                        print('UI START',name,job,flush=True);previous=None
                        while time.monotonic()-started<a.timeout:
                            state=page.evaluate('retopoDemo.getState()')
                            stage=page.locator('#processTitle').inner_text()
                            if stage!=previous:print('UI PROGRESS',name,stage,flush=True);previous=stage
                            if not state['busy']:finished=True;break
                            page.wait_for_timeout(1000)
                        assert finished,'Observation timeout'
                        row['lastAttempt']=state.get('lastAttempt');write(folder/'final-state.json',state)
                        page.screenshot(path=str(folder/'result.png'))
                        if a.expect_rejection:
                            assert state['lastAttempt']['phase']=='failed',state['lastAttempt']
                            assert state.get('resultJob')!=job,'Rejected result was promoted'
                            assert sha(ROOT/'runs/parts'/part['partSource']/'source.obj')==source['sourceSha256']
                            assert not errors,errors
                            row.update(passed=True,expectedRejection=True,workerAccepted=False)
                            continue
                        assert state['lastAttempt']['phase']=='complete',state['lastAttempt']
                        assert state['resultJob']==job,state
                        mesh=page.request.get(url+f'/api/jobs/{job}/mesh.json').json()
                        for key in ('quality','surfaceValidation','intersectionValidation','featureValidation')+(('boundaryValidation',) if mesh.get('openSurface') else ()):
                            assert mesh[key]['passed'],(key,mesh[key])
                        assert mesh['guideCount']==len(submitted['curves'])
                        assert bool(mesh.get('openSurface'))==(source.get('solver')=='open-surface-quads')
                        with page.expect_download() as download:page.locator('#exportMesh').click()
                        download.value.save_as(str(folder/'download.obj'))
                        actual=ROOT/'runs'/job/'output.obj'
                        assert (folder/'download.obj').read_bytes()==actual.read_bytes(),'Downloaded OBJ differs from accepted output'
                        page.reload(wait_until='networkidle');page.locator('#meshSelect').select_option('toilet-skp')
                        page.wait_for_function('retopoDemo.getPartsState()?.parts.length===11')
                        page.locator(f'[data-part-id="{part_id}"] .part-name').click();page.locator('#partsWork').click()
                        page.wait_for_function('(id)=>retopoDemo.getState().resultJob===id',arg=job)
                        assert page.evaluate('retopoDemo.getState().target')==target
                        assert not errors,errors
                        row.update(passed=True,workerAccepted=True,faces=len(mesh['faces']),outputSha256=sha(actual),sourceSha256=source['sourceSha256'])
                    except Exception as error:
                        row.update(error=str(error),traceback=traceback.format_exc())
                        try:write(folder/'failure-state.json',page.evaluate('({state:retopoDemo.getState(),parts:retopoDemo.getPartsState()})'))
                        except Exception:pass
                        try:page.screenshot(path=str(folder/'failure.png'))
                        except Exception:pass
                    finally:
                        if job and not finished:
                            try:page.request.post(url+f'/api/jobs/{job}/cancel',data={},timeout=10000)
                            except Exception:pass
                        row.update(errors=errors,networkDiagnostics=network,consoleDiagnostics=console,observedSeconds=time.monotonic()-started)
                        write(folder/'result.json',row);result['cases'].append(row);write(out/'result.json',result)
                        print('UI RESULT',name,row['passed'],row.get('faces'),row.get('error',''),flush=True);context.close()
            finally:browser.close()
    finally:
        if http:http.shutdown();http.server_close()
    result['codeAfter']=code_identity(ROOT);result['engineAfter']=engine_identity(ROOT,os.environ)
    result['codeStable']=before==result['codeAfter'] and result['engineBefore']==result['engineAfter'];result['allPassed']=all(r['passed'] for r in result['cases'])
    result['allWorkersAccepted']=all(r.get('workerAccepted',False) for r in result['cases'])
    write(out/'result.json',result)
    return 0 if result['allPassed'] and result['codeStable'] else 1

if __name__=='__main__':raise SystemExit(main())

