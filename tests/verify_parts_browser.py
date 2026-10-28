"""Actual toilet partition, per-part solve, assembly download and reload."""
from pathlib import Path
import json,time,uuid,sys,argparse
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'runs'/('parts-browser-'+uuid.uuid4().hex[:8]);out.mkdir()
parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8741');args=parser.parse_args();url=args.url;errors=[];checks=[]
print('BROWSER',out,flush=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport=dict(width=1700,height=1100))
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(url,wait_until='networkidle');page.wait_for_function('window.retopoDemo?.getState().meshId === "hexagon"')
    page.locator('#meshSelect').select_option('toilet');page.wait_for_function('window.retopoDemo.getState().meshId === "toilet" && window.retopoDemo.getPartsState()?.parts[0].name === "White toilet"')
    page.locator('#partsSelection').evaluate('(e)=>e.open=true')
    page.locator('#partsHandle').click();assert page.evaluate('window.retopoDemo.getPartsState().selectedFaces.length')==273
    page.locator('#partsPreviewFaces').click();page.locator('#partsReview').wait_for(state='visible',timeout=120000)
    page.screenshot(path=str(out/'handle-preview.png'));page.locator('#partsCancel').click();assert len(page.evaluate('window.retopoDemo.getPartsState().parts'))==1
    checks.append('Cancel preview leaves original unchanged')
    page.locator('#partsPreviewFaces').click();page.locator('#partsReview').wait_for(state='visible',timeout=120000);page.locator('#partsApply').click()
    page.wait_for_function('window.retopoDemo.getPartsState().parts.length===2 && window.retopoDemo.getState().meshId.includes("--part-")')
    parts=page.evaluate('window.retopoDemo.getPartsState()');assert len([n for n in parts['parts'] if n['excluded']])==1;checks.append('Handle excluded; body closed and isolated')
    page.locator('#partsName').fill('Tank lid');page.locator('#partsExclude').uncheck();page.locator('#partsPlaneValue').fill('.82');page.locator('#partsPreviewPlane').click();page.locator('#partsReview').wait_for(state='visible',timeout=120000)
    page.screenshot(path=str(out/'lid-preview.png'));page.locator('#partsApply').click();page.wait_for_function('window.retopoDemo.getPartsState().parts.length===3 && document.getElementById("workspaceModelName").textContent === "Tank lid"')
    page.locator('#partsSelection').evaluate('(e)=>e.open=false')
    page.locator('#targetNumber').fill('800');page.locator('#targetNumber').press('Tab')
    with page.expect_response(lambda r:r.url.endswith('/api/remesh') and r.request.method=='POST') as submission:page.locator('#generateButton').click()
    response=submission.value;assert response.status==202,response.text();job=response.json()['id'];print('JOB',job,flush=True)
    (out/'job.json').write_text(json.dumps(dict(job=job,request=json.loads(response.request.post_data))))
    deadline=time.monotonic()+1500
    while time.monotonic()<deadline:
        state=page.evaluate('window.retopoDemo.getState()')
        if not state['busy']:
            assert state['lastAttempt']['phase']=='complete',state['lastAttempt'];break
        page.wait_for_timeout(1000)
    assert state['resultJob']==job;checks.append('Real selected-part worker accepted')
    accepted=page.evaluate('window.retopoDemo.getPartsState()');lid=next(n for n in accepted['parts'] if n['name']=='Tank lid');assert lid['result']['job']==job
    page.screenshot(path=str(out/'lid-generated.png'))
    with page.expect_download() as exported:page.locator('#partsExport').click()
    exported.value.save_as(str(out/'assembly.obj'));text=(out/'assembly.obj').read_text();assert text.count('\no ')==2;assert 'Flush_handle' not in text;assert '_retopo' in text and '_working_source' in text
    checks.append('Assembly exports lid output and retained source; excludes handle')
    with page.expect_download() as saved:page.locator('#partsSave').click()
    saved.value.save_as(str(out/'parts.json'))
    page.locator('#partsAssembly').click();page.wait_for_timeout(1000);page.screenshot(path=str(out/'assembly.png'))
    page.reload(wait_until='networkidle');page.wait_for_function('window.retopoDemo?.getState().meshId === "hexagon"');page.locator('#meshSelect').select_option('toilet');page.wait_for_function('window.retopoDemo.getPartsState()?.parts.length===3')
    page.get_by_role('button',name='Tank lid',exact=True).click();page.locator('#partsWork').click();page.wait_for_function('(job)=>window.retopoDemo.getState().resultJob===job',arg=job)
    assert page.evaluate('window.retopoDemo.getState().target')==800;checks.append('Reload restores per-part settings and accepted output')
    page.locator('#partsUndo').click();page.wait_for_function('window.retopoDemo.getPartsState().parts.length===2');page.locator('#partsUndo').click();page.wait_for_function('window.retopoDemo.getPartsState().parts.length===1 && window.retopoDemo.getState().meshId === "toilet"');checks.append('Undo splits restores original whole toilet')
    page.locator('#partsFile').set_input_files(str(out/'parts.json'));page.wait_for_function('window.retopoDemo.getPartsState().parts.length===3');checks.append('Parts project roundtrip')
    assert not errors,errors
    (out/'result.json').write_text(json.dumps(dict(passed=True,job=job,checks=checks,errors=errors),indent=2));(ROOT/'runs/parts-browser-latest.json').write_text(json.dumps(dict(directory=str(out),job=job)));print('PASSED',json.dumps(checks),flush=True)
    browser.close()
