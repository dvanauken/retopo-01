"""Recover the user's real rejected run through the API and visible Log panel."""
from pathlib import Path
from http.server import ThreadingHTTPServer
import json, sys, threading
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import server
server.Handler.log_message=lambda *args:None
http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=http.serve_forever,daemon=True).start()
out=ROOT/'runs/job-activity-review';out.mkdir(exist_ok=True);errors=[]
job_id='18a9e33afe0644c6867ffbc0153c1dad';part_id='617dd8f640bfa84d6af2fb6e4b080ec1bc73328db4941a49a1375d18b7817db1'
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport=dict(width=1670,height=1050));page.on('pageerror',lambda e:errors.append(str(e)))
  url=f'http://127.0.0.1:{http.server_port}';page.goto(url,wait_until='networkidle')
  status=page.request.get(url+f'/api/jobs/{job_id}').json()
  assert status['state']=='failed' and status['diagnostics']['candidateCount']==15
  assert 'failed source crease preservation' in status['error']
  assert status['events'] and all(e['time'] is None for e in status['events'])
  cursor=status['eventCursor'];assert page.request.get(url+f'/api/jobs/{job_id}?after={cursor}').json()['events']==[]
  assert page.request.get(url+f'/api/jobs/{job_id}/mesh.json').status==409
  latest=page.request.get(url+f'/api/parts/{part_id}/latest-job');assert latest.status==200
  part=page.request.get(url+f'/api/parts/{part_id}').json()
  page.locator('#meshSelect').select_option('toilet-skp');page.wait_for_function('retopoDemo.getPartsState()?.visibleParts.length===11')
  page.evaluate('''({jobId,source})=>localStorage.setItem('retopo-1:last-attempt:toilet-skp--part-skp-6',JSON.stringify({phase:'failed',message:'Old generic rejection',jobId,target:7200,guideCount:0,sourceSha256:source}))''',dict(jobId=job_id,source=part['sourceSha256']))
  page.locator('[data-part-id="skp-6"] .part-name').click();page.locator('#partsWork').click()
  page.wait_for_function('retopoDemo.getState().lastAttempt?.message.includes("source crease preservation")')
  page.locator('[data-dock-tab="log"]').click()
  log=page.locator('#logList').inner_text();assert 'Recovered diagnostics' in log and 'edgeP95' in log and '0.0022622' in log
  assert len(page.locator(f'#logList [data-job-id="{job_id}"]').all())>=15
  with page.expect_download() as download:page.locator('#save-log').click()
  download.value.save_as(str(out/'recovered-activity.txt'))
  assert 'source crease preservation' in (out/'recovered-activity.txt').read_text(encoding='utf-8')
  page.screenshot(path=str(out/'recovered-failure.png'));assert not errors,errors
  report=dict(passed=True,job=job_id,diagnostics=status['diagnostics'],checks=['real saved failure available after server restart','15 candidates with specific failing checks','old individual event timestamps explicitly unavailable','incremental cursor suppresses duplicates','failed mesh remains unpublished','latest part attempt can be found','browser restores diagnostic log and failure summary','measurement values and downloadable activity log','no browser errors'],errors=errors)
  (out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True);browser.close()
finally:http.shutdown();http.server_close()
