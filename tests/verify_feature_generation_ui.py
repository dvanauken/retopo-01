"""Real browser submission, accepted feature result and native OBJ download."""
from pathlib import Path
import argparse,hashlib,json,time,uuid
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--url',default='http://127.0.0.1:8741');ap.add_argument('--case',choices=['bowl','four'],default='bowl');args=ap.parse_args()
out=ROOT/'runs'/('feature-browser-'+uuid.uuid4().hex[:8]);out.mkdir()
packet=(ROOT/'tests/toilet-sampled-worker/integrated-fallback/bowl-only-1800/curves.json' if args.case=='bowl' else ROOT/'tests/fixtures/toilet-four-guides.json')
curves=json.loads(packet.read_text())['curves'];errors=[];job_id=None;finished=False
print('BROWSER',out,flush=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport=dict(width=1700,height=1050),device_scale_factor=1)
    page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto(args.url,wait_until='networkidle')
        page.wait_for_function('window.retopoDemo?.getState().meshId')
        page.locator('#meshSelect').select_option('toilet')
        page.wait_for_function('window.retopoDemo.getState().meshId === "toilet" && !document.getElementById("generateButton").disabled')
        model=page.request.get(args.url+'/api/mesh/toilet').json()
        assert model.get('featureLayout'),'The live app has not enabled feature layout'
        guide_packet=dict(coordinateFrame='source',sourceSha256=model['sourceSha256'],curves=curves)
        page.locator('#guideFile').set_input_files(dict(name='toilet-guides.json',mimeType='application/json',buffer=json.dumps(guide_packet).encode()))
        page.wait_for_function('(n)=>window.retopoDemo.getState().guides.length===n',arg=len(curves))
        page.locator('#targetNumber').fill('7200');page.locator('#targetNumber').press('Tab')
        with page.expect_response(lambda response:response.url.endswith('/api/remesh') and response.request.method=='POST') as admission:
            page.locator('#generateButton').click()
        response=admission.value;assert response.status==202,response.text();job_id=response.json()['id']
        (out/'submitted.json').write_text(response.request.post_data+'\n')
        (out/'job.json').write_text(json.dumps(dict(id=job_id,url=args.url),indent=2))
        print('JOB',job_id,flush=True);deadline=time.monotonic()+1530;last_stage=None
        while time.monotonic()<deadline:
            state=page.evaluate('''() => { const s=window.retopoDemo.getState(); return {busy:s.busy,lastAttempt:s.lastAttempt,resultJob:s.resultJob,resultFaces:s.resultFaces}; }''')
            stage=page.locator('#processTitle').inner_text()
            if stage!=last_stage:print(stage,flush=True);last_stage=stage
            if not state['busy']:
                assert state['lastAttempt']['phase']=='complete',state
                assert state['resultJob']==job_id,state
                finished=True;break
            page.wait_for_timeout(1000)
        assert finished,'Browser solve did not complete within the observation limit'
        mesh=page.request.get(args.url+f'/api/jobs/{job_id}/mesh.json').json()
        assert mesh['featurePolicy']=='enforced' and mesh['featureValidation']['passed']
        assert mesh['quality']['passed'] and mesh['surfaceValidation']['passed'] and mesh['intersectionValidation']['passed']
        assert mesh['guideCount']==len(curves) and len(mesh['guidePaths'])==len(curves)
        assert page.locator('#topologyMetric').inner_text()=='Checks passed'
        assert page.locator('#resultBadge').inner_text()=='Generated'
        page.screenshot(path=str(out/'generated.png'))
        with page.expect_download() as exported:page.locator('#exportMesh').click()
        exported.value.save_as(str(out/'download.obj'))
        actual=ROOT/'runs'/job_id/'output.obj'
        assert (out/'download.obj').read_bytes()==actual.read_bytes()
        page.locator('#detailsButton').click()
        assert 'Source feature preservation' in page.locator('#detailsContent').inner_text()
        page.locator('#detailsDialog').evaluate('(dialog)=>dialog.close()')
        page.locator('#targetNumber').fill('7300');page.locator('#targetNumber').press('Tab')
        assert page.locator('#resultBadge').inner_text()=='Needs update'
        assert 'Previous result' in page.locator('#resultSummary').inner_text()
        assert not errors,errors
        report=dict(passed=True,jobId=job_id,faces=len(mesh['faces']),guideCount=len(curves),elapsedSeconds=mesh['elapsedSeconds'],downloadSha256=hashlib.sha256(actual.read_bytes()).hexdigest(),errors=errors,scope='Actual browser Generate, live service/worker, accepted feature checks, native byte-identical OBJ download, and stale-result label. No substituted responses or geometry.')
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print('BROWSER VERIFIED',json.dumps(report),flush=True)
    finally:
        if job_id and not finished:
            try:page.request.post(args.url+f'/api/jobs/{job_id}/cancel',data={},timeout=10000)
            except Exception:pass
        browser.close()
