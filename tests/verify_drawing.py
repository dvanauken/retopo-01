from pathlib import Path
import hashlib,json,math,socket,subprocess,sys,time,traceback,urllib.request
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'tests/drawing-fix';OUT.mkdir(exist_ok=True)
checks=[];errors=[];job=None
def check(value,name):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def get(path):
 with urllib.request.urlopen(URL+path,timeout=10) as r:return json.load(r)
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
URL=f'http://127.0.0.1:{port}'
log=(OUT/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'server.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
 for _ in range(100):
  try:get('/api/health');break
  except Exception:time.sleep(.1)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1540,'height':1020},accept_downloads=True)
  page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(URL,wait_until='networkidle');page.wait_for_function('window.retopoDemo?.getState().resultFaces===736')
  def state():return page.evaluate('window.retopoDemo.getState()')
  def project(points,pane=0):
   screen=page.evaluate('(pts)=>pts.map(p=>window.retopoDemo.projectPoint(p))',points)
   offset=page.locator('#viewport').bounding_box()['width']/2 if pane and state()['view']=='split' else 0
   return [{'x':v['x']+offset,'y':v['y']} for v in screen]
  def stroke(points,pane=0,shot=None):
   screen=project(points,pane);page.mouse.move(**screen[0]);page.mouse.down()
   check(len(state()['draft'])==1,'Pointer down shows immediate surface point'+(' right' if pane else ' left'))
   for v in screen[1:]:page.mouse.move(**v)
   if shot:page.screenshot(path=str(OUT/shot))
   page.mouse.up()
  arc=[[.64*math.cos(a),.64*math.sin(a),1.] for a in [-1.8+i*.9/25 for i in range(26)]]
  stroke(arc,shot='default-left-live.png');left=state()['guides'];check(len(left)==1 and len(left[0])>20,'Default isometric source freehand drawing works')
  page.locator('#undoButton').click();page.locator('#guidesToggle').uncheck()
  stroke(arc,1,'default-right-live-dark.png');right=state()['guides']
  check(page.locator('#guidesToggle').is_checked(),'Drawing enables hidden guide display')
  write(OUT/'pane-comparison.json',{'left':left,'right':right,'canvasBounds':page.locator('#viewport').bounding_box(),'sourceCoordinateTolerance':1e-5,'toleranceReason':'Chromium pointer client coordinates lose subpixel precision at different screen X positions; tolerance is 0.0005 percent of source extent.'})
  print(json.dumps({'leftPoints':len(left[0]),'rightPoints':len(right[0]),'startDifference':math.dist(left[0][0],right[0][0]),'endDifference':math.dist(left[0][-1],right[0][-1])}),flush=True)
  check(len(right)==1 and len(right[0])==len(left[0]) and max(math.dist(a,b) for a,b in zip(right[0],left[0]))<1e-5,'Equivalent left and right gestures attach to the same original source positions')
  page.locator('[data-tool=erase]').click();point=project([right[0][len(right[0])//2]],1)[0];page.mouse.click(**point)
  check(not state()['guides'],'Erase works on the right comparison mesh')
  page.locator('#undoButton').click();check(state()['guides']==right,'Undo restores right-pane guide')
  page.locator('#clearButton').click();page.locator('[data-tool=draw]').click();page.locator('#topButton').click();page.locator('#closedGuide').check()
  loop=[[.62*math.cos(i*2*math.pi/80),.62*math.sin(i*2*math.pi/80),1.] for i in range(81)]
  stroke(loop,1,'right-loop-live-dark.png');curves=state()['guides'];check(len(curves)==1 and math.dist(curves[0][0],curves[0][-1])<1e-6,'Right-pane freehand loop closes on its original source point')
  before={x.name for x in (ROOT/'runs').iterdir() if x.is_dir()}
  page.locator('#generateButton').click();page.wait_for_function('!window.retopoDemo.getState().busy',timeout=180000)
  new=[x for x in (ROOT/'runs').iterdir() if x.is_dir() and x.name not in before];check(len(new)==1,'Right-pane guides create one new real worker solve');job=new[0]
  result=json.loads((job/'mesh.json').read_text());submitted=json.loads((job/'curves.json').read_text())
  check(submitted['curves']==curves and json.loads((job/'report.json').read_text())['passed'],'Worker successfully uses exact right-pane surface curves')
  check(not state()['dirty'] and result['stats']['faces']!=736 and result['stats']['quadFraction']==1 and result['stats']['eulerCharacteristic']==0 and result['stats']['boundaryEdges']==0 and result['stats']['nonmanifoldEdges']==0,'Generated geometry changes and retains quads and a closed through-hole')
  check(result['guideAlignment'][0]['p95Distance']<.02,'Actual generated edges follow the drawn guide')
  write(OUT/'right-pane-curves.json',{'coordinateFrame':'source','curves':curves});page.screenshot(path=str(OUT/'generated-right-guide-dark.png'))
  page.locator('#themeButton').click();page.screenshot(path=str(OUT/'generated-right-guide-light.png'));check(page.locator('html').get_attribute('data-theme')=='light','Drawing and result checked in light theme')
  page.locator('[data-view=overlay]').click();page.locator('#closedGuide').uncheck();before_count=len(state()['guides']);stroke(arc,shot='overlay-live-light.png');check(len(state()['guides'])==before_count+1,'Overlay freehand still works')
  # Touch input uses real Chromium touch dispatch rather than invoking application handlers.
  page.locator('[data-view=split]').click();page.locator('#clearButton').click();session=context.new_cdp_session(page)
  points=project(arc,1);session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':points[0]['x'],'y':points[0]['y']}]})
  for point in points[1:]:session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[point]})
  session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});check(len(state()['guides'])==1,'Touch drag creates a surface guide in the right pane')
  page.locator('#clearButton').click();points=project(arc);session.send('Input.dispatchMouseEvent',{'type':'mousePressed','x':points[0]['x'],'y':points[0]['y'],'button':'left','buttons':1,'clickCount':1,'pointerType':'pen'})
  for point in points[1:]:session.send('Input.dispatchMouseEvent',{'type':'mouseMoved',**point,'button':'left','buttons':1,'pointerType':'pen'})
  session.send('Input.dispatchMouseEvent',{'type':'mouseReleased',**points[-1],'button':'left','buttons':0,'clickCount':1,'pointerType':'pen'});check(len(state()['guides'])==1,'Pen drag creates a surface guide')
  # The two views cannot be joined accidentally by a single captured pointer.
  page.locator('#clearButton').click();box=page.locator('#viewport').bounding_box();start=project([arc[0]])[0];page.mouse.move(**start);page.mouse.down();page.mouse.move(box['x']+box['width']*.75,start['y'],steps=30);page.mouse.up()
  check(all(len(c)<2 or max(math.dist(a,b) for a,b in zip(c,c[1:]))<.15 for c in state()['guides']),'Crossing the divider never bridges between view coordinates')
  check(not errors,'No browser JavaScript errors')
  browser.close()
 write(OUT/'result.json',{'passed':True,'checks':checks,'browserErrors':errors,'job':job.name,'appSha256':hashlib.sha256((ROOT/'app.js').read_bytes()).hexdigest(),'indexSha256':hashlib.sha256((ROOT/'index.html').read_bytes()).hexdigest(),'guideP95':result['guideAlignment'][0]['p95Distance'],'faces':result['stats']['faces'],'scope':'Real Chromium mouse, touch and pen input. Default isometric left/right, overlay, visibility, erase/undo, closed loop, one actual remesh from right-pane curves. No native algorithm equivalence claim.'})
 print(json.dumps({'passed':True,'checks':len(checks),'job':job.name,'faces':result['stats']['faces'],'guideP95':result['guideAlignment'][0]['p95Distance']}),flush=True)
except Exception:
 write(OUT/'result.json',{'passed':False,'checks':checks,'browserErrors':errors,'error':traceback.format_exc()});raise
finally:
 server.terminate();server.wait(timeout=20);log.close()
