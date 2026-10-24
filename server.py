"""Local canvas demo server; each solve runs in its own owned Python worker."""
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import argparse,datetime,json,mimetypes,os,re,subprocess,sys,threading,time,uuid

ROOT=Path(__file__).resolve().parent
CATALOG=json.loads((ROOT/'assets/catalog.json').read_text(encoding='utf-8'))
MESHES={m['id']:m for m in CATALOG};JOBS={};LOCK=threading.Lock();QUEUE=ThreadPoolExecutor(max_workers=1)

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,data):p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def snapshot(job):return {k:v for k,v in job.items() if k not in ('process','directory')}
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
    if job['state']=='cancelled':process.terminate()
   try:code=process.wait(timeout=600)
   except subprocess.TimeoutExpired:process.terminate();code=process.wait(timeout=10);job['error']='The mesh calculation exceeded the ten-minute limit.'
  with LOCK:
   job.update(finishedAt=time.time(),actualExitCode=code)
   if job['state']!='cancelled':
    report=read(folder/'report.json') if (folder/'report.json').exists() else {}
    if code==0 and report.get('passed') is True and (folder/'mesh.json').exists():job.update(state='complete',stage='Mesh ready',resultUrl='/api/jobs/'+job['id']+'/mesh.json')
    else:job.update(state='failed',stage='Could not generate this network',error=job.get('error') or report.get('message') or 'The solver could not complete this guide network. Try a shorter stroke on one visible surface.')
 except Exception as error:
  with LOCK:job.update(state='failed',stage='Worker failed',error=str(error),finishedAt=time.time())
 finally:
  with LOCK:write(folder/'execution.json',dict(snapshot(job),command=command))

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
  match=re.fullmatch('/api/mesh/([a-z-]+)',path)
  if match:
   key=match[1]
   if key not in MESHES:return self.respond(dict(error='Unknown mesh'),404)
   data=read(ROOT/'assets/models'/(key+'.json'));data['previewUrl']='/assets/previews/'+key+'.json' if (ROOT/'assets/previews'/(key+'.json')).exists() else None;return self.respond(data)
  match=re.fullmatch('/api/jobs/([a-f0-9]{32})(?:/(mesh.json|output.obj|curves.json|settings.json|features.json|report.json))?',path)
  if match:
   with LOCK:job=JOBS.get(match[1]);data=snapshot(job) if job else None
   if not job:return self.respond(dict(error='Job not found; the server may have restarted.'),404)
   if not match[2]:return self.respond(data)
   return self.file(job['directory']/match[2],download=match[2] not in ('mesh.json','report.json'))
  if path=='/':return self.file(ROOT/'index.html')
  if path in ['/app.js','/favicon.svg']:return self.file(ROOT/path[1:])
  if re.fullmatch(r'/src/(geometry|domain|view|io|snapping|contracts)/[A-Za-z0-9_-]+\.js',path):return self.file(ROOT/path[1:])
  if re.fullmatch('/vendor/[A-Za-z0-9_.-]+',path):return self.file(ROOT/path[1:])
  if re.fullmatch('/assets/previews/[a-z-]+\.(json|obj)',path):return self.file(ROOT/path[1:])
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
     if job['state'] in ('queued','running'):
      previous=job['state']
      job.update(state='cancelled',stage='Cancelled',finishedAt=time.time())
      write(job['directory']/'cancel-request.json',snapshot(job))
      if previous=='queued':write(job['directory']/'execution.json',dict(snapshot(job),actualExitCode=None,processStarted=False))
      if job.get('process') and job['process'].poll() is None:job['process'].terminate()
    return self.respond(snapshot(job))
   if self.path!='/api/remesh':return self.respond(dict(error='Not found'),404)
   mesh_id=data.get('meshId');target=data.get('target');curves=data.get('curves');mode=data.get('guideMode',2)
   if mesh_id not in MESHES:raise ValueError('Choose one of the example meshes.')
   if isinstance(target,bool) or not isinstance(target,int) or not 150<=target<=1800:raise ValueError('Target must be an integer from150 to1800.')
   if mode not in [1,2] or isinstance(mode,bool):raise ValueError('Unknown guide behavior.')
   if mesh_id!='cylinder' and mode!=2:raise ValueError('This mesh uses preserved guide paths.')
   if not isinstance(curves,list) or len(curves)>48:raise ValueError('Use at most48 guide curves.')
   total=0
   import math
   for curve in curves:
    if not isinstance(curve,list) or not 2<=len(curve)<=2048:raise ValueError('Each guide needs2–2048 surface samples.')
    total+=len(curve)
    for point in curve:
     if not isinstance(point,list) or len(point)!=3 or not all(type(x) in (float,int) and math.isfinite(x) and abs(x)<1e6 for x in point):raise ValueError('Guides must contain finite XYZ surface positions.')
   if total>8192:raise ValueError('Use fewer guide samples.')
   if mesh_id=='cylinder' and not curves:raise ValueError('Draw a guide or load the example network for the curved mesh.')
   with LOCK:
    if sum(j['state'] in ('queued','running') for j in JOBS.values())>=3:raise ValueError('Wait for the current calculation or cancel it first.')
    job_id=uuid.uuid4().hex;folder=ROOT/'runs'/job_id;folder.mkdir(parents=True)
    write(folder/'settings.json',dict(meshId=mesh_id,target=target,guideMode=mode,sourceSha256=MESHES[mesh_id]['sourceSha256'],createdAt=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    write(folder/'curves.json',dict(coordinateFrame='source',curves=curves))
    job=dict(id=job_id,meshId=mesh_id,target=target,state='queued',stage='Waiting for solver',createdAt=time.time(),directory=folder);JOBS[job_id]=job
   QUEUE.submit(execute,job);return self.respond(snapshot(job),202)
  except (ValueError,TypeError,json.JSONDecodeError) as error:return self.respond(dict(error=str(error)),400)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--port',type=int,default=8741);args=ap.parse_args()
 server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);(ROOT/'runs').mkdir(exist_ok=True)
 write(ROOT/'runs/server.json',dict(pid=os.getpid(),url=f'http://127.0.0.1:{args.port}',port=args.port));print(f'Retopo1 is ready at http://127.0.0.1:{args.port}',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:
  with LOCK:
   for job in JOBS.values():
    if job.get('process') and job['process'].poll() is None:job['process'].terminate()
  server.server_close();QUEUE.shutdown(wait=False,cancel_futures=True)
if __name__=='__main__':main()
