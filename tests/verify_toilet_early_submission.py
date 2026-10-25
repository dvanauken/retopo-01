"""Cancel/Reset before request delivery; replay exact captured bytes over real HTTP."""
import argparse,asyncio,hashlib,json,os,socket,subprocess,sys,time,traceback,urllib.request,uuid
from pathlib import Path
import psutil
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
if not args.label.replace('-','').isalnum():raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-early-submission'/args.label;OUT.mkdir(parents=True,exist_ok=True)
checks,errors,records=[],[],[]
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('app.js','server.py','tests/verify_toilet_early_submission.py')}
def check(value,name,**details):
    checks.append(dict(passed=bool(value),name=name,**details));print(('PASS ' if value else 'FAIL ')+name,flush=True)
def http(path,body=None):
    req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=15))
async def exercise(browser,reset):
    label='Reset' if reset else 'Cancel';context=await browser.new_context(viewport={'width':1700,'height':1050})
    page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    pending,release=asyncio.Event(),asyncio.Event();captured={};genuine_response=None
    async def hold_before_delivery(route):
        captured['body']=route.request.post_data_json;pending.set();await release.wait()
        try:
            if genuine_response is not None:await route.fulfill(response=genuine_response)
            else:await route.abort()
        except Exception:
            if not reset:raise
    try:
        await page.goto(url,wait_until='networkidle');await page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
        await page.locator('#meshSelect').select_option('toilet');await page.wait_for_function('window.retopoDemo.getState().meshId==="toilet"')
        guides=(await page.evaluate('window.retopoDemo.getState()'))['guides']
        await page.evaluate('localStorage.setItem("retopo-1:early-probe","preserve")')
        await page.route('**/api/remesh',hold_before_delivery)
        await page.locator('#generateButton').click();await asyncio.wait_for(pending.wait(),timeout=10)
        check(len(captured['body'].get('requestId',''))==32,label+': browser owns a request identity before sending any bytes to the service')
        if reset:
            await page.locator('#resetButton').click();await page.locator('#confirmReset').click()
            await page.wait_for_function('window.retopoDemo?.getState().meshId==="hexagon"',timeout=10000)
            check(await page.evaluate('localStorage.getItem("retopo-1:early-probe")') is None,'Reset finishes after early cancellation without waiting for an undelivered acknowledgement')
        else:
            await page.locator('#cancelButton').click()
            await page.wait_for_function('window.retopoDemo.getState().lastAttempt?.phase==="cancelled"',timeout=10000)
            check((await page.evaluate('window.retopoDemo.getState()'))['guides']==guides,'Early Cancel keeps the authored toilet guides')
        # Deliver the captured POST after the user action. This is genuine HTTP
        # and its genuine response is used for the held browser request, if live.
        genuine_response=await context.request.post(url+'/api/remesh',headers={'Content-Type':'application/json'},data=json.dumps(captured['body']))
        data=await genuine_response.json()
        check(genuine_response.status==202 and data['state']=='cancelled' and data['id'] is None,label+': delayed delivery cannot admit a cancelled request',response=data)
        second=await context.request.post(url+'/api/remesh',headers={'Content-Type':'application/json'},data=json.dumps(captured['body']))
        again=await second.json()
        check(second.status==202 and again==data,label+': repeated delayed delivery remains cancelled without allocating a job')
        changed=dict(captured['body'],target=600)
        conflict=await context.request.post(url+'/api/remesh',headers={'Content-Type':'application/json'},data=json.dumps(changed))
        check(conflict.status==409,label+': reusing the identity with changed parameters is rejected')
        release.set();await page.wait_for_timeout(200)
        workers=[p.pid for p in psutil.Process(server.pid).children(recursive=True) if 'worker.py' in ' '.join(p.cmdline())]
        check(not workers,label+': no toilet worker starts after the confirmed early cancellation',workers=workers)
        after=await page.evaluate('window.retopoDemo.getState()')
        check(not after['busy'] and after['meshId']==('hexagon' if reset else 'toilet'),label+': late response cannot revive the obsolete attempt')
        records.append(dict(scenario=label,body=captured['body'],lateResponse=data))
        await page.screenshot(path=str(OUT/(label.lower()+'.png')))
    finally:release.set();await context.close()
async def run():
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        try:
            await exercise(browser,False);await exercise(browser,True)
        finally:await browser.close()
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}';log=(OUT/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'server.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=log,
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
    deadline=time.monotonic()+30
    while True:
        try:http('/api/health');break
        except OSError:
            if server.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Server failed to start')
            time.sleep(.1)
    asyncio.run(run())
except Exception:
    errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:
    for child in psutil.Process(server.pid).children(recursive=True):
        try:child.kill()
        except psutil.NoSuchProcess:pass
    server.terminate();server.wait(timeout=10);log.close()
    report=dict(passed=not errors and all(c['passed'] for c in checks),checks=checks,errors=errors,cases=records,sourceHashes=hashes,
        implementationUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),
        scope='Real browser Cancel/Reset before remesh delivery. Exact captured body is later sent over genuine HTTP; genuine response only. Verifies no job allocation or worker creation for cancelled request identities.')
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=report['passed'],checks=len(checks))),flush=True)
raise SystemExit(0 if report['passed'] else 1)
