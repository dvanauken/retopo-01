"""Actual browser drawing -> live worker -> measured/exported geometry verification."""
from pathlib import Path
import hashlib,json,math,os,socket,subprocess,sys,time,traceback,urllib.request,urllib.error
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));OUT=ROOT/'tests/verification';OUT.mkdir(exist_ok=True);SHOTS=ROOT/'tests/screenshots';SHOTS.mkdir(exist_ok=True)
checks=[];console=[];jobs=[]
def check(value,name):
 checks.append(dict(name=name,passed=bool(value)))
 if not value:raise AssertionError(name)
def write(p,data):p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def post(url,data,headers=None):
 request=urllib.request.Request(url,data=json.dumps(data).encode(),headers={'Content-Type':'application/json',**(headers or {})},method='POST')
 try:
  with urllib.request.urlopen(request,timeout=10) as response:return response.status,json.loads(response.read())
 except urllib.error.HTTPError as error:return error.code,json.loads(error.read())
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
URL=f'http://127.0.0.1:{port}';log=(OUT/'server.log').open('w',encoding='utf-8');server=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'server.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
 for _ in range(100):
  if server.poll() is not None:raise RuntimeError('Test server exited; see server.log')
  try:
   with urllib.request.urlopen(URL+'/api/health',timeout=1) as response:
    if response.status==200:break
  except Exception:time.sleep(.1)
 for label,payload in [('nonobject',[]),('unknown-mesh',dict(meshId='missing',target=600,curves=[])),('target-low',dict(meshId='hexagon',target=1,curves=[])),('nonfinite',dict(meshId='hexagon',target=600,curves=[[[0,0,0],[math.nan,0,0]]]))]:
  status,_=post(URL+'/api/remesh',payload);check(status==400,'API rejects '+label)
 status,_=post(URL+'/api/remesh',dict(meshId='hexagon',target=600,curves=[]),{'Origin':'https://example.invalid'});check(status==403,'API rejects foreign origin')
 before={p.name for p in (ROOT/'runs').iterdir() if p.is_dir()}
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True);context=browser.new_context(viewport=dict(width=1540,height=1020),device_scale_factor=1,accept_downloads=True)
  page=context.new_page();page.on('pageerror',lambda error:console.append(str(error)));requests=[];page.on('request',lambda request:requests.append(request.url))
  page.goto(URL,wait_until='networkidle');page.wait_for_function('window.retopoDemo?.getState().resultFaces === 736',timeout=30000);page.wait_for_timeout(500)
  state=page.evaluate('window.retopoDemo.getState()');check(state['meshId']=='hexagon' and not state['guides'],'Online source and explicit baseline load')
  box=page.locator('#generateButton').bounding_box();check(box['y']+box['height']<=1020,'Generate action stays visible')
  page.screenshot(path=str(SHOTS/'desktop-dark.png'),full_page=True)
  page.get_by_role('button',name='Top',exact=True).click();page.locator('#closedGuide').check();page.wait_for_timeout(400)
  points=[[.62*math.cos(a),.62*math.sin(a),1.] for a in [i*2*math.pi/80 for i in range(81)]]
  screen=page.evaluate('(points)=>points.map(window.retopoDemo.projectPoint)',points)
  page.mouse.move(screen[0]['x'],screen[0]['y']);page.mouse.down()
  for point in screen[1:]:page.mouse.move(point['x'],point['y'])
  page.mouse.up();state=page.evaluate('window.retopoDemo.getState()');curves=state['guides'];check(len(curves)==1 and len(curves[0])>20,'Real pointer stroke creates surface curve samples')
  check(math.dist(curves[0][0],curves[0][-1])<1e-6,'Pointer loop closes on its starting surface point');check(state['dirty'],'Changed curves mark previous result stale')
  write(OUT/'drawn-curves.json',dict(coordinateFrame='source',curves=curves))
  page.get_by_role('button',name='Generate retopology',exact=True).click();page.wait_for_function('!window.retopoDemo.getState().busy',timeout=180000)
  state=page.evaluate('window.retopoDemo.getState()');check(state['resultFaces']!=736 and not state['dirty'],'Live result changes after the actual drawn curve')
  created=[p for p in (ROOT/'runs').iterdir() if p.is_dir() and p.name not in before];check(len(created)==1,'One isolated original-input job was created');job=created[0];jobs.append(job.name)
  report=json.loads((job/'report.json').read_text());mesh=json.loads((job/'mesh.json').read_text());submitted=json.loads((job/'curves.json').read_text());check(report['passed'] and submitted['curves']==curves,'Worker uses exact browser-submitted surface curves')
  provenance=json.loads((job/'engine-provenance.json').read_text());check(bool(provenance['sourceHashes']) and all(Path(p).is_relative_to(ROOT/'engine') for p in provenance['sourceHashes']),'Loaded construction sources are inside this standalone project engine')
  check(mesh['stats']['quadFraction']==1 and mesh['stats']['eulerCharacteristic']==0 and mesh['stats']['boundaryEdges']==0 and mesh['stats']['nonmanifoldEdges']==0,'Actual drawn-guide result retains quads, closed surface and through-hole')
  import worker
  from measure_geometry import topology,guide_alignment,read_obj
  from measure_polygon_geometry import measure
  import numpy as np
  baseline=json.loads((ROOT/'assets/previews/hexagon.json').read_text());bv=np.asarray(baseline['vertices']);_,_,edges=topology(bv,baseline['faces']);curve=np.asarray(curves[0]);samples=curve[np.linspace(0,len(curve)-1,min(len(curve),129),dtype=int)];old=guide_alignment(bv,edges,samples);new=mesh['guideAlignment'][0]
  check(new['p95Distance']<.02 and new['p95Distance']<old['p95Distance']*.5,'Drawn guide improves actual edge registration over baseline')
  measured=measure(ROOT/'assets/models/hexagon.obj',job/'output.obj',curves,True);check(max(measured['sourceToOutput']['sampledMax'],measured['outputToSource']['sampledMax'])<2e-6,'Independent exported surface measurement preserves the online source')
  write(OUT/'drawn-output-measurement.json',dict(passed=True,baselineGuide=old,generatedGuide=new,geometry=measured,surfaceTolerance=2e-6,method='Independent rereading of actual exported polygons; deterministic bidirectional surface samples, incidence/Euler and nearest actual output edge registration. No output fitting.'))
  page.screenshot(path=str(SHOTS/'drawn-guide-result-dark.png'),full_page=True)
  with page.expect_download() as download:page.get_by_role('button',name='Export OBJ',exact=False).click()
  downloaded=OUT/'downloaded-output.obj';download.value.save_as(downloaded);check(sha(downloaded)==sha(job/'output.obj'),'Browser OBJ export is the actual generated mesh')
  with page.expect_download() as download:page.get_by_role('button',name='Save guides',exact=True).click()
  downloaded=OUT/'downloaded-guides.json';download.value.save_as(downloaded);check(json.loads(downloaded.read_text())['curves']==curves,'Browser guide export preserves drawn coordinates')
  page.get_by_role('button',name='Details',exact=True).click();check(page.locator('#detailsDialog').is_visible(),'Measured mesh details open');page.locator('#detailsDialog [data-close-dialog]').click()
  page.locator('[data-view=overlay]').click();check(page.evaluate('window.retopoDemo.getState().view')=='overlay','Overlay comparison works');page.screenshot(path=str(SHOTS/'overlay-dark.png'),full_page=True);page.locator('[data-view=split]').click()
  page.locator('[data-tool=erase]').click();point=page.evaluate('window.retopoDemo.projectPoint(window.retopoDemo.getState().guides[0][12])');page.mouse.click(point['x'],point['y']);check(not page.evaluate('window.retopoDemo.getState().guides'),'Surface erase removes the selected guide')
  page.locator('#undoButton').click();check(len(page.evaluate('window.retopoDemo.getState().guides'))==1,'Undo restores guide');page.locator('#redoButton').click();check(not page.evaluate('window.retopoDemo.getState().guides'),'Redo restores deletion');page.locator('#undoButton').click()
  page.locator('#targetNumber').fill('450');page.locator('#targetNumber').press('Tab');check(page.evaluate('window.retopoDemo.getState().target')==450 and page.evaluate('window.retopoDemo.getState().dirty'),'Density control changes the real request state')
  previous_faces=state['resultFaces'];page.get_by_role('button',name='Generate retopology',exact=True).click();page.wait_for_function('!window.retopoDemo.getState().busy',timeout=180000)
  next_jobs=[p for p in (ROOT/'runs').iterdir() if p.is_dir() and p.name not in before and p.name not in jobs];check(len(next_jobs)==1,'Changed density creates another actual solve');density_job=next_jobs[0];jobs.append(density_job.name)
  density_mesh=json.loads((density_job/'mesh.json').read_text());check(density_mesh['target']==450 and density_mesh['stats']['eulerCharacteristic']==0 and density_mesh['stats']['faces']!=mesh['stats']['faces'],'Density setting changes generated topology while retaining the hole')
  page.locator('#targetNumber').fill('600');page.locator('#targetNumber').press('Tab')
  page.get_by_role('button',name='Switch color theme').click();page.wait_for_timeout(300);check(page.locator('html').get_attribute('data-theme')=='light','Light theme works');page.screenshot(path=str(SHOTS/'desktop-light.png'),full_page=True)
  page.locator('#meshSelect').select_option('terrain');page.wait_for_function('window.retopoDemo.getState().meshId === "terrain" && window.retopoDemo.getState().resultFaces === 450');check(page.locator('#topologyMetric').inner_text()=='Passed','Open terrain example loads its measured mesh');page.screenshot(path=str(SHOTS/'terrain-light.png'),full_page=True)
  page.locator('#meshSelect').select_option('cylinder');page.wait_for_function('window.retopoDemo.getState().meshId === "cylinder" && window.retopoDemo.getState().resultFaces === 512');page.locator('#guideMode').select_option('1');check(page.evaluate('window.retopoDemo.getState().mode')==1,'Curved example exposes actual semantic guide modes')
  page.locator('#meshSelect').select_option('hexagon');page.wait_for_function('window.retopoDemo.getState().meshId === "hexagon" && !window.retopoDemo.getState().busy');page.wait_for_timeout(300);check(page.evaluate('window.retopoDemo.getState().guides')==curves,'Source switching restores saved surface guides')
  page.set_viewport_size(dict(width=390,height=844));page.wait_for_timeout(500);check(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'),'Narrow layout has no horizontal overflow');page.screenshot(path=str(SHOTS/'mobile-light.png'),full_page=True)
  page.set_viewport_size(dict(width=1360,height=850));page.wait_for_timeout(500);box=page.locator('#generateButton').bounding_box();check(box['y']+box['height']<=850,'Generate stays visible on a laptop viewport')
  # Cancel an owned job after the API creates it, without touching any other process.
  status,queued=post(URL+'/api/remesh',dict(meshId='hexagon',target=600,guideMode=2,curves=curves));check(status==202,'Valid solve is queued');jobs.append(queued['id']);status,cancelled=post(URL+'/api/jobs/'+queued['id']+'/cancel',{});check(status==200 and cancelled['state']=='cancelled','Owned worker cancellation reports cancelled, never passed')
  check(not console,'No browser JavaScript errors');check(all(url.startswith(URL) for url in requests),'Renderer and application request only local assets')
  browser.close()
 write(OUT/'result.json',dict(passed=all(c['passed'] for c in checks),checks=checks,browserErrors=console,jobs=jobs,source='Kenney Prototype Kit CC0 hollow hexagon, prepared source hash recorded in assets',sourceSha256=sha(ROOT/'assets/models/hexagon.obj'),workerSha256=sha(ROOT/'worker.py'),appSha256=sha(ROOT/'app.js'),scope='Actual headless Chromium pointer drawing, local API/worker generation and original-output geometry measurements, real downloads, controls, source switching, themes and responsive layout. Cached examples separately labeled. Tests do not establish every unsupported guide/mesh branch.'))
 print(json.dumps(dict(passed=True,checks=len(checks),jobs=jobs,guideP95Before=old['p95Distance'],guideP95After=new['p95Distance'])),flush=True)
except Exception:
 write(OUT/'result.json',dict(passed=False,checks=checks,browserErrors=console,jobs=jobs,error=traceback.format_exc()));traceback.print_exc();raise
finally:
 # Ensure a queued cancellation has time to leave its owned worker before stop.
 for job in jobs:
  try:post(URL+'/api/jobs/'+job+'/cancel',{})
  except Exception:pass
 time.sleep(.5);server.terminate();server.wait(timeout=20);log.close()
