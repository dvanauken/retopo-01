from pathlib import Path
import sys,json,time,socket,subprocess,hashlib,urllib.request,traceback
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'tests/quality-repair'/(sys.argv[1] if len(sys.argv)>1 else 'browser-'+str(time.time_ns()));OUT.mkdir(exist_ok=False)
HASHES={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['worker.py','structured_prism.py','quad_quality.py','app.js','index.html','assets/previews/hexagon.json']};checks=[];errors=[]
def check(value,name):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
def write(name,value):(OUT/name).write_text(json.dumps(value,indent=2)+'\n')
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
URL=f'http://127.0.0.1:{port}';log=(OUT/'server.log').open('w',encoding='utf-8');server=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'server.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
 for _ in range(100):
  try:
   with urllib.request.urlopen(URL+'/api/health',timeout=1):break
  except Exception:time.sleep(.1)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1920,'height':1040},accept_downloads=True);page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(URL,wait_until='networkidle');page.wait_for_function('window.retopoDemo?.getState().resultFaces===624');check(page.locator('#topologyMetric').inner_text()=='Good','Rebuilt startup example has actual quad-quality qualification')
  check('Continuous quad grid' in page.locator('#resultSummary').inner_text(),'UI identifies the actual structured backend')
  original=ROOT/'tests/quality-repair/original/user-failed-run/curves.json';curves=json.loads(original.read_text())['curves'];page.locator('#guideFile').set_input_files(original);page.wait_for_function('window.retopoDemo.getState().guides[0]?.length===452');page.locator('#targetNumber').fill('450');page.locator('#targetNumber').press('Tab');page.locator('#topButton').click();check(page.evaluate('window.retopoDemo.getState().guides')==curves,'UI imports the exact 452-point user-rejected stroke')
  before={x.name for x in (ROOT/'runs').iterdir() if x.is_dir()};page.locator('#generateButton').click();page.wait_for_function('!window.retopoDemo.getState().busy',timeout=180000);created=[x for x in (ROOT/'runs').iterdir() if x.is_dir() and x.name not in before];check(len(created)==1,'Generate creates one actual new reconstruction job');job=created[0];mesh=json.loads((job/'mesh.json').read_text());check(mesh['quality']['passed'] and mesh['backend']=='engineering-structured-prismatic-annulus','Browser receives a quality-checked continuous quad grid')
  check(page.evaluate('window.retopoDemo.getState().resultFaces')==480 and page.locator('#topologyMetric').inner_text()=='Good','The actual 480-quad result is rendered and reported')
  check('52' in page.locator('#topologyDetail').inner_text(),'UI shows actual minimum angle rather than topology-only Passed')
  page.screenshot(path=str(OUT/'user-result-top-dark.png'),full_page=True)
  page.locator('#detailsButton').click();check('Minimum quad angle' in page.locator('#detailsContent').inner_text() and 'Scaled' not in page.locator('#detailsContent').inner_text() or 'scaled Jacobian' in page.locator('#detailsContent').inner_text(),'Details expose element-quality measurements');page.locator('#detailsDialog [data-close-dialog]').click()
  with page.expect_download() as dl:page.locator('#exportMesh').click()
  file=OUT/'actual-browser-output.obj';dl.value.save_as(file);check(hashlib.sha256(file.read_bytes()).hexdigest()==hashlib.sha256((job/'output.obj').read_bytes()).hexdigest(),'Browser export is the actual rebuilt mesh')
  page.locator('#fitButton').click();page.screenshot(path=str(OUT/'user-result-perspective-dark.png'),full_page=True)
  page.locator('#themeButton').click();page.wait_for_timeout(200);page.locator('#topButton').click();page.screenshot(path=str(OUT/'user-result-top-light.png'),full_page=True);check(page.locator('html').get_attribute('data-theme')=='light','Result remains visible in light theme')
  # Drawing remains an actual input gesture after the algorithm/UI repair.
  page.locator('[data-tool=draw]').click();screen=page.evaluate('[[.6,-.2,1],[.61,-.05,1],[.6,.1,1]].map(p=>window.retopoDemo.projectPoint(p))');page.mouse.move(screen[0]['x'],screen[0]['y']);page.mouse.down()
  for q in screen[1:]:page.mouse.move(q['x'],q['y'],steps=8)
  page.mouse.up();check(len(page.evaluate('window.retopoDemo.getState().guides'))>1,'Real mouse drawing still creates surface guide samples')
  check(page.locator('#resultBadge').inner_text()=='Needs update','A new stroke marks the previous result stale')
  page.locator('#meshSelect').select_option('cylinder');page.wait_for_function('window.retopoDemo.getState().meshId==="cylinder" && window.retopoDemo.getState().resultFaces===512');check(page.locator('#resultBadge').inner_text()=='Quality warning' and page.locator('#topologyMetric').inner_text()=='Needs work','An old count-mismatched example is not misrepresented as quality-passing')
  check(not errors,'No browser JavaScript errors');check(all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value for name,value in HASHES.items()),'Code and preview cohort stayed unchanged during verification');browser.close()
 write('result.json',{'passed':True,'checks':checks,'browserErrors':errors,'sourceHashes':HASHES,'job':job.name,'scope':'Actual UI import of unchanged user curve, live local worker generation, rendered quad-quality display and real export; both themes; actual new pointer stroke; honest warning on old unqualified example.'});print(json.dumps({'passed':True,'checks':len(checks),'job':job.name,'output':str(OUT)}),flush=True)
except Exception:
 write('result.json',{'passed':False,'checks':checks,'browserErrors':errors,'error':traceback.format_exc()});raise
finally:server.terminate();server.wait(timeout=20);log.close()
