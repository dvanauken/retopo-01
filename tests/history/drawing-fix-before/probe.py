from pathlib import Path
import json, math
from playwright.sync_api import sync_playwright
OUT=Path(__file__).parent/'retopo-drawing-fix';OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 page=browser.new_page(viewport={'width':1540,'height':1020})
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8742',wait_until='networkidle')
 page.wait_for_function('window.retopoDemo?.getState().resultFaces===736')
 points=[[.64*math.cos(a),.64*math.sin(a),1] for a in [-1.8+i*.9/25 for i in range(26)]]
 screen=page.evaluate('(points)=>points.map(window.retopoDemo.projectPoint)',points)
 states=[]
 for label,offset in [('default-left',0),('default-right',page.locator('#viewport').bounding_box()['width']/2)]:
  page.mouse.move(screen[0]['x']+offset,screen[0]['y']);page.mouse.down()
  for pt in screen[1:]:page.mouse.move(pt['x']+offset,pt['y'])
  page.mouse.up();states.append({'case':label,'state':page.evaluate('window.retopoDemo.getState()')})
 page.screenshot(path=str(OUT/'before.png'))
 (OUT/'before.json').write_text(json.dumps({'states':states,'errors':errors},indent=2))
 print(json.dumps({'guideCounts':[(s['case'],len(s['state']['guides'])) for s in states],'errors':errors}))
 browser.close()
