"""Real browser polling across an actual Windows service crash and restart."""
import argparse,asyncio,hashlib,json,os,socket,subprocess,sys,time,traceback,urllib.request
from pathlib import Path
import psutil
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--label',required=True);args=parser.parse_args()
if not args.label.replace('-','').isalnum():raise ValueError('Use a plain label')
OUT=ROOT/'tests/toilet-restart-ui'/args.label;OUT.mkdir(parents=True,exist_ok=True)
checks,errors,records,servers=[],[],[],[]
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('app.js','server.py','process_ownership.py','tests/verify_toilet_restart_ui.py')}
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
url=f'http://127.0.0.1:{port}';log=(OUT/'server.log').open('w',encoding='utf-8')
def check(value,name,**detail):
    checks.append(dict(passed=bool(value),name=name,**detail));print(('PASS ' if value else 'FAIL ')+name,flush=True)
def http(path,body=None):
    req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req,timeout=15))
def launch():
    p=subprocess.Popen([sys.executable,'-X','utf8',str(ROOT/'server.py'),'--port',str(port)],cwd=ROOT,stdout=log,stderr=log,
        env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1'),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));servers.append(p)
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        try:http('/api/health');return p
        except OSError:
            if p.poll() is not None:raise RuntimeError('Server failed during startup')
            time.sleep(.05)
    raise RuntimeError('Server did not start')
async def run(server):
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True);context=await browser.new_context(viewport={'width':1700,'height':1050})
        page=await context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        held,release=asyncio.Event(),asyncio.Event();captured={}
        async def delay_poll(route):
            captured['statusUrl']=route.request.url;held.set();await release.wait()
            response=await context.request.get(route.request.url)
            captured['statusAfterRestart']=response.status
            await route.fulfill(response=response)
        try:
            await page.goto(url,wait_until='networkidle');await page.wait_for_function('window.retopoDemo?.getState().resultFaces>0')
            await page.locator('#meshSelect').select_option('toilet');await page.wait_for_function('window.retopoDemo.getState().meshId==="toilet"')
            before=await page.evaluate('window.retopoDemo.getState()')
            await page.route('**/api/jobs/*',delay_poll)
            await page.locator('#generateButton').click();await asyncio.wait_for(held.wait(),timeout=15)
            job=captured['statusUrl'].split('/')[-1]
            deadline=time.monotonic()+30;observed=[]
            while time.monotonic()<deadline:
                descendants=psutil.Process(server.pid).children(recursive=True)
                workers=[w for w in descendants if 'worker.py' in ' '.join(w.cmdline())]
                if workers:
                    observed=[dict(pid=w.pid,created=w.create_time()) for w in workers];break
                await asyncio.sleep(.05)
            check(bool(observed),'Browser crash test starts with a real admitted toilet worker')
            server.kill();await asyncio.to_thread(server.wait,10)
            replacement=await asyncio.to_thread(launch)
            check(replacement.pid!=server.pid,'A new server process replaces the dead service on the same port')
            release.set();await page.wait_for_function('!window.retopoDemo.getState().busy',timeout=15000)
            state=await page.evaluate('window.retopoDemo.getState()')
            check(captured['statusAfterRestart']==404 and state['lastAttempt']['phase']=='failed','A genuine missing old-job response becomes a failed attempt')
            check(state['guides']==before['guides'] and state['target']==before['target'] and state['meshId']=='toilet','Service restart preserves authored guides and requested density')
            check(state['resultJob'] is None and not state['resultFaces'],'Restart cannot publish a result from the interrupted worker')
            check(await page.locator('#processing').is_hidden() and not await page.locator('#generateButton').is_disabled(),'New service resolves the old request identity and leaves Generate usable')
            await page.unroute('**/api/jobs/*',delay_poll)
            await page.screenshot(path=str(OUT/'after-restart.png'))
            async with page.expect_response('**/api/remesh') as event:await page.locator('#generateButton').click()
            response=await event.value;fresh=await response.json()
            check(response.status==202 and fresh['id']!=job,'A browser retry is admitted as a fresh request after restart')
            await page.locator('#cancelButton').click();await page.wait_for_function('window.retopoDemo.getState().lastAttempt?.phase==="cancelled"')
            actual=await asyncio.to_thread(http,'/api/jobs/'+fresh['id'])
            check(actual['state']=='cancelled','The fresh browser request still cancels normally')
            records.append(dict(oldJob=job,freshJob=fresh['id'],oldServer=server.pid,newServer=replacement.pid,observedWorkers=observed,stateAfterRestart=state))
        finally:release.set();await context.close();await browser.close()
try:
    server=launch();asyncio.run(run(server))
except Exception:
    errors.append(traceback.format_exc());print(errors[-1],flush=True)
finally:
    for p in servers:
        if p.poll() is None:p.kill();p.wait(timeout=10)
    log.close()
    report=dict(passed=not errors and all(c['passed'] for c in checks),checks=checks,errors=errors,cases=records,sourceHashes=hashes,
        implementationUnchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in hashes.items()),
        scope='Actual browser and actual isolated server replacement on the same port while a toilet job is owned. One polling request is delayed before forwarding; the replacement server supplies its genuine 404. No fabricated job status or mesh.')
    (OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=report['passed'],checks=len(checks))),flush=True)
raise SystemExit(0 if report['passed'] else 1)
