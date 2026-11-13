"""Verify in the real UI that an accepted part output shows its mesh edges in the assembly view.

Generates island 6 at 200 with the 483afe83 guide through the real page (owned server and
Chromium, no stubs), returns to the assembly and checks that the Display option "Mesh edges"
changes the picture of the accepted output in the Retopology pane. Screenshots are kept.

Usage: python tests/verify_assembly_output_edges.py --out tests/extra-faces/<folder>
"""
from pathlib import Path
import argparse, io, json, sys, threading, time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from verify_registered_features import GUIDE_200, read, write


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--timeout',type=float,default=600.);a=ap.parse_args()
    out=a.out.resolve()
    if not out.is_relative_to(ROOT):ap.error('Evidence must remain in workspace')
    out.mkdir(parents=True,exist_ok=False)
    import server
    import numpy as np
    from PIL import Image
    from playwright.sync_api import sync_playwright
    http=server.LocalHTTPServer(('127.0.0.1',0),server.Handler);server.Handler.log_message=lambda *args:None
    threading.Thread(target=http.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{http.server_port}'
    model=read(ROOT/'assets/models/toilet-skp.json');part=next(p for p in model['initialParts'] if p['id']=='skp-6');packet=read(GUIDE_200)
    result=dict(url=url,passed=False)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            try:
                page=browser.new_context(viewport=dict(width=1700,height=1100),device_scale_factor=1).new_page();errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(url,wait_until='networkidle');page.locator('#meshSelect').select_option('toilet-skp')
                page.wait_for_function('retopoDemo.getPartsState()?.visibleParts.length===11')
                page.locator('[data-part-id="skp-6"] .part-name').click();page.locator('#partsWork').click()
                page.wait_for_function('(part)=>retopoDemo.getPartsState().active===part && !document.getElementById("generateButton").disabled',arg='skp-6')
                source=page.request.get(url+'/api/parts/'+part['partSource']).json()
                upload=dict(coordinateFrame='source',sourceSha256=source['sourceSha256'],curves=packet['curves'])
                page.locator('#guideFile').set_input_files(dict(name='authored-guide.json',mimeType='application/json',buffer=json.dumps(upload).encode()))
                page.wait_for_function('(n)=>retopoDemo.getState().guides.length===n',arg=len(packet['curves']))
                page.locator('#targetNumber').fill('200');page.locator('#targetNumber').press('Tab')
                with page.expect_response(lambda r:r.url.endswith('/api/remesh') and r.request.method=='POST') as admission:page.locator('#generateButton').click()
                result['job']=admission.value.json()['id'];started=time.monotonic()
                while page.evaluate('retopoDemo.getState().busy'):
                    assert time.monotonic()-started<a.timeout,'Generation timed out'
                    page.wait_for_timeout(1000)
                assert page.evaluate('retopoDemo.getState().resultJob')==result['job'],'The job was not accepted'
                page.locator('#partsAssembly').click()
                page.wait_for_function('retopoDemo.getPartsState().active===null && retopoDemo.getPartsState().visibleParts.length===11')
                page.wait_for_function('document.getElementById("resultMeta").textContent.includes("accepted part output")')
                result['resultMeta']=page.locator('#resultMeta').inner_text()
                box=page.locator('#viewport').bounding_box()
                pane=dict(x=box['x']+box['width']/2,y=box['y'],width=box['width']/2,height=box['height'])   # the Retopology pane
                pictures={}
                for name,checked in (('edges-on',True),('edges-off',False),('edges-on-again',True)):
                    page.locator('#wireToggle').set_checked(checked);page.wait_for_timeout(400)
                    page.screenshot(path=str(out/f'assembly-{name}.png'))
                    pictures[name]=np.asarray(Image.open(io.BytesIO(page.screenshot(clip=pane))).convert('RGB'),int)
                changed=int((np.abs(pictures['edges-on']-pictures['edges-off']).sum(2)>30).sum())
                restored=int((np.abs(pictures['edges-on']-pictures['edges-on-again']).sum(2)>30).sum())
                result.update(pixelsChangedByMeshEdges=changed,pixelsDifferentAfterTurningBackOn=restored,pageErrors=errors)
                # The 436-quad output has about 900 edges on screen; a few hundred pixels would be noise, thousands are edge lines.
                result['passed']=bool(changed>2000 and restored<changed//20 and not errors)
            finally:browser.close()
    finally:
        http.shutdown();http.server_close();write(out/'result.json',result)
    print(json.dumps(result));return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
