"""Run actual part workers with unchanged acceptance gates and retained evidence.

--project-root can point at a frozen project. Failed attempts remain failures.
Timeout and CPU caps are verification policy, never geometry acceptance rules.
"""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, sys, time, uuid

ROOT=Path(__file__).resolve().parents[1]
GUIDE=ROOT/'tests/fixtures/island6-authored-guide.json'
CASES=[('island6-150','skp-6',150,False),('island6-200','skp-6',200,False),
       ('island6-300','skp-6',300,False),('island6-750-guide','skp-6',750,True),
       ('island2-300','skp-2',300,False),('island7-300','skp-7',300,False),
       ('island10-500','skp-10',500,False)]

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,data):p.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def code_identity(root):
    paths=list(root.glob('*.py'))
    for rel in ('engine/targets/zbrush/clone','engine/targets/zbrush/experiments/python'):
        paths.extend((root/rel).rglob('*.py'))
    paths.extend(root/'engine/guided-quadriflow'/n for n in ('quadriflow.exe','manifest.json'))
    return {p.relative_to(root).as_posix():sha(p) for p in sorted(paths) if p.is_file()}

def engine_identity(root,env):
    vendor=Path(env.get('RETOPO_REGISTERED_ENGINE',str(root/'engine/guided-quadriflow')))
    manifest=read(vendor/'manifest.json')
    paths=[vendor/'manifest.json',vendor/'quadriflow.exe']
    runtime=Path(env.get('RETOPO_MINGW_RUNTIME',manifest['runtimeDirectory']))
    paths.extend(runtime/name for name in manifest['runtimeImports'])
    return {str(path.resolve()):sha(path) for path in paths}

def prepare(root,case,angle,packet,run_id):
    name,part_id,target,guided=case;model=read(root/'assets/models/toilet-skp.json')
    part=next(p for p in model['initialParts'] if p['id']==part_id)
    source=root/'runs/parts'/part['partSource']/'source.obj'
    settings=dict(meshId='toilet-skp',partSource=part['partSource'],target=target,guideMode=2,
                  creaseAngle=angle,sourceSha256=sha(source),originalSourceSha256=model['sourceSha256'])
    job=root/'runs'/('registered-'+run_id+'-'+name);job.mkdir(parents=True,exist_ok=False)
    write(job/'settings.json',settings)
    write(job/'curves.json',packet if guided else dict(coordinateFrame='source',curves=[]))
    return job,settings

def last_event(job):
    try:return json.loads((job/'events.jsonl').read_text(encoding='utf-8').splitlines()[-1])['message']
    except (OSError,ValueError,KeyError,IndexError):return ''

def run(root,case,angle,packet,run_id,out,timeout,env):
    job,settings=prepare(root,case,angle,packet,run_id)
    command=[sys.executable,'-X','utf8',str(root/'worker.py'),'--feature-layout','--job',str(job)]
    row=dict(case=case[0],part=case[1],job=str(job),settings=settings,command=command,
             curvesSha256=sha(job/'curves.json'),guideCount=len(packet['curves']) if case[3] else 0)
    write(out/(case[0]+'-request.json'),row);started=time.monotonic();print('START',case[0],job,flush=True)
    with (job/'worker.log').open('w',encoding='utf-8') as log:
        child=subprocess.Popen(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        previous=None
        try:
            while child.poll() is None:
                elapsed=time.monotonic()-started
                if elapsed>timeout:row['timedOut']=True;child.kill();child.wait(timeout=30);break
                stage=last_event(job)
                if stage!=previous:print('PROGRESS',case[0],round(elapsed,1),stage,flush=True);previous=stage
                time.sleep(2)
        finally:
            # Actual worker owns a kill-on-close Windows job, covering its engine.
            if child.poll() is None:child.kill();child.wait(timeout=30)
    row.update(exitCode=child.returncode,observedSeconds=time.monotonic()-started)
    report=read(job/'report.json') if (job/'report.json').exists() else {}
    mesh=read(job/'mesh.json') if (job/'mesh.json').exists() else {}
    row['report']=report;row['passed']=bool(child.returncode==0 and report.get('passed') and mesh)
    if mesh:
        keys=('stats','quality','featureValidation','surfaceValidation','boundaryValidation','intersectionValidation','guidePaths','elapsedSeconds','registeredFeatures','registrationSkipped','layoutStyle','candidateSelection','featureRows')
        row['result']={k:mesh.get(k) for k in keys};row['faces']=len(mesh['faces']);row['outputSha256']=sha(job/'output.obj')
        row['allAcceptanceGatesPassed']=all(mesh.get(k,{}).get('passed') for k in ('quality','featureValidation','surfaceValidation','intersectionValidation')+(('boundaryValidation',) if mesh.get('openSurface') else ()))
        row['passed']=row['passed'] and row['allAcceptanceGatesPassed']
        assert sha(job/'source.obj')==settings['sourceSha256'],'Source integrity'
    row['retainedMetadata']={n:str(job/n) for n in ('engine-provenance.json','open-surface.json','surface-solver.json') if (job/n).exists()}
    write(out/(case[0]+'-result.json'),row)
    print('RESULT',case[0],row['passed'],'faces',row.get('faces'),'seconds',round(row['observedSeconds'],1),report.get('message',''),flush=True)
    return row

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project-root',type=Path,default=ROOT)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--case',action='append',choices=[c[0] for c in CASES])
    ap.add_argument('--crease-angle',type=float,default=30.);ap.add_argument('--guide',type=Path,default=GUIDE)
    ap.add_argument('--timeout',type=float,default=720.);ap.add_argument('--env',action='append',default=[],metavar='NAME=VALUE')
    a=ap.parse_args();root=a.project_root.resolve();out=a.out.resolve()
    if not out.is_relative_to(ROOT):ap.error('Evidence must remain inside this workspace')
    out.mkdir(parents=True,exist_ok=False);(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes());packet=read(a.guide)
    if packet.get('coordinateFrame')!='source' or not packet.get('curves'):ap.error('Expected authored source-space guide')
    write(out/'authored-guide.json',packet);env=os.environ.copy()
    overrides={k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}
    for value in a.env:
        if '=' not in value:ap.error('--env must be NAME=VALUE')
        key,item=value.split('=',1);overrides[key]=item
    env.update(overrides);run_id=uuid.uuid4().hex[:12];before=code_identity(root)
    result=dict(projectRoot=str(root),runnerSha256=sha(Path(__file__)),runId=run_id,command=sys.argv,
                environmentOverrides=overrides,guideSource=str(a.guide.resolve()),guideSha256=sha(a.guide),
                codeBefore=before,engineBefore=engine_identity(root,env),creaseAngle=a.crease_angle,cases=[],
                scope='Actual worker inputs and unchanged acceptance gates. No native ZBrush, mocks or substituted solver outputs.')
    write(out/'manifest.json',result)
    for case in CASES:
        if a.case and case[0] not in a.case:continue
        result['cases'].append(run(root,case,a.crease_angle,packet,run_id,out,a.timeout,env))
        write(out/'result.json',result)
    result['codeAfter']=code_identity(root);result['engineAfter']=engine_identity(root,env)
    result['codeStable']=before==result['codeAfter'] and result['engineBefore']==result['engineAfter']
    result['allPassed']=all(r['passed'] for r in result['cases']);result['passedCases']=sum(r['passed'] for r in result['cases'])
    write(out/'result.json',result)
    print('MATRIX',result['passedCases'],'/',len(result['cases']),'codeStable',result['codeStable'],flush=True)
    return 0 if result['allPassed'] and result['codeStable'] else 1

if __name__=='__main__':raise SystemExit(main())

