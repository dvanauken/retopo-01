"""Lose a genuine job-admission response without revealing its ID to the app.

The test observer can inspect the real response for cleanup and assertions;
Chromium receives only a connection reset. No worker state is fabricated.
"""
import argparse,asyncio,hashlib,json,os,socket,subprocess,sys,time,traceback,urllib.request
from pathlib import Path
import psutil
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
if not args.label.replace('-','').isalnum():raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-submission-transport'/args.label;OUT.mkdir(parents=True,exist_ok=True)
checks,errors,jobs,records=[],[],[],[]
hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('app.js','server.py','tests/verify_toilet_submission_transport.py')}
def check(value,name,**details):
    checks.append(dict(passed=bool(value),name=name,**details));print(('PASS ' if value else 'FAIL ')+name,flush=True)
def http(path,body=None):
    request=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(request,timeout=15))
def alive(observed):
    result=[]
    for record in observed:
        try:
            p=psutil.Process(record['pid'])
            if p.is_running() and p.create_time()==record['created']:result.append(p.pid)
        except psutil.NoSuchProcess:pass
    return result
async def run():
    async with async_playwright() as playwright:
        browser=await playwright.chromium.launch(headless=True)
        context=await browser.new_context(viewport={'width':1700,'height':1050})
        page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        lost=asyncio.Event();captured={};observed=[]
        async def discard_reply(route):
            captured['request']=route.request.post_data_json
            response=await route.fetch();captured['acknowledgement']=await response.json()
            jobs.append(captured['acknowledgement']['id'])
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                descendants=psutil.Process(server.pid).children(recursive=True)
                workers=[p for p in descendants if 'worker.py' in ' '.join(p.cmdline())]
                if workers:
                    owned={p.pid:p for worker in workers for p in [worker,*worker.children(recursive=True)]}
                    observed.extend(dict(pid=p.pid,created=p.create_time(),name=p.name(),parentPid=p.ppid(),command=p.cmdline()) for p in owned.values())
                    break
                await asyncio.sleep(.05)
            await route.abort('connectionreset');lost.set()
        try:
            await page.goto(url,wait_until='networkidle');await page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
            await page.locator('#meshSelect').select_option('toilet');await page.wait_for_function('window.retopoDemo.getState().meshId==="toilet"')
            before=await page.evaluate('window.retopoDemo.getState()')
            await page.evaluate('localStorage.setItem("retopo-1:submission-probe","preserve")')
            await page.route('**/api/remesh',discard_reply)
            await page.locator('#generateButton').click();await asyncio.wait_for(lost.wait(),timeout=40)
            check(bool(observed),'A real toilet worker exists before the admission response is lost',processes=observed)
            await page.wait_for_function('!window.retopoDemo.getState().busy',timeout=15000)
            after=await page.evaluate('window.retopoDemo.getState()')
            check(after['lastAttempt']['phase']=='failed','Lost admission response is reported as an unsuccessful attempt')
            check(after['guides']==before['guides'] and after['meshId']=='toilet','Lost admission response preserves authored toilet guides')
            deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                actual=await asyncio.to_thread(http,'/api/jobs/'+jobs[0])
                if actual['state']=='cancelled':break
                await asyncio.sleep(.05)
            check(actual['state']=='cancelled','An admitted job is stopped even though its generated ID never reached the browser',observed=actual['state'])
            deadline=time.monotonic()+5
            while actual['state']=='cancelled' and alive(observed) and time.monotonic()<deadline:await asyncio.sleep(.05)
            check(not alive(observed),'Lost acknowledgement leaves no observed worker or child alive',survivors=alive(observed))
            await page.screenshot(path=str(OUT/'lost-acknowledgement.png'))
            await page.locator('#resetButton').click();await page.locator('#confirmReset').click()
            await page.wait_for_function('window.retopoDemo?.getState().meshId==="hexagon"',timeout=15000)
            actual=await asyncio.to_thread(http,'/api/jobs/'+jobs[0])
            check(actual['state']=='cancelled' and not alive(observed),'Reset cannot discard an unacknowledged running calculation',observed=actual['state'],survivors=alive(observed))
            check(actual['state']=='cancelled' and await page.evaluate('localStorage.getItem("retopo-1:submission-probe")') is None,'Reset clears the saved workspace after ownership is resolved')
            records.append(dict(captured=captured,observedProcesses=observed,interruptedUI=after,finalJob=actual))
        finally:
            for job in jobs:await asyncio.to_thread(http,'/api/jobs/'+job+'/cancel',{})
            await context.close();await browser.close()
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}'
log=(OUT/'server.log').open('w',encoding='utf-8')
server=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'server.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=log,
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
try:
    deadline=time.monotonic()+30
    while True:
        try:http('/api/health');break
        except OSError:
            if server.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Server did not start')
            time.sleep(.1)
    asyncio.run(run())
except Exception:
    errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:
    for job in jobs:
        try:http('/api/jobs/'+job+'/cancel',{})
        except Exception as e:errors.append('Cleanup: '+str(e))
    for child in psutil.Process(server.pid).children(recursive=True):
        try:child.kill()
        except psutil.NoSuchProcess:pass
    server.terminate();server.wait(timeout=20);log.close()
    report=dict(passed=not errors and all(c['passed'] for c in checks),checks=checks,errors=errors,cases=records,sourceHashes=hashes,
        implementationUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),
        scope='Genuine HTTP admission and actual toilet worker, followed by loss of the initial response before the browser receives any server-generated job ID. Observer-only response retained for assertions and cleanup; no simulated solve.')
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(passed=report['passed'],checks=len(checks),failures=[c['name'] for c in checks if not c['passed']])),flush=True)
raise SystemExit(0 if report['passed'] else 1)
