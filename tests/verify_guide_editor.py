"""Real Chromium guide selection/editing, native capture, IO and worker evidence."""
from pathlib import Path
import hashlib,json,math,socket,subprocess,sys,time,traceback,urllib.request
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests/guide-editor';OUT.mkdir(exist_ok=True)
checks=[];errors=[];worker_jobs=[]
def check(value,name):
 checks.append({'name':name,'passed':bool(value)})
 print(('PASS ' if value else 'FAIL ')+name,flush=True)
 if not value:raise AssertionError(name)
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'
log=(OUT/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'server.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
 for _ in range(100):
  try:urllib.request.urlopen(url+'/api/health',timeout=1);break
  except Exception:time.sleep(.1)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True)
  context=browser.new_context(viewport={'width':1540,'height':1020},accept_downloads=True)
  page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(url,wait_until='networkidle');page.wait_for_function('window.retopoDemo?.getState().resultFaces > 0')
  if page.locator('html').get_attribute('data-theme')!='dark':page.locator('#themeButton').click()
  def state():return page.evaluate('window.retopoDemo.getState()')
  def doc():return state()['guideDocument']
  def screen(point,pane=0):
   a=page.evaluate('([p,pane])=>window.retopoDemo.projectPoint(p,pane)',[point,pane]);return {'x':a['x'],'y':a['y']}
  def tool(name):page.locator(f'[data-tool={name}]').click()
  def click(point,pane=0,**kwargs):page.mouse.click(**screen(point,pane),**kwargs)
  def dismiss():
   if page.locator('#guideErrorDialog').is_visible():page.locator('#guideErrorDialog button').click()
  def draw(points,pane=0):
   tool('draw');page.mouse.move(**screen(points[0],pane));page.mouse.down()
   for v in points[1:]:page.mouse.move(**screen(v,pane))
   page.mouse.up()
  page.locator('#topButton').click()
  a=[-.45,-.65,1];b=[0,-.7,1];c=[.45,-.65,1]
  # Escape must release real capture before pointer-up, and cancel the preview.
  page.mouse.move(**screen(a));page.mouse.down();page.mouse.move(**screen(b))
  check(page.evaluate('document.querySelector("#viewport").hasPointerCapture(1)'),'Native capture is held during a freehand gesture')
  page.keyboard.press('Escape')
  check(not page.evaluate('document.querySelector("#viewport").hasPointerCapture(1)'),'Escape releases native capture before physical pointer-up')
  check(not doc() and not state()['draft'],'Escape discards provisional geometry without history')
  page.mouse.up()
  # Clicked construction excludes hover; completion writes one command.
  tool('polyline');click(a);click(b);click(c);page.mouse.move(**screen([.5,-.6,1]));page.keyboard.press('Enter')
  check(len(doc())==1 and len(doc()[0]['points'])==3,'Polyline creates only its accepted click vertices')
  original=doc()[0];original_points=[v['position'] for v in original['points']]
  check(state()['guideHistory']['index']==1,'Polyline creation has one history entry')
  # Body chooses Object Selection, even on an unselected guide.
  tool('select');click([-.225,-.675,1]);s=state()
  check(s['interaction']['selection']['model']=='object' and s['interaction']['selection']['entityIds']==[original['id']],'Body click enters Object Selection')
  check(s['guideHistory']['index']==1,'Selection creates no document history')
  click([-.225,-.675,1],click_count=2,delay=70)
  check(state()['interaction']['selection']['model']=='direct','Double activation enters Direct Selection')
  page.screenshot(path=str(OUT/'direct-selection-dark.png'))
  # Move a visible vertex; the accepted document is unchanged during preview.
  start=screen(a);end=screen([-.38,-.72,1]);page.mouse.move(**start);page.mouse.down();page.mouse.move(**end,steps=8)
  check(doc()[0]==original,'Point drag leaves accepted document unchanged while held')
  check(bool(state()['interaction']['candidates']),'Point drag exposes a separate edit candidate')
  page.screenshot(path=str(OUT/'point-preview-dark.png'))
  page.mouse.up();edited=doc()[0]
  check(edited['id']==original['id'] and [v['id'] for v in edited['points']]==[v['id'] for v in original['points']],'Point editing preserves guide and point identities')
  check(math.dist(edited['points'][0]['position'],[-.38,-.72,1])<.002,'Point drag reaches the surface point at release')
  check(state()['guideHistory']['index']==2,'Point gesture creates exactly one undo unit')
  rev=state()['guideRevisions'][original['id']]
  page.keyboard.press('Control+z');check(doc()[0]==original,'Undo restores exact authored guide values')
  page.keyboard.press('Control+Shift+z');check(doc()[0]==edited and state()['guideRevisions'][original['id']]>rev,'Redo restores values with a newer runtime revision')
  # Two Escapes: cancel an in-progress edit, then leave Direct Selection.
  page.mouse.move(**screen(edited['points'][0]['position']));page.mouse.down();page.mouse.move(**screen([-.34,-.7,1]));page.keyboard.press('Escape');page.mouse.up()
  check(doc()[0]==edited and state()['interaction']['selection']['model']=='direct','First Escape cancels the point gesture and retains Direct Selection')
  page.keyboard.press('Escape');check(state()['interaction']['selection']['model']=='object','Ready Escape returns to Object Selection')
  # Direct drag from an unselected endpoint must latch in one pointer sequence.
  click([0,0,1]);start=screen(edited['points'][0]['position']);end=screen([-.4,-.7,1]);page.mouse.move(**start);page.mouse.down();page.mouse.move(**end,steps=8);page.mouse.up()
  check(state()['interaction']['selection']['model']=='direct' and math.dist(doc()[0]['points'][0]['position'],[-.4,-.7,1])<.002,'Unselected endpoint selects and edits in one drag')
  # Smooth spline with its own editable authored fit points.
  tool('spline');fits=[[-.3,-.8,1],[0,-.85,1],[.3,-.8,1]]
  for point in fits:click(point)
  activity=state()['interaction']['activityId'];page.keyboard.down('Space');page.keyboard.up('Space')
  check(state()['interaction']['activityId']==activity,'Temporary navigation preserves unfinished construction identity')
  page.keyboard.press('Enter');check(len(doc())==2 and doc()[1]['type']=='spline','Spline creates a distinct authored guide type')
  check(len(state()['guides'][1])>3 and len(doc()[1]['points'])==3,'Spline derives dense surface samples without authoring extra fit points')
  # Real right-pane edit and frame/point reprojection after camera changes.
  tool('select');page.locator('.guide-name').nth(1).click();page.keyboard.press('a')
  fit=doc()[1]['points'][1];page.mouse.move(**screen(fit['position'],1));page.mouse.down();page.mouse.move(**screen([0,-.82,1],1),steps=8);page.mouse.up()
  check(math.dist(doc()[1]['points'][1]['position'],[0,-.82,1])<.002,'Right-pane spline fit-point editing uses the original source surface')
  # An invalid release over the hole rejects; it cannot substitute the last valid preview.
  baseline=doc();history=state()['guideHistory']['index'];page.mouse.move(**screen(doc()[1]['points'][1]['position'],1));page.mouse.down();page.mouse.move(**screen([0,0,1],1),steps=12)
  check(state()['interaction']['invalid'],'Off-surface candidate is visibly invalid while held')
  page.mouse.up();check(doc()==baseline and state()['guideHistory']['index']==history,'Invalid release preserves exact accepted guides and history')
  check(len(state()['guideErrors'])==1 and page.locator('#guideErrorDialog').is_visible(),'Rejected submitted edit produces one incident and one visible dialog')
  dismiss()
  # Multi-selection uses one atomic surface move.
  page.locator('.guide-name').nth(0).click();page.keyboard.down('Shift');page.locator('.guide-name').nth(1).click();page.keyboard.up('Shift')
  check(len(state()['interaction']['selection']['entityIds'])==2,'Shift selection retains multiple guide identities')
  old=doc();history=state()['guideHistory']['index'];body=[-.15,-.675,1];start=screen(body)
  # Use an exact point on the first segment away from its endpoints.
  g=old[0];body=[(g['points'][0]['position'][i]+g['points'][1]['position'][i])/2 for i in range(3)];start=screen(body)
  page.mouse.move(**start);page.mouse.down();page.mouse.move(start['x'],start['y']-10,steps=8);page.mouse.up()
  check(all(a!=b for a,b in zip(old,doc())) and state()['guideHistory']['index']==history+1,'Multi-guide body drag changes all guides in one undo step')
  page.keyboard.press('Control+z');check(doc()==old,'One undo restores the complete multi-guide move')
  # Both rectangle directions use full containment, and membership is ephemeral.
  history=state()['guideHistory']['index'];tool('select');page.keyboard.press('Escape')
  for reverse in [False,True]:
   corners=[screen([-.7,-.98,1]),screen([.7,-.5,1])]
   if reverse:corners.reverse()
   page.mouse.move(**corners[0]);page.mouse.down();page.mouse.move(**corners[1],steps=10);page.mouse.up()
   check(len(state()['interaction']['selection']['entityIds'])==2,'Marquee fully contains both guides'+(' right-to-left' if reverse else ' left-to-right'))
  check(state()['guideHistory']['index']==history,'Marquee changes no document history')
  # Explicit model transitions preserve the complete object membership.
  page.keyboard.press('a');check(len(state()['interaction']['selection']['entityIds'])==2 and state()['interaction']['selection']['model']=='direct','Direct Selection retains multi-selection and edits its active owner')
  page.keyboard.press('v');check(len(state()['interaction']['selection']['entityIds'])==2,'Object Selection restores the retained guide membership')
  # Reverse and point deletion are exact, reversible authored operations.
  before=doc();page.locator('#reverseGuides').click();check(all(a['points']==list(reversed(b['points'])) for a,b in zip(doc(),before)),'Reverse preserves identities and reverses every selected authored point sequence')
  page.keyboard.press('Control+z');check(doc()==before,'Undo Reverse restores exact authored values')
  page.locator('.guide-name').nth(0).click();page.keyboard.press('a');click(doc()[0]['points'][1]['position']);before=doc();page.keyboard.press('Delete')
  check(len(doc()[0]['points'])==2 and doc()[0]['id']==before[0]['id'],'Direct Delete removes a selected point while preserving its owning guide')
  page.keyboard.press('Control+z');check(doc()==before,'Undo point deletion restores the same point identity')
  # Actual snapping uses the same source points as the indicator and edit.
  page.locator('#snapGuides').check();page.locator('.guide-name').nth(1).click();page.keyboard.press('a');before=doc()
  target=before[0]['points'][0]['position'];start=screen(before[1]['points'][1]['position']);near=screen(target)
  page.mouse.move(**start);page.mouse.down();page.mouse.move(near['x']+2,near['y']+2,steps=8);page.mouse.up()
  check(doc()[1]['points'][1]['position']==target,'Point snapping commits the exact indicated source point')
  page.keyboard.press('Control+z');page.keyboard.down('Alt');page.mouse.move(**start);page.mouse.down();page.mouse.move(near['x']+2,near['y']+2,steps=8);page.mouse.up();page.keyboard.up('Alt')
  check(doc()[1]['points'][1]['position']!=target,'Alt bypasses soft snapping through the final release sample')
  page.keyboard.press('Control+z');page.locator('#snapGuides').uncheck()
  # Native export preserves IDs, algorithms and source binding on reload.
  with page.expect_download() as download:page.locator('#exportGuides').click()
  target=OUT/'guides.json';download.value.save_as(str(target));packet=json.loads(target.read_text())
  check(packet['schemaVersion']==3 and packet['sourceSha256'] and packet['guides']==doc(),'Saved guide file carries authored records and source identity')
  page.locator('#clearButton').click();page.locator('#guideFile').set_input_files(str(target));page.wait_for_function('window.retopoDemo.getState().guideDocument.length===2')
  check(doc()==packet['guides'],'Guide import restores exact authored identities and spline parameters')
  # Refresh checks actual browser storage migration/roundtrip rather than an oracle.
  page.reload(wait_until='networkidle');page.wait_for_function('window.retopoDemo?.getState().guideDocument.length===2')
  check(doc()==packet['guides'],'Local persistence restores both guide types exactly after reload')
  page.locator('#topButton').click();tool('select');page.locator('.guide-name').nth(1).click();page.keyboard.press('a')
  page.locator('#themeButton').click();page.screenshot(path=str(OUT/'direct-selection-light.png'))
  page.set_viewport_size({'width':900,'height':800});page.screenshot(path=str(OUT/'narrow-light.png'))
  check(page.locator('#directSelection').is_visible() and page.locator('#viewport').bounding_box()['width']>200,'Selection controls remain accessible in narrow layout')
  page.set_viewport_size({'width':1540,'height':1020});page.locator('#topButton').click()
  # Real touch cancellation must never commit a provisional guide.
  tool('draw');before=doc();cdp=context.new_cdp_session(page);start=screen(a);end=screen(b)
  cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[start]});cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[end]});cdp.send('Input.dispatchTouchEvent',{'type':'touchCancel','touchPoints':[]})
  check(doc()==before and state()['interaction']['pointerId'] is None,'Native touch cancellation discards the guide and releases ownership')
  # A release without a delivered move still contributes its final position.
  page.locator('#clearButton').click();tool('draw');start=screen(a);end=screen(b);page.mouse.move(**start);page.mouse.down()
  cdp.send('Input.dispatchMouseEvent',{'type':'mouseReleased','x':end['x'],'y':end['y'],'button':'left','buttons':0,'clickCount':1})
  check(len(doc())==1 and math.dist(doc()[0]['points'][-1]['position'],b)<.002,'Pointer-up contributes movement even without a final pointer-move event')
  # Crossing the through-hole stages multiple parts and commits only once.
  page.locator('#clearButton').click();tool('draw');history=state()['guideHistory']['index'];start=screen([-.7,0,1]);end=screen([.7,0,1]);page.mouse.move(**start);page.mouse.down();page.mouse.move(**end,steps=30)
  check(not doc(),'Crossing empty space does not commit a partial stroke')
  page.mouse.up();check(len(doc())==2 and state()['guideHistory']['index']==history+1,'One stroke across the hole creates two surface guides in one undo unit')
  page.keyboard.press('Control+z');check(not doc(),'One undo removes every fragment of a split stroke')
  # Scope loss is terminal even while capture is held.
  start=screen(a);page.mouse.move(**start);page.mouse.down();page.mouse.move(**screen(b));page.evaluate('window.dispatchEvent(new Event("blur"))')
  check(not doc() and state()['interaction']['pointerId'] is None and not page.evaluate('document.querySelector("#viewport").hasPointerCapture(1)'),'Window context loss discards unfinished work and releases native capture')
  page.mouse.up()
  # Rejected construction remains repairable and never bridges a hole.
  tool('polyline');click([-.7,0,1]);click([.7,0,1]);page.keyboard.press('Enter')
  check(not doc() and state()['interaction']['activityId'] is not None,'A polyline through the hole is rejected with its accepted clicks retained for repair')
  dismiss();page.locator('#viewport').focus();page.keyboard.press('Escape')
  # Verify the unchanged worker API consumes the actual derived surface samples.
  tool('draw');page.locator('#closedGuide').check()
  loop=[[.64*math.cos(i*2*math.pi/80),.64*math.sin(i*2*math.pi/80),1] for i in range(81)]
  draw(loop);submitted=state()['guides'];check(len(submitted)==1 and doc()[0]['closed'],'Closed freehand guide uses explicit authored closure')
  page.locator('#generateButton').click();page.wait_for_function('!window.retopoDemo.getState().busy',timeout=180000)
  check(not state()['dirty'] and state()['resultFaces']>0,'Real worker solve accepts the new guide document adapter')
  worker_jobs.append(state()['resultJob'])
  with urllib.request.urlopen(url+'/api/jobs/'+state()['resultJob']+'/curves.json') as response:actual=json.load(response)
  check(actual['curves']==submitted,'Worker input contains exactly the editor-derived freehand samples')
  page.screenshot(path=str(OUT/'generated.png'))
  page.locator('#clearButton').click();tool('spline')
  fits=[[.64*math.cos(i*2*math.pi/8),.64*math.sin(i*2*math.pi/8),1] for i in range(8)]
  for point in fits:click(point)
  page.keyboard.press('Alt+Enter');check(len(doc())==1 and doc()[0]['type']=='spline' and doc()[0]['closed'] and len(doc()[0]['points'])==8,'Closed Spline retains eight authored fit points with no closing duplicate')
  spline_samples=state()['guides'];page.locator('#generateButton').click();page.wait_for_function('!window.retopoDemo.getState().busy',timeout=180000)
  check(not state()['dirty'] and state()['resultFaces']>0,'A real worker solve succeeds from the authored closed Spline')
  worker_jobs.append(state()['resultJob'])
  with urllib.request.urlopen(url+'/api/jobs/'+state()['resultJob']+'/curves.json') as response:actual=json.load(response)
  check(actual['curves']==spline_samples,'Spline worker input matches the actual projected and sampled guide')
  page.screenshot(path=str(OUT/'generated-spline.png'))
  for mesh in ['terrain','cylinder','hexagon']:
   page.locator('#meshSelect').select_option(mesh)
   page.wait_for_function('(id)=>window.retopoDemo.getState().meshId===id && window.retopoDemo.getState().resultFaces>0',arg=mesh)
   check(state()['meshId']==mesh,'Existing '+mesh+' source, preset guides and preview still load')
  check(not errors,'No browser JavaScript errors')
  browser.close()
 result={'passed':True,'checks':checks,'workerJobs':worker_jobs,'browserErrors':errors,'sourceHashes':{str(f.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'app.js',ROOT/'index.html',ROOT/'server.py',*sorted((ROOT/'src').rglob('*.js'))]},'scope':'Real Chromium pointer/keyboard/touch, native capture before pointer-up, surface editing, authored IO and real freehand and Spline worker solves.'}
 (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'passed':True,'checks':len(checks)}),flush=True)
except Exception:
 (OUT/'result.json').write_text(json.dumps({'passed':False,'checks':checks,'browserErrors':errors,'error':traceback.format_exc()},indent=2)+'\n',encoding='utf-8')
 if 'page' in locals():
  try:page.screenshot(path=str(OUT/'failure.png'))
  except Exception:pass
 raise
finally:
 server.terminate();server.wait(timeout=20);log.close()
