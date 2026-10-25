"""Ribbon, five-region layout, theme, resizing, focus and contextual properties."""
from pathlib import Path
import json,socket,subprocess,sys,time,traceback,urllib.request,hashlib
from playwright.sync_api import sync_playwright
ROOT=Path('C:\\dbva\\code\\retopo-1\\runs\\frozen-boundary-service');OUT=Path('C:\\dbva\\code\\retopo-1\\tests\\toilet-final-audit\\workspace');OUT.mkdir(exist_ok=True)
checks=[];errors=[]
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
  browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1600,'height':1050},accept_downloads=True);page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(url,wait_until='networkidle');page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
  def state():return page.evaluate('window.retopoDemo.getState()')
  def box(selector):return page.locator(selector).bounding_box()
  def tab(name):page.locator(f'[data-ribbon-tab={name}]').click()
  def screen(point):
   p=page.evaluate('p=>window.retopoDemo.projectPoint(p)',point);return {'x':p['x'],'y':p['y']}
  check(page.locator('html').get_attribute('data-theme')=='light','New workspace defaults to the requested light theme')
  colors=page.evaluate('''()=>({primary:getComputedStyle(document.querySelector('#generateButton')).backgroundColor,gold:getComputedStyle(document.querySelector('[data-ribbon-tab=home]'),'::after').backgroundColor,panel:getComputedStyle(document.querySelector('.inspector')).backgroundColor})''')
  check(colors['primary']=='rgb(36, 99, 207)' and colors['gold']=='rgb(181, 136, 44)' and colors['panel']=='rgb(255, 255, 255)','Blue primary, gold accent and white neutral surfaces are applied')
  north,west,center,east,south=[box(s) for s in ['.ribbon','.navigator','.workspace','.inspector','.bottom-dock']]
  check(north['y']+north['height']<=center['y']+1 and west['x']<center['x'] and east['x']>=center['x']+center['width'] and south['y']>=center['y']+center['height'],'Ribbon, navigator, center, inspector and bottom dock occupy their standard regions')
  check(page.locator('[data-tool] svg').count()==page.locator('[data-tool]').count(),'Every guide tool uses a flat SVG icon')
  page.screenshot(path=str(OUT/'light-desktop.png'))
  # Shell interaction must preserve an unfinished guide and its accepted world points.
  page.locator('#topButton').click();page.locator('[data-tool=spline]').click()
  for point in [[-.4,-.65,1],[0,-.7,1],[.4,-.65,1]]:page.mouse.click(**screen(point))
  activity=state()['interaction']['activityId'];before=state()['draft'];tab('view')
  check(state()['interaction']['activityId']==activity and state()['draft']==before,'Ribbon tab focus preserves unfinished construction')
  width=box('#viewport')['width'];page.locator('#toggle-inspector').click()
  check(box('#viewport')['width']>width+200 and state()['interaction']['activityId']==activity,'Collapsing properties grows the canvas without discarding construction')
  page.locator('#toggle-inspector').click();height=box('#viewport')['height'];page.locator('#toggle-ribbon').click()
  check(box('#viewport')['height']>height+60 and state()['interaction']['activityId']==activity,'Ribbon collapse preserves the activity and gives its space to the viewport')
  page.locator('#toggle-ribbon').click()
  splitter=box('[data-splitter=west]');old_width=box('.navigator')['width'];page.mouse.move(splitter['x']+2,splitter['y']+60);page.mouse.down();page.mouse.move(splitter['x']+37,splitter['y']+60,steps=8);page.mouse.up()
  check(abs(box('.navigator')['width']-old_width-35)<2 and state()['interaction']['activityId']==activity,'Native splitter dragging resizes the navigator and preserves accepted guide points')
  old_width=box('.inspector')['width'];page.locator('[data-splitter=east]').focus();page.keyboard.press('ArrowLeft')
  check(abs(box('.inspector')['width']-old_width-10)<2,'Panel splitters support keyboard resizing')
  page.locator('[data-dock-tab=history]').click();check(state()['interaction']['activityId']==activity and state()['guideHistory']['index']==0,'Bottom dock focus preserves construction without creating history')
  page.locator('#viewport').focus();page.keyboard.press('Escape');tab('home');page.locator('[data-tool=circle]').click();page.mouse.click(**screen([0,0,1]));page.mouse.move(**screen([.64,0,1]));page.mouse.click(**screen([.64,0,1]))
  page.locator('[data-tool=select]').click();page.mouse.click(**screen([0,.64,1]));check(page.locator('#circleProperties').is_visible(),'Inspector exposes contextual Circle properties')
  prior=state()['guideHistory']['index'];page.locator('#circleRadius').fill('0.68');page.locator('#circleRadius').press('Tab')
  check(state()['guideDocument'][0]['radius']==.68 and state()['guideHistory']['index']==prior+1,'Numeric Circle radius uses one validated history command')
  page.locator('#undoButton').click();check(abs(state()['guideDocument'][0]['radius']-.64)<.002,'Ribbon Undo restores the exact Circle radius')
  page.locator('[data-dock-tab=history]').click();check(page.locator('#historyList li').count()>=2,'History dock displays actual commands and the redo tail')
  page.locator('[data-dock-tab=log]').click();check(page.locator('#logList li').count()>0,'Log dock displays actual application operations')
  tab('view');page.locator('#toggle-dock').click();check(page.locator('#toggle-dock').get_attribute('aria-pressed')=='false','Bottom dock can be collapsed')
  page.locator('#toggle-dock').click();saved_nav=box('.navigator')['width'];saved_east=box('.inspector')['width'];authored=state()['guideDocument'];page.reload(wait_until='networkidle');page.wait_for_function('window.retopoDemo?.getState().guideDocument.length===1')
  check(abs(box('.navigator')['width']-saved_nav)<2 and abs(box('.inspector')['width']-saved_east)<2 and state()['guideDocument']==authored,'Panel preferences and authored guides restore independently after reload')
  check(not state()['interaction']['selection']['entityIds'],'Selection remains transient after reload while authored guides persist')
  page.locator('.guide-name').first.click()
  page.locator('[data-dock-tab=measurements]').click();page.screenshot(path=str(OUT/'circle-light.png'))
  page.locator('#themeButton').click();check(page.locator('html').get_attribute('data-theme')=='dark','Existing dark-theme option remains functional');page.screenshot(path=str(OUT/'dark-desktop.png'));page.locator('#themeButton').click()
  page.set_viewport_size({'width':900,'height':800});check(box('#viewport')['width']>250 and box('#viewport')['height']>250,'Three-panel workspace remains usable at 900 px width');page.screenshot(path=str(OUT/'light-narrow.png'))
  page.set_viewport_size({'width':650,'height':780});page.wait_for_function('document.querySelector("#appShell").classList.contains("compact") && document.querySelector("#viewport").clientWidth>550');check('compact' in page.locator('#appShell').get_attribute('class') and box('#viewport')['width']>550,'Compact layout prioritizes the canvas and folds side panels')
  tab('view');page.locator('#toggle-inspector').click();check(page.locator('#circleRadius').is_visible(),'Compact layout can reopen contextual properties');page.screenshot(path=str(OUT/'light-compact.png'))
  check(not errors,'No browser JavaScript errors');browser.close()
 (OUT/'result.json').write_text(json.dumps({'passed':True,'checks':checks,'browserErrors':errors,'colors':colors,'sourceHashes':{str(f.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'app.js',ROOT/'index.html',ROOT/'index.css',ROOT/'src/view/WorkspaceShell.js']}},indent=2)+'\n',encoding='utf-8');print(json.dumps({'passed':True,'checks':len(checks)}),flush=True)
except Exception:
 (OUT/'result.json').write_text(json.dumps({'passed':False,'checks':checks,'browserErrors':errors,'error':traceback.format_exc()},indent=2)+'\n',encoding='utf-8');raise
finally:
 server.terminate();server.wait(timeout=20);log.close()
