"""Local canvas demo server; each solve runs in its own owned Python worker."""
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import argparse,datetime,errno,functools,hashlib,json,math,mimetypes,os,re,socket,subprocess,sys,threading,time,uuid
from urllib.request import ProxyHandler,build_opener
from urllib.parse import parse_qs, urlsplit
import psutil
from process_ownership import protect_service_tree
from job_progress import read_events
from job_diagnostics import from_job as job_diagnostics, recovered_events
from crease_angle import check as check_crease_angle, DEFAULT as DEFAULT_CREASE_ANGLE

ROOT=Path(__file__).resolve().parent
CATALOG=json.loads((ROOT/'assets/catalog.json').read_text(encoding='utf-8'))
MESHES={m['id']:m for m in CATALOG};JOBS={};REQUESTS={};LOCK=threading.Lock();QUEUE=ThreadPoolExecutor(max_workers=1)

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,data):p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def snapshot(job):return {k:v for k,v in job.items() if k not in ('process','directory')}

@functools.lru_cache(maxsize=8)
def source_geometry(part_id,mesh_id,stamp):
 # Prepared parts are content-addressed; catalog sources are keyed by file time.
 import numpy as np
 if part_id:
  from mesh_parts import load_part
  model=load_part(part_id)[0]
 else:model=read(ROOT/'assets/models'/(mesh_id+'.json'))
 return np.asarray(model['vertices'],float),np.asarray(model['faces'],int)

def source_creases(part_id,mesh_id,angle,target):
 """The auto guides a solve would use: the same detect() and spacing rule as the worker."""
 engine=str(ROOT/'engine/targets/zbrush/clone')
 if engine not in sys.path:sys.path.insert(0,engine)
 from source_features import detect,spacing
 stamp=None if part_id else (ROOT/'assets/models'/(mesh_id+'.json')).stat().st_mtime_ns
 vertices,faces=source_geometry(part_id,mesh_id,stamp)
 h=spacing(vertices,faces,target);edges,detection=detect(vertices,faces,h,angle,target=target)
 return dict(detection,target=target,spacing=h,edges=edges.tolist())

def persisted_job(job_id):
 if not re.fullmatch('[a-f0-9]{32}',job_id):return None
 folder=ROOT/'runs'/job_id
 try:
  data=read(folder/'execution.json')
  if data.get('id')!=job_id or data.get('state') not in ('complete','failed','cancelled'):return None
  return {**{k:v for k,v in data.items() if k!='command'},'directory':folder}
 except (OSError,ValueError):return None

def job_status(job,cursor=0):
 data=snapshot(job);folder=job['directory']
 if data['state']=='running':
  try:data['stage']=read(folder/'progress.json')['stage']
  except (OSError,KeyError,ValueError):pass
 data.update(read_events(folder,cursor) if (folder/'events.jsonl').exists() else recovered_events(folder,cursor))
 try:
  settings=read(folder/'settings.json');data.update(sourceSha256=settings.get('sourceSha256'),partSource=settings.get('partSource'))
 except (OSError,ValueError):pass
 if data['state']=='failed':
  try:report=read(folder/'report.json')
  except (OSError,ValueError):report={}
  detail=report.get('diagnostics') or job_diagnostics(folder)
  if detail:
   data['diagnostics']=detail;data['error']=detail['message']
 if data.get('startedAt'):data['elapsedSeconds']=round((data.get('finishedAt') or time.time())-data['startedAt'],1)
 return data
def diagnostic(path,data):
 # Diagnostic files are advisory. A sharing violation must not stop cleanup.
 try:write(path,data)
 except OSError as error:print(f'Could not write {path.name}: {error}',file=sys.stderr,flush=True)

def terminate_worker(process):
 if process.poll() is not None:return
 try:
  parent=psutil.Process(process.pid);children=parent.children(recursive=True)
  process.kill()
  for child in reversed(children):
   try:child.kill()
   except psutil.NoSuchProcess:pass
 except psutil.NoSuchProcess:pass
def cancel_job(job):
 # Caller holds LOCK, shared with admission and worker state changes.
 if job['state'] in ('queued','running'):
  previous=job['state']
  # Stop the process before confirming cancellation, regardless of log access.
  # If termination itself fails, retain the active state so cancellation retries.
  if job.get('process') and job['process'].poll() is None:terminate_worker(job['process'])
  job.update(state='cancelled',stage='Cancelled',finishedAt=time.time())
  from job_progress import emit
  emit(job['directory'],'Calculation cancelled; previous accepted output and source are retained.',kind='cancelled')
  diagnostic(job['directory']/'cancel-request.json',snapshot(job))
  if previous=='queued':diagnostic(job['directory']/'execution.json',dict(snapshot(job),actualExitCode=None,processStarted=False))
 return snapshot(job)

def cancelled_request(request_id):
 return dict(id=None,requestId=request_id,state='cancelled',stage='Cancelled before admission')

def execute(job):
 with LOCK:
  if job['state']=='cancelled':return
  job.update(state='running',startedAt=time.time(),stage='Constructing mesh')
 folder=job['directory'];command=[sys.executable,'-X','utf8',str(ROOT/'worker.py'),'--job',str(folder)]
 try:
  with (folder/'worker.log').open('w',encoding='utf-8') as log:
   process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   with LOCK:
    job['process']=process
    if job['state']=='cancelled':terminate_worker(process)
   limit=MESHES.get(job.get('meshId'),{}).get('solverTimeoutSeconds',600)
   try:code=process.wait(timeout=limit)
   except subprocess.TimeoutExpired:
    terminate_worker(process);code=process.wait(timeout=10)
    with LOCK:
     if job['state']!='cancelled':
      duration='ten' if limit==600 else f'{limit/60:g}'
      job['error']=f'The mesh calculation exceeded the {duration}-minute limit.'
  with LOCK:
   job.update(finishedAt=time.time(),actualExitCode=code)
   if job['state']!='cancelled':
    report=read(folder/'report.json') if (folder/'report.json').exists() else {}
    if code==0 and report.get('passed') is True and (folder/'mesh.json').exists():job.update(state='complete',stage='Mesh ready',resultUrl='/api/jobs/'+job['id']+'/mesh.json')
    else:job.update(state='failed',stage='Could not generate this network',error=job.get('error') or report.get('message') or 'The solver could not complete this guide network. Try a shorter stroke on one visible surface.')
 except Exception as error:
  with LOCK:
   if job['state']!='cancelled':job.update(state='failed',stage='Worker failed',error=str(error),finishedAt=time.time())
 finally:
  with LOCK:diagnostic(folder/'execution.json',dict(snapshot(job),command=command))

class Handler(BaseHTTPRequestHandler):
 server_version='RetopoDemo/1.0'
 def log_message(self,format,*args):print('%s %s'%(self.log_date_time_string(),format%args),flush=True)
 def respond(self,data,status=200):
  payload=json.dumps(data,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(payload)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(payload)
 def file(self,path,download=False):
  if not path.is_file():return self.respond(dict(error='File not available'),404)
  data=path.read_bytes();self.send_response(200);kind='text/javascript' if path.suffix=='.js' else mimetypes.guess_type(str(path))[0] or 'application/octet-stream';self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-cache')
  if download:self.send_header('Content-Disposition','attachment; filename="'+path.name+'"')
  self.end_headers();self.wfile.write(data)
 def do_GET(self):
  path=self.path.split('?',1)[0]
  if path=='/api/health':return self.respond(dict(ready=True,engine='Local reference engine',models=len(MESHES)))
  if path=='/api/catalog':return self.respond(CATALOG)
  match=re.fullmatch('/api/(?:mesh/([a-z-]+)|parts/([a-f0-9]{64}))/creases',path)
  if match:
   query=parse_qs(urlsplit(self.path).query)
   try:
    try:angle=float(query.get('angle',[DEFAULT_CREASE_ANGLE])[0])
    except ValueError:angle=math.nan
    angle=check_crease_angle(angle)
    try:target=int(query.get('target',['x'])[0])
    except ValueError:target=0
    if not 150<=target<=12000:raise ValueError('Target must be an integer from 150 to 12,000.')
    if match[1]:
     if match[1] not in MESHES:return self.respond(dict(error='Unknown mesh'),404)
    else:
     from mesh_parts import load_part
     load_part(match[2])
    return self.respond(source_creases(match[2],match[1],angle,target))
   except ValueError as error:return self.respond(dict(error=str(error)),400)
  match=re.fullmatch('/api/mesh/([a-z-]+)',path)
  if match:
   key=match[1]
   if key not in MESHES:return self.respond(dict(error='Unknown mesh'),404)
   data=read(ROOT/'assets/models'/(key+'.json'));data['previewUrl']='/assets/previews/'+key+'.json' if (ROOT/'assets/previews'/(key+'.json')).exists() else None;return self.respond(data)
  match=re.fullmatch('/api/parts/([a-f0-9]{64})/results/([a-f0-9]{32})(/output.obj)?',path)
  if match:
   from mesh_parts import load_part
   try:
    part,_=load_part(match[1]);folder=ROOT/'runs'/match[2];report=read(folder/'report.json');execution=read(folder/'execution.json');mesh=read(folder/'mesh.json')
    if not report.get('passed') or execution.get('state')!='complete' or mesh.get('partSource')!=match[1] or mesh.get('sourceSha256')!=part['sourceSha256']:raise ValueError('No accepted result matches this working part.')
    if match[3]:return self.file(folder/'output.obj',download=True)
    return self.respond(mesh)
   except (OSError,ValueError,KeyError) as error:return self.respond(dict(error=str(error)),404)
  match=re.fullmatch('/api/parts/([a-f0-9]{64})',path)
  if match:
   from mesh_parts import load_part
   try:return self.respond(load_part(match[1])[0])
   except ValueError as error:return self.respond(dict(error=str(error)),400)
  match=re.fullmatch('/api/parts/([a-f0-9]{64})/latest-job',path)
  if match:
   from mesh_parts import load_part
   try:part,_=load_part(match[1])
   except ValueError as error:return self.respond(dict(error=str(error)),400)
   for entry in sorted((ROOT/'runs').glob('*/execution.json'),key=lambda p:p.stat().st_mtime,reverse=True):
    try:
     settings=read(entry.parent/'settings.json')
     if settings.get('partSource')==match[1] and settings.get('sourceSha256')==part['sourceSha256']:
      job=persisted_job(entry.parent.name)
      if job:return self.respond(job_status(job))
    except (OSError,ValueError):continue
   return self.respond(dict(error='No saved attempt for this part.'),404)
  match=re.fullmatch('/api/jobs/([a-f0-9]{32})(?:/(mesh.json|output.obj|curves.json|settings.json|features.json|report.json))?',path)
  if match:
   with LOCK:job=JOBS.get(match[1]);job=dict(job) if job else None
   if job is None:job=persisted_job(match[1])
   if not job:return self.respond(dict(error='Job not found; the server may have restarted.'),404)
   if not match[2]:
    try:cursor=int(parse_qs(urlsplit(self.path).query).get('after',['0'])[0])
    except ValueError:return self.respond(dict(error='Invalid log cursor.'),400)
    if cursor<0:return self.respond(dict(error='Invalid log cursor.'),400)
    return self.respond(job_status(job,cursor))
   data=snapshot(job)
   # Worker files can exist before acceptance or survive cancellation/failure.
   # Their presence is not authorization to publish a generated result.
   if match[2] in ('mesh.json','output.obj','features.json') and data['state']!='complete':
    return self.respond(dict(error='No accepted result is available for this job.'),409)
   return self.file(job['directory']/match[2],download=match[2] not in ('mesh.json','report.json'))
  if path=='/':return self.file(ROOT/'index.html')
  if path in ['/app.js','/favicon.svg','/index.css']:return self.file(ROOT/path[1:])
  if re.fullmatch(r'/src/(geometry|domain|view|io|snapping|contracts)/[A-Za-z0-9_-]+\.js',path):return self.file(ROOT/path[1:])
  if re.fullmatch('/vendor/[A-Za-z0-9_.-]+',path):return self.file(ROOT/path[1:])
  if re.fullmatch(r'/assets/previews/[a-z-]+\.(json|obj)',path):return self.file(ROOT/path[1:])
  return self.respond(dict(error='Not found'),404)
 def do_POST(self):
  try:
   origin=self.headers.get('Origin')
   if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):return self.respond(dict(error='Use the local application origin.'),403)
   if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Use application/json for API requests.')
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=2_000_000:raise ValueError('Request is empty or too large.')
   data=json.loads(self.rfile.read(length))
   if not isinstance(data,dict):raise ValueError('The request must be a JSON object.')
   match=re.fullmatch('/api/jobs/([a-f0-9]{32})/cancel',self.path)
   if match:
    with LOCK:
     job=JOBS.get(match[1])
     if not job:return self.respond(dict(error='Unknown job'),404)
     data=cancel_job(job)
    return self.respond(data)
   match=re.fullmatch('/api/requests/([a-f0-9]{32})/cancel',self.path)
   if match:
    request_id=match[1]
    with LOCK:
     # A cancellation may arrive before the original request. Keep a tombstone
     # so delayed delivery cannot create a worker after the page has reset.
     record=REQUESTS.setdefault(request_id,dict(jobId=None,fingerprint=None))
     data=cancel_job(JOBS[record['jobId']]) if record['jobId'] else cancelled_request(request_id)
    return self.respond(data)
   if self.path=='/api/parts/split':
    from mesh_parts import split
    if data.get('meshId') not in MESHES:raise ValueError('Choose a source model.')
    return self.respond(split(MESHES[data['meshId']],data))
   if self.path!='/api/remesh':return self.respond(dict(error='Not found'),404)
   request_id=data.get('requestId')
   if 'requestId' in data and (not isinstance(request_id,str) or not re.fullmatch('[a-f0-9]{32}',request_id)):raise ValueError('Request ID must contain 32 lowercase hexadecimal characters.')
   mesh_id=data.get('meshId');target=data.get('target');curves=data.get('curves');mode=data.get('guideMode',2)
   if mesh_id not in MESHES:raise ValueError('Choose one of the example meshes.')
   part=None
   if 'partSource' in data:
    from mesh_parts import load_part
    part,_=load_part(data['partSource'],mesh_id)
    if not part['canRemesh']:raise ValueError('An excluded open region cannot be generated. Undo its split to restore the original source.')
   if part is None and MESHES[mesh_id].get('canRemesh') is False:raise ValueError('Select one source part and choose Work on selected before generating.')
   maximum=MESHES[mesh_id].get('maxTargetQuads',1800)
   if isinstance(target,bool) or not isinstance(target,int) or not 150<=target<=maximum:raise ValueError(f'Target must be an integer from 150 to {maximum:,}.')
   if mode not in [1,2] or isinstance(mode,bool):raise ValueError('Unknown guide behavior.')
   crease_angle=check_crease_angle(data.get('creaseAngle',DEFAULT_CREASE_ANGLE))
   if mesh_id!='cylinder' and mode!=2:raise ValueError('This mesh uses preserved guide paths.')
   if not isinstance(curves,list) or len(curves)>48:raise ValueError('Use at most48 guide curves.')
   total=0
   import math
   for curve in curves:
    if not isinstance(curve,list) or not 2<=len(curve)<=2048:raise ValueError('Each guide needs2–2048 surface samples.')
    total+=len(curve)
    for point in curve:
     if not isinstance(point,list) or len(point)!=3 or not all(type(x) in (float,int) and abs(x)<1e6 and math.isfinite(x) for x in point):raise ValueError('Guides must contain finite XYZ surface positions.')
   if total>8192:raise ValueError('Use fewer guide samples.')
   if not part and (mesh_id=='cylinder' or MESHES[mesh_id].get('requiresGuides')) and not curves:raise ValueError('Draw a guide or load the example network for the curved mesh.')
   fingerprint=hashlib.sha256(json.dumps(dict(meshId=mesh_id,target=target,curves=curves,guideMode=mode,creaseAngle=crease_angle,sourceSha256=MESHES[mesh_id]['sourceSha256'],partSource=data.get('partSource')),sort_keys=True,allow_nan=False).encode()).hexdigest()
   replay=None;conflict=False
   with LOCK:
    record=REQUESTS.get(request_id) if request_id else None
    if record is not None:
     conflict=record['fingerprint'] not in (None,fingerprint)
     if not conflict:
      record['fingerprint']=fingerprint
      replay=snapshot(JOBS[record['jobId']]) if record['jobId'] else cancelled_request(request_id)
    else:
     if sum(j['state'] in ('queued','running') for j in JOBS.values())>=3:raise ValueError('Wait for the current calculation or cancel it first.')
     job_id=uuid.uuid4().hex;folder=ROOT/'runs'/job_id;folder.mkdir(parents=True)
     write(folder/'settings.json',dict(meshId=mesh_id,target=target,guideMode=mode,creaseAngle=crease_angle,sourceSha256=MESHES[mesh_id]['sourceSha256'],createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat()))
     if part:
      settings=read(folder/'settings.json');settings.update(partSource=data['partSource'],sourceSha256=part['sourceSha256'],originalSourceSha256=MESHES[mesh_id]['sourceSha256']);write(folder/'settings.json',settings)
     write(folder/'curves.json',dict(coordinateFrame='source',curves=curves))
     job=dict(id=job_id,meshId=mesh_id,target=target,state='queued',stage='Waiting for solver',createdAt=time.time(),directory=folder);JOBS[job_id]=job
     if request_id:
      job['requestId']=request_id;REQUESTS[request_id]=dict(jobId=job_id,fingerprint=fingerprint)
   if conflict:return self.respond(dict(error='This request ID already belongs to different generation parameters.'),409)
   if replay is not None:return self.respond(replay,202)
   QUEUE.submit(execute,job)
   # A worker can insert process/exit fields immediately after submission.
   # Copy the acknowledgement under the same lock as every worker update.
   with LOCK:response=snapshot(job)
   return self.respond(response,202)
  except (ValueError,TypeError,json.JSONDecodeError) as error:return self.respond(dict(error=str(error)),400)

class LocalHTTPServer(ThreadingHTTPServer):
 # Windows SO_REUSEADDR permits two independent app instances to accept on
 # one port. Exclusivity prevents an older server from serving stale state.
 allow_reuse_address=os.name!='nt'
 def server_bind(self):
  if os.name=='nt':self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
  super().server_bind()

def owns_server_process(process):
 # Match the Python entrypoint, not an incidental server.py data argument.
 command=process.cmdline()
 if not command or not re.fullmatch(r'pythonw?(?:\d+(?:\.\d+)*)?(?:\.exe)?',Path(command[0]).name.lower()):return False
 arguments=iter(command[1:])
 for argument in arguments:
  if argument in ('-c','-m'):return False
  if argument in ('-X','-W','--check-hash-based-pycs'):
   next(arguments,None);continue
  if argument.startswith('-'):continue
  script=Path(argument)
  if not script.is_absolute():script=Path(process.cwd())/script
  return script.resolve()==Path(__file__).resolve()
 return False

def listening_server(port):
 # A health response or PID file alone is not proof of process ownership.
 try:
  for connection in psutil.net_connections(kind='tcp'):
   if connection.status!=psutil.CONN_LISTEN or not connection.pid or connection.laddr.port!=port:continue
   if connection.laddr.ip not in ('127.0.0.1','0.0.0.0','::','::ffff:127.0.0.1'):continue
   try:
    process=psutil.Process(connection.pid)
    if owns_server_process(process):return process
   except (psutil.Error,OSError,ValueError):continue
 except psutil.Error:pass
 return None

def existing_server(port):
 process=listening_server(port)
 if process is None:return None
 try:
  opener=build_opener(ProxyHandler({}))
  with opener.open(f'http://127.0.0.1:{port}/api/health',timeout=2) as response:health=json.loads(response.read(4096))
  if isinstance(health,dict) and health.get('ready') is True and health.get('engine')=='Local reference engine':return process.pid
 except (OSError,ValueError):pass
 return None

def restart_existing(port):
 # Also find our recorded instance if the previous launch selected a fallback
 # port. Other unrecorded ports/checkouts remain independent instances.
 candidates=[(port,None)]
 try:
  previous=read(ROOT/'runs/server.json')
  if type(previous.get('port')) is int and type(previous.get('pid')) is int and 1<=previous['port']<=65535:
   candidates.append((previous['port'],previous['pid']))
 except (OSError,ValueError,AttributeError):pass
 stopped=set()
 for candidate,expected_pid in candidates:
  process=listening_server(candidate)
  if process is None or process.pid in stopped or (expected_pid is not None and process.pid!=expected_pid):continue
  if not owns_server_process(process):continue
  children=process.children(recursive=True)
  print(f'Stopping Retopo1 on port {candidate} (PID {process.pid})...',flush=True)
  try:
   process.terminate()
   try:process.wait(timeout=5)
   except psutil.TimeoutExpired:process.kill();process.wait(timeout=5)
  except psutil.NoSuchProcess:pass
  # Windows lifetime jobs already close descendants; this also cleans up
  # owned workers on other platforms and older servers without a lifetime job.
  for child in reversed(children):
   try:child.kill()
   except psutil.NoSuchProcess:pass
  psutil.wait_procs(children,timeout=5)
  stopped.add(process.pid)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8741)
 ap.add_argument('--restart',action='store_true',help='Stop this checkout\'s existing server before starting')
 ap.add_argument('--next-port',action='store_true',help='Choose another available port if the requested port is occupied')
 args=ap.parse_args()
 if not 1<=args.port<=65535:ap.error('--port must be between 1 and 65535')
 protect_service_tree()
 if args.restart:
  try:restart_existing(args.port)
  except (psutil.Error,OSError) as error:
   print(f'Could not stop the existing Retopo1 server: {error}',file=sys.stderr,flush=True);return 1
 ports=list(range(args.port,min(args.port+100,65536)))+[0] if args.next_port else [args.port]
 for port in ports:
  try:server=LocalHTTPServer(('127.0.0.1',port),Handler);break
  except OSError as error:
   unavailable=error.errno in (errno.EADDRINUSE,errno.EACCES) or getattr(error,'winerror',None) in (10048,10013)
   if unavailable and args.next_port and port:
    print(f'Port {port} is unavailable; trying another port...',flush=True);continue
   if unavailable:
    owner=existing_server(port)
    if owner is not None:
     print(f'Retopo1 is already running on port {port} (PID {owner}). Keep using your existing browser tab, or open http://localhost:{port}',flush=True);return 0
    alternative=8742 if port!=8742 else 8743
    print(f'Port {port} is already in use by another process or an unresponsive server. Try start.cmd --port {alternative}',file=sys.stderr,flush=True)
   else:print(f'Could not listen on port {port}: {error}',file=sys.stderr,flush=True)
   return 1
 port=server.server_port
 (ROOT/'runs').mkdir(exist_ok=True)
 write(ROOT/'runs/server.json',dict(pid=os.getpid(),url=f'http://127.0.0.1:{port}',port=port));print(f'Retopo1 is ready at http://127.0.0.1:{port}',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:
  with LOCK:
   for job in JOBS.values():
    if job.get('process') and job['process'].poll() is None:terminate_worker(job['process'])
  server.server_close();QUEUE.shutdown(wait=False,cancel_futures=True)
if __name__=='__main__':raise SystemExit(main())
