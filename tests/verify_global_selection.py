"""Real pointer checks for shared part selection and uninterrupted navigation."""
from pathlib import Path
from http.server import ThreadingHTTPServer
import json, sys, threading
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import server
out = ROOT / 'runs/draw3d-review'; out.mkdir(exist_ok=True)
server.Handler.log_message = lambda *args: None
http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
threading.Thread(target=http.serve_forever, daemon=True).start()
errors = []; checks = []
try:
 with sync_playwright() as pw:
  browser = pw.chromium.launch(headless=True); page = browser.new_page(viewport=dict(width=1700, height=1100))
  page.on('pageerror', lambda e: errors.append(str(e)))
  page.goto(f'http://127.0.0.1:{http.server_port}', wait_until='networkidle')
  page.locator('#meshSelect').select_option('toilet-skp')
  page.wait_for_function('window.retopoDemo.getPartsState()?.parts.length === 11')
  page.wait_for_function('retopoDemo.getPartsState().visibleParts.length === 11', timeout=60000)
  page.wait_for_timeout(200)
  def parts(): return page.evaluate('window.retopoDemo.getPartsState()')
  def state(): return page.evaluate('window.retopoDemo.getState()')
  def camera(): return page.evaluate('window.retopoDemo.getCameraState()')
  # Query observations only; selection itself always goes through real pointer input.
  targets = page.evaluate('''() => {
    const r = document.getElementById('viewport').getBoundingClientRect(), found = {};
    for (let y=r.top+35;y<r.bottom-30;y+=12) for(let x=r.left+15;x<r.left+r.width/2-15;x+=12) {
      const id=retopoDemo.pickPart(x,y); if(id && !found[id]) found[id]={x,y};
    } return found;
  }''')
  page.screenshot(path=str(out/'initial.png'))
  assert len(targets) >= 3, (targets, errors)
  entries = list(targets.items()); a, b = entries[:2]
  before = camera(); history = state()['guideHistory']
  page.mouse.click(**a[1]); assert parts()['selectedParts'] == [a[0][5:]]
  assert parts()['active'] is None and camera() == before
  assert page.locator('#generateButton').is_enabled()
  assert page.locator('#generateButton').inner_text() == 'Generate selected'
  checks.append('Viewport click selects the visible part without isolation or camera motion')
  page.keyboard.down('Shift'); page.mouse.click(**b[1]); page.keyboard.up('Shift')
  assert len(parts()['selectedParts']) == 2
  assert page.locator('#partsWork').is_disabled()
  assert page.locator('#generateButton').is_disabled()
  page.keyboard.down('Shift'); page.mouse.click(**b[1]); page.keyboard.up('Shift')
  assert parts()['selectedParts'] == [a[0][5:]]
  checks.append('Shift toggles shared object selection; work requires exactly one part')
  page.locator('#partsWork').click(); page.wait_for_function('(id)=>retopoDemo.getPartsState().active===id', arg=a[0][5:])
  assert parts()['viewMode'] == 'working'
  page.locator('#partsShowAll').click(); page.wait_for_function('retopoDemo.getPartsState().viewMode==="assembly"')
  checks.append('Work on selected isolates a part; Show assembly restores context')
  page.locator(f'[data-part-id="{a[0][5:]}"] .part-name').click()
  page.locator('#partsExcludeSelected').click(); page.wait_for_function('(id)=>retopoDemo.getPartsState().parts.find(p=>p.id===id).excluded', arg=a[0][5:])
  assert a[0] != page.evaluate('(p)=>retopoDemo.pickPart(p.x,p.y)', a[1])
  page.locator('#partsRestoreAll').click(); page.wait_for_function('retopoDemo.getPartsState().parts.every(p=>!p.excluded)')
  checks.append('Excluded parts disappear from picking; Restore all restores open imports')
  page.locator(f'[data-part-id="{a[0][5:]}"] .part-name').click(); page.locator('#partsKeepSelected').click()
  page.wait_for_function('retopoDemo.getPartsState().parts.filter(p=>!p.excluded).length===1')
  with page.expect_download() as exported: page.locator('#partsExport').click()
  exported.value.save_as(str(out/'one-part.obj'))
  assert (out/'one-part.obj').read_text().count('\no ') == 1
  page.locator('#partsRestoreAll').click(); page.wait_for_function('retopoDemo.getPartsState().visibleParts.length===11')
  checks.append('Keep only selected and assembly export retain exactly one chosen source part')
  page.locator('#partsUndoEdit').click(); page.wait_for_function('retopoDemo.getPartsState().parts.filter(p=>!p.excluded).length===1')
  page.locator('#partsUndoEdit').click(); page.wait_for_function('retopoDemo.getPartsState().parts.every(p=>!p.excluded)')
  page.locator('#partsRedoEdit').click(); page.wait_for_function('retopoDemo.getPartsState().parts.filter(p=>!p.excluded).length===1')
  page.locator('#partsRestoreAll').click(); page.wait_for_function('retopoDemo.getPartsState().visibleParts.length===11')
  checks.append('Keep-only and restore each undo atomically; redo restores the entire inclusion command')
  page.locator(f'[data-part-id="{b[0][5:]}"] .part-name').click()
  selected = parts()['selectedParts']; before = camera()
  r = page.locator('#viewport').bounding_box(); x=r['x']+r['width']*.3; y=r['y']+r['height']*.45
  def drag(button, dx, dy):
   page.mouse.move(x,y); page.mouse.down(button=button); page.mouse.move(x+dx,y+dy,steps=12); page.mouse.up(button=button)
  drag('middle',65,25); after=camera()
  assert after['position'] != before['position'] and after['target'] == before['target']
  assert abs(after['distance']-before['distance']) < 1e-8 and parts()['selectedParts']==selected
  before=camera(); page.keyboard.down('Shift'); drag('middle',40,20); page.keyboard.up('Shift'); after=camera()
  assert after['target'] != before['target'] and abs(after['distance']-before['distance']) < 1e-8
  assert not after['navigating'] and not state()['interaction']['temporary']
  assert state()['guideHistory'] == history
  checks.append('Orbit preserves target/distance; Shift-middle pan translates camera and target without changing selection/history')
  page.locator('#partsShowAll').click(); page.keyboard.press('v')
  before=camera(); page.keyboard.press('f'); after=camera()
  def direction(c): return [(p-t)/c['distance'] for p,t in zip(c['position'],c['target'])]
  assert max(abs(a-b) for a,b in zip(direction(before),direction(after))) < 1e-8
  page.mouse.click(r['x']+10, r['y']+20); assert not parts()['selectedParts']
  page.keyboard.press('f'); page.wait_for_timeout(150)
  # Both drag directions use containment. Camera and authored geometry are unchanged.
  page.mouse.move(r['x']+5,r['y']+5); page.mouse.down(); page.mouse.move(r['x']+r['width']/2-5,r['y']+r['height']-5,steps=10); page.mouse.up()
  assert len(parts()['selectedParts']) >= 3, parts()['selectedParts']
  checks.append('Fit preserves orientation; empty click clears; marquee selects contained visible parts')
  contained=state()['interaction']['selection']['entityIds']
  page.locator(f'[data-part-id="{b[0][5:]}"] .part-name').click()
  page.keyboard.down('Shift'); page.mouse.move(r['x']+r['width']/2-5,r['y']+r['height']-5); page.mouse.down(); page.mouse.move(r['x']+5,r['y']+5,steps=10); page.mouse.up(); page.keyboard.up('Shift')
  assert state()['interaction']['selection']['entityIds']==[b[0]]+[id for id in contained if id!=b[0]]
  assert state()['interaction']['selection']['activeEntityId']==b[0]
  page.keyboard.press('Control+a'); assert len(parts()['selectedParts'])==11
  selection=state()['interaction']['selection']; page.locator('#targetNumber').focus(); page.keyboard.press('Control+a')
  assert state()['interaction']['selection']==selection
  checks.append('Reverse marquee uses ordered Shift-union; Select All selects objects while input fields retain keyboard ownership')
  page.locator(f'[data-part-id="{b[0][5:]}"] .part-name').click(); page.locator('#partsWork').click()
  page.wait_for_function('(id)=>retopoDemo.getPartsState().active===id',arg=b[0][5:])
  page.wait_for_timeout(250)
  samples=page.evaluate('''() => {
    const r=document.getElementById('viewport').getBoundingClientRect(), out=[];
    for(let y=r.top+80;y<r.bottom-80 && out.length<4;y+=20) for(let x=r.left+80;x<r.left+r.width/2-80 && out.length<4;x+=20) {
      const p=retopoDemo.pickSource(x,y);if(p)out.push({x,y,p});
    }return out;
  }''')
  assert len(samples)>2
  page.locator('[data-tool="polyline"]').click()
  for p in samples[:2]: page.mouse.click(p['x'],p['y'])
  draft=state()['interaction']; before_history=state()['guideHistory']
  assert draft['constructionType']=='polyline'
  drag('right',25,12)
  assert state()['interaction']['activityId']==draft['activityId'] and state()['draft']==draft['draft'][-1]
  assert state()['guideHistory']==before_history
  page.keyboard.press('Enter'); assert len(state()['guideDocument'])==1
  page.keyboard.press('v'); page.locator('.guide-name').click()
  page.keyboard.down('Shift'); page.locator(f'[data-part-id="{b[0][5:]}"] .part-name').click(); page.keyboard.up('Shift')
  assert len(state()['interaction']['selection']['entityIds'])==2
  checks.append('Temporary pan preserves unfinished Polyline identity and points; guides and parts share one selection')
  page.keyboard.press('h'); before=camera(); drag('left',15,10)
  assert camera()['target']!=before['target'] and not state()['interaction']['temporary']
  page.mouse.move(x,y);page.mouse.down(button='middle');page.mouse.move(x+10,y+5)
  page.keyboard.press('Escape');page.mouse.up(button='middle')
  assert not camera()['navigating'] and not state()['interaction']['temporary']
  assert not page.evaluate('document.getElementById("viewport").hasPointerCapture(1)')
  checks.append('Pan action resumes Select; Escape ends navigation and releases capture')
  # Cursor anchoring uses a real source point lying on the current target-depth plane.
  anchor=camera()['target']; anchor_screen=page.evaluate('(p)=>retopoDemo.projectPoint(p)',anchor)
  page.mouse.move(anchor_screen['x'],anchor_screen['y']);page.mouse.wheel(0,-120);page.wait_for_timeout(100)
  projected=page.evaluate('(p)=>retopoDemo.projectPoint(p)',anchor)
  assert abs(projected['x']-anchor_screen['x'])<.5 and abs(projected['y']-anchor_screen['y'])<.5, (projected, anchor_screen)
  checks.append('Wheel zoom retains its target-plane cursor anchor')
  page.locator('[data-tool="polyline"]').click()
  first=page.evaluate('retopoDemo.projectPoint(retopoDemo.getState().guides[0][0])')
  page.mouse.click(first['x'],first['y']); assert state()['interaction']['constructionType']=='polyline'
  page.mouse.move(x,y);page.mouse.down(button='middle');page.mouse.move(x+10,y+5)
  page.keyboard.press('Escape');page.mouse.up(button='middle')
  assert state()['interaction']['activityId'] is None and state()['tool']=='select'
  assert not camera()['navigating'] and not state()['interaction']['temporary']
  checks.append('Escape during temporary navigation discards the unfinished pair and returns to global Select')
  page.locator('#partsShowAll').click(); page.keyboard.press('v'); page.keyboard.press('f')
  page.locator(f'[data-part-id="{b[0][5:]}"] .part-name').click()
  page.wait_for_timeout(400); page.screenshot(path=str(out/'selection.png'))
  assert not errors, errors
  (out/'interaction-result.json').write_text(json.dumps(dict(passed=True, checks=checks, errors=errors),indent=2))
  print(json.dumps(checks,indent=2)); browser.close()
finally:
 http.shutdown(); http.server_close()
