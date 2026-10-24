"""Native input checks for 5-CSS-pixel closure, Circle and the real white toilet."""
from pathlib import Path
import json,math,subprocess,socket,sys,time,traceback,urllib.request,hashlib
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'tests/guide-additions';OUT.mkdir(exist_ok=True)
checks=[];errors=[];jobs=[]
def check(value,name):
 checks.append({'name':name,'passed':bool(value)});print(('PASS ' if value else 'FAIL ')+name,flush=True)
 if not value:raise AssertionError(name)
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}';log=(OUT/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'server.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
 for _ in range(100):
  try:urllib.request.urlopen(url+'/api/health',timeout=1);break
  except Exception:time.sleep(.1)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1540,'height':1020},device_scale_factor=2,accept_downloads=True)
  page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(url,wait_until='networkidle');page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
  if page.locator('html').get_attribute('data-theme')!='dark':page.locator('#themeButton').click()
  page.locator('#topButton').click()
  def state():return page.evaluate('window.retopoDemo.getState()')
  def doc():return state()['guideDocument']
  def screen(point,pane=0):
   a=page.evaluate('([p,pane])=>window.retopoDemo.projectPoint(p,pane)',[point,pane]);return {'x':a['x'],'y':a['y']}
  def tool(name):page.locator(f'[data-tool={name}]').click()
  def clear():
   if page.locator('#clearButton').is_enabled():page.locator('#clearButton').click()
  def click(point,pane=0):page.mouse.click(**screen(point,pane))
  def pixel_green(point,pane=0):
   return page.evaluate('''([p,pane])=>{const q=window.retopoDemo.projectPoint(p,pane),canvas=document.querySelector('#guideChrome'),r=canvas.getBoundingClientRect(),s=canvas.width/r.width;return [...canvas.getContext('2d').getImageData(Math.round((q.x-r.left)*s),Math.round((q.y-r.top)*s),1,1).data];}''',[point,pane])
  # Closure acquisition is independent of the ordinary snapping checkbox.
  for name,pane in [('polyline',0),('spline',1)]:
   clear();tool(name);fits=[[.64*math.cos(i*math.pi/4),.64*math.sin(i*math.pi/4),1] for i in range(8)]
   for point in fits:click(point,pane)
   start=screen(fits[0],pane);page.mouse.move(start['x']+5.5,start['y'])
   check(state()['interaction']['closureSnap'] is None,name+' remains open outside 5 CSS pixels at DPR 2')
   page.mouse.move(start['x']+4.5,start['y']);s=state();check(s['interaction']['closureSnap']['position']==doc()[0]['points'][0]['position'] if doc() else s['interaction']['closureSnap'] is not None,name+' acquires the first point inside 5 CSS pixels')
   rgb=pixel_green(fits[0],pane);check(rgb[1]>rgb[0]+25 and rgb[1]>rgb[2]+20,name+' first point is actually painted green')
   page.screenshot(path=str(OUT/(name+'-green-close.png')))
   check(not doc(),name+' closed preview has not mutated the document')
   page.mouse.click(start['x']+4.5,start['y']);check(len(doc())==1 and doc()[0]['closed'] and len(doc()[0]['points'])==8,name+' proximity click closes without a duplicate authored endpoint')
  clear();tool('draw');loop=[[.64*math.cos(i*2*math.pi/40),.64*math.sin(i*2*math.pi/40),1] for i in range(40)]
  page.mouse.move(**screen(loop[0]));page.mouse.down()
  for point in loop[1:]:page.mouse.move(**screen(point))
  start=screen(loop[0]);page.mouse.move(start['x']+4,start['y']);check(state()['interaction']['closureSnap'] is not None,'Freehand shows closure snap with Close next stroke unchecked')
  page.mouse.up();check(len(doc())==1 and doc()[0]['closed'],'Freehand release snaps closed atomically')
  # Circle construction over an empty center is important for annular guides.
  clear();tool('circle');click([0,0,1]);page.mouse.move(**screen([.64,0,1]));s=state()
  check(not doc() and s['interaction']['constructionPreview']['type']=='circle','Circle previews an analytic primitive without committing')
  check(abs(s['interaction']['constructionPreview']['radius']-.64)<.002,'Circle center over the hole resolves to the rim source plane')
  page.screenshot(path=str(OUT/'circle-preview.png'));click([.64,0,1]);g=doc()[0]
  check(g['type']=='circle' and g['closed'] and len(g['points'])==1,'Circle stores a center and radius rather than a polygon approximation')
  tool('select');click([0,.64,1],1);check(state()['interaction']['selection']['model']=='direct','Circle body enters its center/radius editor directly')
  check(page.locator('#reverseGuides').is_disabled(),'Circle does not advertise path reversal')
  old=doc();history=state()['guideHistory']['index'];start=screen([.64,0,1],1);end=screen([.69,0,1],1)
  page.mouse.move(**start);page.mouse.down();page.mouse.move(**end,steps=8)
  check(doc()==old,'Circle radius drag changes only its preview while held')
  page.mouse.up();check(abs(doc()[0]['radius']-.69)<.002 and state()['guideHistory']['index']==history+1,'Circle radius edit commits one undo unit')
  radius=doc()[0]['radius'];center=doc()[0]['points'][0]['position'];start=screen(center,1);end=screen([.02,.01,1],1)
  page.mouse.move(**start);page.mouse.down();page.mouse.move(**screen([.08,.04,1],1),steps=6);page.mouse.move(**end,steps=6);page.mouse.up()
  check(math.dist(doc()[0]['points'][0]['position'],[.02,.01,1])<.002 and doc()[0]['radius']==radius,'Circle center handle moves over the hole without changing its radius')
  page.keyboard.press('Control+z');page.keyboard.press('Control+Shift+z');check(doc()[0]['id']==g['id'],'Circle history preserves authored identity')
  with page.expect_download() as download:page.locator('#exportGuides').click()
  native=OUT/'circle-guides.json';download.value.save_as(str(native));packet=json.loads(native.read_text());check(packet['schemaVersion']==3 and packet['guides']==doc(),'Circle export preserves its analytic native record')
  clear();page.locator('#guideFile').set_input_files(str(native));page.wait_for_function('window.retopoDemo.getState().guideDocument.length===1');check(doc()==packet['guides'],'Circle import restores exact center, radius and plane values')
  page.locator('#generateButton').click();page.wait_for_function('!window.retopoDemo.getState().busy',timeout=180000)
  check(not state()['dirty'] and state()['resultJob'],'Circle drives a real retopology solve');jobs.append(state()['resultJob']);page.screenshot(path=str(OUT/'circle-generated.png'))
  # Imported original plain fixture: actual geometry, material and surface input.
  page.locator('#meshSelect').select_option('toilet');page.wait_for_function('window.retopoDemo.getState().meshId==="toilet" && window.retopoDemo.getState().sourceStats?.faces===24000');page.locator('[data-view=overlay]').click()
  check(state()['sourceStats']['boundaryEdges']==0 and state()['sourceStats']['nonmanifoldEdges']==0 and state()['sourceStats']['zeroAreaFanTriangles']==0,'White toilet is a closed nondegenerate source mesh')
  check(state()['sourceMaterial']['color']=='f5f5f2' and state()['sourceMaterial']['metalness']==0,'Toilet uses the plain white nonmetallic material')
  page.locator('#wireToggle').uncheck();page.screenshot(path=str(OUT/'white-toilet-dark.png'))
  page.locator('#themeButton').click();check(state()['sourceMaterial']['color']=='f5f5f2','Toilet stays white when the host theme changes');page.screenshot(path=str(OUT/'white-toilet-light.png'))
  check(len(doc())==1 and len(state()['guides'][0])>100,'Toilet loads its real bowl-surface contour test guide')
  clear();tool('draw');box=page.locator('#viewport').bounding_box();found=None
  for y in [.3,.4,.5,.6]:
   for x in [.4,.5,.6]:
    px=box['x']+box['width']*x;py=box['y']+box['height']*y
    pair=page.evaluate('([x,y])=>[window.retopoDemo.pickSource(x,y),window.retopoDemo.pickSource(x+12,y)]',[px,py])
    if all(pair):found=(px,py);break
   if found:break
  check(found is not None,'Toilet picking finds its actual surface')
  page.mouse.move(*found);page.mouse.down();page.mouse.move(found[0]+12,found[1],steps=6);page.mouse.up()
  check(len(doc())==1 and doc()[0]['type']=='polyline','A native freehand stroke attaches to the imported toilet mesh')
  check(not errors,'No browser JavaScript errors');browser.close()
 result={'passed':True,'checks':checks,'browserErrors':errors,'workerJobs':jobs,'sourceHashes':{str(f.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'app.js',ROOT/'index.html',ROOT/'server.py',*sorted((ROOT/'src').rglob('*.js'))]}}
 (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({'passed':True,'checks':len(checks)}),flush=True)
except Exception:
 (OUT/'result.json').write_text(json.dumps({'passed':False,'checks':checks,'browserErrors':errors,'error':traceback.format_exc()},indent=2)+'\n',encoding='utf-8');raise
finally:
 server.terminate();server.wait(timeout=20);log.close()
