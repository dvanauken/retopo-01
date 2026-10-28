"""Browser checks for density controls and crease-aware source display; no solve."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/feature-ui';OUT.mkdir(exist_ok=True)
errors=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport=dict(width=1600,height=1000),device_scale_factor=1)
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8741',wait_until='networkidle')
    page.wait_for_function('window.retopoDemo?.getState().meshId')
    page.locator('#meshSelect').select_option('toilet')
    page.wait_for_function('window.retopoDemo.getState().meshId === "toilet" && !document.getElementById("generateButton").disabled')
    assert page.locator('#targetNumber').get_attribute('max')=='12000'
    page.locator('#targetNumber').fill('1800');page.locator('#targetNumber').press('Tab')
    assert page.evaluate('window.retopoDemo.getState().target')==1800
    assert page.locator('#densityWarning').is_visible()
    assert '7,200' in page.locator('#densityWarning').inner_text()
    page.locator('#targetNumber').fill('7200');page.locator('#targetNumber').press('Tab')
    assert page.evaluate('window.retopoDemo.getState().target')==7200
    assert page.locator('#densityWarning').is_hidden()
    page.locator('#sameButton').click()
    assert page.evaluate('window.retopoDemo.getState().target')==12000
    page.locator('#halfButton').click()
    assert page.evaluate('window.retopoDemo.getState().target')==6000
    assert page.locator('#doubleButton').is_disabled()
    assert page.locator('#creasesToggle').locator('..').inner_text()=='Detected creases'
    page.screenshot(path=str(OUT/'toilet.png'))
    # Source picking must survive the move to per-corner rendering normals.
    visible=page.evaluate('''() => {
      const box=document.getElementById('viewport').getBoundingClientRect();
      let hits=0;
      for(let y=box.top+20;y<box.bottom;y+=35) for(let x=box.left+20;x<box.left+box.width/2;x+=35)
        if(window.retopoDemo.pickSource(x,y,0)) hits++;
      return hits;
    }''')
    assert visible>10,visible
    page.locator('#meshSelect').select_option('hexagon')
    page.wait_for_function('window.retopoDemo.getState().meshId === "hexagon" && !document.getElementById("generateButton").disabled')
    assert page.locator('#targetNumber').get_attribute('max')=='1800'
    assert page.locator('#topologyMetric').inner_text()=='Geometry checked'
    assert not errors,errors
    (OUT/'result.json').write_text(json.dumps(dict(passed=True,sourcePickingHits=visible,errors=errors,scope='Actual browser controls and source rendering, without generation or substituted network responses.'),indent=2)+'\n')
    print('PASS density bounds, Half/Same/Double, crease display, source picking, quality labels; no browser errors')
    browser.close()
