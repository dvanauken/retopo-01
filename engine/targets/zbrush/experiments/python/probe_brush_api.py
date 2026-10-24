"""Read-only supported Python API inspection in a fresh owned batch child."""
import argparse,hashlib,json,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
HOST_SHA='0fa10544438f5b7fe520a2a44b92183370001aacbd218daa96a65b179f45dff7'

def main():
    host=Path(json.loads((ROOT/'targets/zbrush/target.local.json').read_text(encoding='utf-8-sig'))['inputs']['host'])
    if hashlib.sha256(host.read_bytes()).hexdigest()!=HOST_SHA:raise RuntimeError('Runtime host identity changed')
    parser=argparse.ArgumentParser();parser.add_argument('--run-name',default='api-inspection');args=parser.parse_args()
    if not args.run_name.replace('-','').isalnum():raise ValueError('Simple run name required')
    out=ROOT/'work/zbrush/brushes'/args.run_name
    out.mkdir(parents=True,exist_ok=False)
    script=out/'inspect_api.py'
    script.write_text('''import json,sys,traceback
from pathlib import Path
out=Path(__file__).resolve().parent
(out/'entered.txt').write_text('Python entered',encoding='utf-8')
try:
 import zbrush.commands as zbc
 names=['stroke','canvas_stroke','canvas_strokes','get_stroke_info','get_last_stroke','query_mesh3d','get','press','set','exists','set_next_filename']
 rows=[dict(name=n,exists=hasattr(zbc,n),doc=getattr(getattr(zbc,n,None),'__doc__',None)) for n in names]
 (out/'api.json').write_text(json.dumps(dict(passed=True,commands=rows),indent=2),encoding='utf-8')
except BaseException:
 (out/'api.json').write_text(json.dumps(dict(passed=False,error=traceback.format_exc()),indent=2),encoding='utf-8')
sys.exit(0)
''',encoding='utf-8')
    result=dict(hostSha256=HOST_SHA,started=time.time(),scope='Own fresh batch child; API docs only, no sculpting or existing user session interaction.')
    with (out/'process.log').open('w',encoding='utf-8') as log:
        child=subprocess.Popen([str(host),'-batch','-script',str(script)],cwd=host.parent,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        result['pid']=child.pid
        try:result['exitCode']=child.wait(timeout=60);result['timedOut']=False
        except subprocess.TimeoutExpired:
            child.terminate();result['exitCode']=child.wait(timeout=15);result['timedOut']=True
    result.update(finished=time.time(),pythonEntered=(out/'entered.txt').exists())
    result['passed']=result['pythonEntered'] and not result['timedOut'] and result['exitCode']==0 and (out/'api.json').exists() and json.loads((out/'api.json').read_text(encoding='utf-8'))['passed']
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
