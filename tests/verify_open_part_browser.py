"""Real part-scoped Generate, persistence and OBJ download; no substituted solver."""
from pathlib import Path
from http.server import ThreadingHTTPServer
import argparse, hashlib, json, sys, threading, time, uuid
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import server
parser=argparse.ArgumentParser(); parser.add_argument('--guided', action='store_true'); parser.add_argument('--direct', action='store_true'); args=parser.parse_args()
if args.direct and args.guided: parser.error('--direct tests generation directly from assembly selection; --guided requires editing the part first')
out = ROOT / 'runs' / ('open-browser-' + uuid.uuid4().hex[:8]); out.mkdir()
print('EVIDENCE', out, flush=True)
http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
server.Handler.log_message = lambda *args: None
threading.Thread(target=http.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{http.server_port}'; errors = []; job = None; finished = False
source = ROOT / 'assets/raw/toilet-skp/SW_Toilet.skp'; source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
try:
 with sync_playwright() as pw:
  browser = pw.chromium.launch(headless=True); page = browser.new_page(viewport=dict(width=1700, height=1100))
  page.on('pageerror', lambda error: errors.append(str(error)))
  page.goto(url, wait_until='networkidle'); page.locator('#meshSelect').select_option('toilet-skp')
  page.wait_for_function('retopoDemo.getPartsState()?.visibleParts.length===11')
  if args.direct:
   camera=page.evaluate('retopoDemo.getCameraState()')
   page.locator('[data-part-id="skp-6"] .part-name').click()
   assert page.locator('#generateButton').is_enabled()
   assert page.locator('#generateButton').inner_text()=='Generate selected'
   assert page.evaluate('retopoDemo.getPartsState().active') is None
   assert page.evaluate('retopoDemo.getCameraState()')==camera
   page.keyboard.down('Shift'); page.locator('[data-part-id="skp-2"] .part-name').click(); page.keyboard.up('Shift')
   assert page.locator('#generateButton').is_disabled()
   assert 'exactly one' in page.locator('#generateButton').get_attribute('title')
   page.locator('[data-part-id="skp-6"] .part-name').click(); page.locator('#partsExcludeSelected').click()
   page.wait_for_function('retopoDemo.getPartsState().parts.find(p=>p.id==="skp-6").excluded')
   assert page.locator('#generateButton').is_disabled()
   page.locator('#partsRestoreAll').click()
  page.locator('[data-part-id="skp-2"] .part-name').click()
  if not args.direct:
   page.locator('#partsWork').click()
   page.wait_for_function('retopoDemo.getPartsState().active==="skp-2" && !document.getElementById("generateButton").disabled')
  wanted_target=550 if args.direct else 500
  page.locator('#targetNumber').fill(str(wanted_target)); page.locator('#targetNumber').press('Tab')
  if args.guided:
   page.locator('[data-tool="polyline"]').click()
   points=page.evaluate("""() => { const r=document.getElementById('viewport').getBoundingClientRect();
     for(let y=r.top+r.height*.5;y<r.top+r.height*.7;y+=15) for(let x=r.left+r.width*.18;x<r.left+r.width*.3;x+=15)
       if(retopoDemo.pickSource(x,y)&&retopoDemo.pickSource(x+70,y)) return [[x,y],[x+70,y]];
   }""")
   assert points
   for x,y in points: page.mouse.click(x,y)
   page.keyboard.press('Enter'); assert len(page.evaluate('retopoDemo.getState().guides'))==1
   page.keyboard.press('v'); page.locator('[data-part-id="skp-2"] .part-name').click()
  with page.expect_response(lambda r: r.url.endswith('/api/remesh') and r.request.method == 'POST') as response:
   page.locator('#generateButton').click()
  response = response.value; assert response.status == 202, response.text(); job = response.json()['id']
  submitted=json.loads(response.request.post_data)
  assert submitted['target']==wanted_target
  assert submitted['partSource']==next(p['partSource'] for p in json.loads((ROOT/'assets/models/toilet-skp.json').read_text())['initialParts'] if p['id']=='skp-2')
  assert page.evaluate('retopoDemo.getPartsState().active')=='skp-2'
  (out/'submitted.json').write_text(response.request.post_data, encoding='utf-8'); print('JOB', job, flush=True)
  page.wait_for_function('!retopoDemo.getState().busy', timeout=300000)
  state = page.evaluate('retopoDemo.getState()'); assert state['lastAttempt']['phase'] == 'complete', state['lastAttempt']
  assert state['resultJob'] == job; finished = True
  result = page.request.get(url+f'/api/jobs/{job}/mesh.json').json()
  assert result['openSurface'] and result['boundaryValidation']['passed']
  for key in ('quality', 'surfaceValidation', 'intersectionValidation', 'featureValidation'): assert result[key]['passed'], (key, result[key])
  activity=page.locator('#logList').inner_text()
  for message in ['Starting generation', 'Building open-part layout', 'quads accepted; all checks passed', 'Output is ready to view and export']:
   assert message in activity,(message,activity)
  assert page.locator('[data-dock-panel="log"]').is_visible()
  with page.expect_download() as saved_log: page.locator('#save-log').click()
  saved_log.value.save_as(str(out/'activity.txt'))
  assert job[:8] in (out/'activity.txt').read_text(encoding='utf-8')
  assert result['stats']['boundaryEdges'] > 0
  assert result['guideCount']==(1 if args.guided else 0)
  with page.expect_download() as download: page.locator('#exportMesh').click()
  download.value.save_as(str(out/'generated.obj')); assert (out/'generated.obj').read_bytes() == (ROOT/'runs'/job/'output.obj').read_bytes()
  page.locator('#partsShowAll').click(); page.wait_for_function('retopoDemo.getPartsState().viewMode==="assembly"')
  assert page.evaluate('retopoDemo.getPartsState().selectedParts') == ['skp-2']
  page.wait_for_function('document.getElementById("resultEmpty").hidden && document.getElementById("resultMeta").textContent.includes("1 accepted part")')
  page.locator('[data-part-id="skp-3"] .part-name').click(); page.locator('#partsWork').click()
  page.wait_for_function('retopoDemo.getPartsState().active==="skp-3"')
  assert page.evaluate('retopoDemo.getState().resultJob') is None
  page.locator('[data-part-id="skp-2"] .part-name').click(); page.locator('#partsWork').click()
  page.wait_for_function('(id)=>retopoDemo.getState().resultJob===id', arg=job)
  page.locator('#partsKeepSelected').click()
  with page.expect_download() as download: page.locator('#partsExport').click()
  download.value.save_as(str(out/'one-part-assembly.obj'))
  exported = (out/'one-part-assembly.obj').read_text(); assert exported.count('\no ') == 1 and '_retopo' in exported
  page.reload(wait_until='networkidle'); page.locator('#meshSelect').select_option('toilet-skp')
  page.wait_for_function('retopoDemo.getPartsState()?.parts.length===11')
  assert len(page.evaluate('retopoDemo.getPartsState().parts.filter(p=>!p.excluded)')) == 1
  page.locator('[data-part-id="skp-2"] .part-name').click(); page.locator('#partsWork').click()
  page.wait_for_function('(id)=>retopoDemo.getState().resultJob===id', arg=job)
  page.screenshot(path=str(out/'accepted.png'))
  # A new calculation can be cancelled without discarding the last accepted result.
  page.locator('#targetNumber').fill('9000'); page.locator('#targetNumber').press('Tab')
  with page.expect_response(lambda r: r.url.endswith('/api/remesh') and r.request.method == 'POST') as cancel_response:
   page.locator('#generateButton').click()
  cancel_id=cancel_response.value.json()['id']; page.locator('#cancelButton').click()
  page.wait_for_function('!retopoDemo.getState().busy', timeout=30000)
  assert page.evaluate('retopoDemo.getState().resultJob')==job
  assert page.evaluate('retopoDemo.getState().lastAttempt.phase')=='cancelled'
  assert page.request.get(url+f'/api/jobs/{cancel_id}').json()['state']=='cancelled'
  assert source_hash == hashlib.sha256(source.read_bytes()).hexdigest() and not errors, errors
  report = dict(passed=True, directSelection=args.direct, job=job, faces=len(result['faces']), guideCount=result['guideCount'], boundary=result['boundaryValidation'], sourceSha256=source_hash, errors=errors,
                checks=['real worker and all acceptance gates', 'byte-identical native OBJ download', 'selection retained across assembly view', 'independent sibling state', 'one-part generated assembly export', 'reload retains inclusion and accepted result', 'original SKP unchanged', 'cancellation retains accepted result'])
  (out/'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8'); print(json.dumps(report), flush=True)
  browser.close()
finally:
 if job and not finished:
  import urllib.request
  try: urllib.request.urlopen(urllib.request.Request(url+f'/api/jobs/{job}/cancel', data=b'{}', headers={'Content-Type':'application/json'}))
  except Exception: pass
 http.shutdown(); http.server_close()
