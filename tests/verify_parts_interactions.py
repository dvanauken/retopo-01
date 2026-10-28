"""Visible face painting, part guide isolation and retained results after restart."""
from pathlib import Path
import json,time,argparse
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'runs/parts-interactions';out.mkdir(exist_ok=True);errors=[];checks=[]
parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8741');args=parser.parse_args()
previous=json.loads((ROOT/'runs/parts-browser-latest.json').read_text());packet=Path(previous['directory'])/'parts.json';previous_job=previous['job']
project=json.loads(packet.read_text());remainder_name=next(n['name'] for n in project['nodes'].values() if not n.get('children') and 'remainder' in n['name'])
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport=dict(width=1700,height=1100));page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(args.url,wait_until='networkidle');page.wait_for_function('window.retopoDemo?.getState().meshId === "hexagon"');page.locator('#meshSelect').select_option('toilet');page.wait_for_function('window.retopoDemo.getState().meshId === "toilet" && window.retopoDemo.getPartsState()?.parts[0].name === "White toilet"')
    page.locator('#partsSelection').evaluate('(e)=>e.open=true');page.locator('#partsPaint').click()
    # Find an actual visible point, then use real pointer events, not selection hooks.
    point=page.evaluate('''() => { const r=document.getElementById('viewport').getBoundingClientRect(); for(let y=r.top+r.height*.35;y<r.bottom-60;y+=30)for(let x=r.left+80;x<r.left+r.width/2-80;x+=30)if(window.retopoDemo.pickSource(x,y,0))return {x,y}; }''')
    assert point
    page.mouse.click(point['x'],point['y']);selected=page.evaluate('window.retopoDemo.getPartsState().selectedFaces.length');assert selected>0
    assert page.evaluate('window.retopoDemo.getState().guides.length')==1
    page.locator('#partsGrow').click();assert page.evaluate('window.retopoDemo.getPartsState().selectedFaces.length')>selected
    page.locator('#partsClear').click();assert page.evaluate('window.retopoDemo.getPartsState().selectedFaces.length')==0
    page.mouse.click(point['x'],point['y']);page.keyboard.down('Alt');page.mouse.click(point['x'],point['y']);page.keyboard.up('Alt');assert page.evaluate('window.retopoDemo.getPartsState().selectedFaces.length')==0
    checks.append('Visible face brush, grow, clear and Alt removal; existing guides unchanged')
    # Switching source while preview is pending must not hide the next source.
    page.locator('#partsHandle').click()
    page.route('**/api/parts/split',lambda route:(time.sleep(.4),route.continue_()))
    page.locator('#partsPreviewFaces').click();page.locator('#meshSelect').select_option('hexagon');page.wait_for_function('window.retopoDemo.getState().meshId === "hexagon"');page.wait_for_timeout(1000)
    assert not page.evaluate('window.retopoDemo.getPartsState().preview');assert page.evaluate('window.retopoDemo.getPartsState().parts.length')==1
    page.unroute('**/api/parts/split');checks.append('Late preview discarded after source switch')
    page.locator('#meshSelect').select_option('toilet');page.wait_for_function('window.retopoDemo.getState().meshId === "toilet"')
    page.locator('#partsFile').set_input_files(str(packet));page.wait_for_function('window.retopoDemo.getPartsState().parts.length===3')
    page.get_by_role('button',name='Tank lid',exact=True).click();page.locator('#partsWork').click();page.wait_for_function('(job)=>window.retopoDemo.getState().resultJob === job',arg=previous_job)
    with page.expect_download() as exported:page.locator('#exportMesh').click()
    exported.value.save_as(str(out/'restored-lid.obj'));assert (out/'restored-lid.obj').read_bytes()==(ROOT/'runs'/previous_job/'output.obj').read_bytes()
    checks.append('Accepted part and native OBJ survive service restart')
    # Draw a short guide by clicking two visible points on the isolated lid.
    page.locator('[data-tool="polyline"]').click()
    points=page.evaluate('''() => {const r=document.getElementById('viewport').getBoundingClientRect(); for(let y=r.top+60;y<r.bottom-60;y+=15)for(let x=r.left+80;x<r.left+r.width/2-120;x+=15) if(window.retopoDemo.pickSource(x,y,0)&&window.retopoDemo.pickSource(x+45,y,0))return [[x,y],[x+45,y]];}''')
    assert points
    for x,y in points:page.mouse.click(x,y)
    page.keyboard.press('Enter');page.wait_for_function('window.retopoDemo.getState().guides.length===1')
    page.locator('#targetNumber').fill('850');page.locator('#targetNumber').press('Tab');guide=page.evaluate('window.retopoDemo.getState().guides')
    assert page.locator('#resultBadge').inner_text()=='Needs update';page.locator('#partsExport').click();assert 'changed since its accepted output' in page.locator('#noticeText').inner_text();checks.append('Stale part blocked from assembly export')
    remainder=page.locator('.part-row').filter(has=page.get_by_role('button',name=remainder_name,exact=True))
    remainder.locator('.part-name').click();page.locator('#partsWork').click();page.wait_for_function('document.getElementById("workspaceModelName").textContent.includes("remainder")');assert page.evaluate('window.retopoDemo.getState().guides.length')==0
    page.get_by_role('button',name='Tank lid',exact=True).click();page.locator('#partsWork').click();page.wait_for_function('document.getElementById("workspaceModelName").textContent === "Tank lid" && window.retopoDemo.getState().guides.length===1')
    assert page.evaluate('window.retopoDemo.getState().guides')==guide;assert page.evaluate('window.retopoDemo.getState().target')==850
    assert page.locator('#resultBadge').inner_text()=='Needs update';checks.append('Part guides and target isolated; previous accepted output retained')
    assert not errors,errors;page.screenshot(path=str(out/'part-guide.png'))
    with page.expect_response(lambda r:r.url.endswith('/api/remesh') and r.request.method=='POST') as generated:page.locator('#generateButton').click()
    response=generated.value;assert response.status==202,response.text();guided_job=response.json()['id'];print('GUIDED JOB',guided_job,flush=True)
    (out/'guided-job.json').write_text(json.dumps(dict(job=guided_job,request=json.loads(response.request.post_data))))
    deadline=time.monotonic()+1500
    while time.monotonic()<deadline:
        state=page.evaluate('window.retopoDemo.getState()')
        if not state['busy']:
            assert state['lastAttempt']['phase']=='complete',state['lastAttempt'];break
        page.wait_for_timeout(1000)
    assert state['resultJob']==guided_job;assert state['guides']==guide;assert not state['dirty']
    checks.append('Actual guided lid regeneration passes while sibling parts stay unchanged')
    page.screenshot(path=str(out/'guided-lid-generated.png'))
    (out/'result.json').write_text(json.dumps(dict(passed=True,checks=checks,errors=errors),indent=2));print('PASSED',json.dumps(checks),flush=True);browser.close()
