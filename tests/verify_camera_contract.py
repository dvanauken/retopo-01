"""Camera UI invariants plus depth-clipped/raster-visible selection fixtures."""
from pathlib import Path
from http.server import ThreadingHTTPServer
import json, sys, threading
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import server
server.Handler.log_message=lambda *args:None
http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
out=ROOT/'runs/draw3d-review';errors=[];checks=[]
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport=dict(width=1700,height=1100),device_scale_factor=2)
  page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(f'http://127.0.0.1:{http.server_port}',wait_until='networkidle')
  page.locator('#meshSelect').select_option('toilet-skp');page.wait_for_function('retopoDemo.getPartsState()?.visibleParts.length===11')
  page.locator('[data-part-id="skp-2"] .part-name').click()
  camera=lambda:page.evaluate('retopoDemo.getCameraState()')
  selection=page.evaluate('retopoDemo.getState().interaction.selection'); history=page.evaluate('retopoDemo.getState().guideHistory')
  previous=camera();page.locator('#projectionSelect').select_option('orthographic');current=camera()
  assert current['projection']=='orthographic' and current['target']==previous['target']
  assert abs(current['verticalSpan']-previous['verticalSpan'])<1e-9
  r=page.locator('#viewport').bounding_box();x=r['x']+r['width']*.3;y=r['y']+r['height']*.4
  before=camera();page.mouse.move(x,y);page.mouse.down(button='right');page.mouse.move(x+50,y+30,steps=5);page.mouse.up(button='right');after=camera()
  assert abs(before['distance']-after['distance'])<1e-9 and before['target']!=after['target']
  anchor=page.evaluate('retopoDemo.getCameraState().target');screen=page.evaluate('(p)=>retopoDemo.projectPoint(p)',anchor)
  page.mouse.move(screen['x'],screen['y']);page.mouse.wheel(0,-150);page.wait_for_timeout(100)
  projected=page.evaluate('(p)=>retopoDemo.projectPoint(p)',anchor)
  assert abs(projected['x']-screen['x'])<.5 and abs(projected['y']-screen['y'])<.5
  before=camera();page.locator('#projectionSelect').select_option('perspective');after=camera()
  assert after['target']==before['target'] and abs(before['verticalSpan']-after['verticalSpan'])<1e-9
  checks.append('Projection changes preserve target-plane scale; orthographic pan and anchored zoom preserve camera invariants at DPR 2')
  for name,expected in [('front',[0,-1,0]),('top',[0,0,1]),('right',[1,0,0]),('isometric',[1,-1,1])]:
   before=camera();page.locator('#'+name+'Button').click();after=camera()
   assert after['target']==before['target'] and abs(after['distance']-before['distance'])<1e-8
   direction=[(p-t)/after['distance'] for p,t in zip(after['position'],after['target'])];norm=sum(v*v for v in expected)**.5
   assert max(abs(a-b/norm) for a,b in zip(direction,expected))<.00001,(name,direction)
  assert camera()['projection']=='orthographic'
  page.keyboard.press('f');assert camera()['near']>0 and camera()['far']>camera()['near']
  assert page.evaluate('retopoDemo.getState().interaction.selection')==selection
  assert page.evaluate('retopoDemo.getState().guideHistory')==history
  checks.append('Front/top/right/isometric retain target; Fit preserves selection and navigation never edits history')
  fixture=page.evaluate('''async () => {
    const THREE=await import('three'), {partMarquee,clipDepth}=await import('/src/view/PartMarquee.js');
    const renderer=new THREE.WebGLRenderer();renderer.setPixelRatio(2);renderer.setSize(200,200);
    const camera=new THREE.PerspectiveCamera(90,1,1,10);camera.position.set(0,0,0);camera.lookAt(0,0,-1);camera.updateMatrixWorld();
    const material=new THREE.MeshBasicMaterial({side:THREE.DoubleSide});
    const plane=(z,size=1)=>{const m=new THREE.Mesh(new THREE.PlaneGeometry(size,size),material);m.position.z=z;return m;};
    const front=plane(-2),back=plane(-3),tiny=plane(-3,.03);tiny.position.x=.9;
    const objects=[{id:'front',mesh:front},{id:'back',mesh:back},{id:'tiny',mesh:tiny}],pane={left:0,top:0,width:200,height:200};
    const visible=partMarquee(renderer,camera,pane,objects,[0,0],[200,200]);
    const missed=partMarquee(renderer,camera,pane,objects,[90,90],[110,110]);
    const clipped=clipDepth([[-.2,-.2,-2,1],[.2,-.2,0,1],[0,.2,0,1]]);
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute([-.2,-.2,-.5,.2,-.2,-2,0,.2,-2],3));
    const crossing=partMarquee(renderer,camera,pane,[{id:'crossing',mesh:new THREE.Mesh(geometry,material)}],[0,0],[200,200]);
    const before=renderer.getViewport(new THREE.Vector4()).toArray();
    const reverse=partMarquee(renderer,camera,pane,objects,[200,200],[0,0]);
    const after=renderer.getViewport(new THREE.Vector4()).toArray();
    renderer.dispose();return {visible,missed,clipped,crossing,reverse,before,after};
  }''')
  assert fixture['visible']==['front','tiny'],fixture
  assert fixture['reverse']==fixture['visible'] and fixture['missed']==[] and fixture['crossing']==['crossing']
  assert fixture['before']==fixture['after'] and all(p[2]>=-p[3] for p in fixture['clipped'])
  checks.append('Marquee clips near-plane crossings, rejects partial footprint/occluded parts, selects tiny visible surfaces, works both directions, and restores renderer state at DPR 2')
  assert not errors,errors
  page.screenshot(path=str(out/'orthographic.png'));(out/'camera-result.json').write_text(json.dumps(dict(passed=True,checks=checks,errors=errors),indent=2));print(json.dumps(checks,indent=2))
  browser.close()
finally:http.shutdown();http.server_close()
