"""Negative quality-gate control using the retained known-bad candidate.

The meshing boundary is explicitly injected. This is a rejection regression,
never claimed to be a successful construction or native numerical experiment.
"""
from pathlib import Path
import sys,json,uuid,shutil,hashlib,contextlib,io
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));import worker
from quad_quality import measure
OUT=ROOT/'tests/quality-repair/rejection-controls';OUT.mkdir(exist_ok=False)
checks=[]
def check(value,name):
 checks.append({'name':name,'passed':bool(value)})
 if not value:raise AssertionError(name)
square=np.array([[0.,0,0],[1,0,0],[1,1,0],[0,1,0]])
q=measure(square,[[0,1,2,3]],1);check(q['passed'] and abs(q['scaledJacobianMin']-1)<1e-14 and abs(q['minimumAngleDegrees']-90)<1e-12,'Unit square calibrates corner signs, angles and shape scale')
skinny=square.copy();skinny[:,0]*=100;check(not measure(skinny,[[0,1,2,3]],1)['passed'],'Long thin quad is rejected')
concave=square.copy();concave[2]=[.2,.2,0];check(not measure(concave,[[0,1,2,3]],1)['passed'],'Concave inverted-corner quad is rejected')
bow=square[[0,2,1,3]];check(not measure(bow,[[0,1,2,3]],1)['passed'],'Crossed bow-tie quad is rejected')
original=ROOT/'tests/quality-repair/original/user-failed-run';old=json.loads((original/'mesh.json').read_text());job=ROOT/'runs'/uuid.uuid4().hex;job.mkdir();shutil.copy2(original/'settings.json',job/'settings.json');shutil.copy2(original/'curves.json',job/'curves.json');stream=io.StringIO()
with patch.object(worker,'construct_structured',return_value=(np.array(old['vertices']),old['faces'],{'backend':'negative-control-known-bad-output'})),patch.object(sys,'argv',['worker.py','--job',str(job)]),contextlib.redirect_stderr(stream),contextlib.redirect_stdout(stream):code=worker.main()
(OUT/'worker.log').write_text(stream.getvalue(),encoding='utf-8');report=json.loads((job/'report.json').read_text());check(code==1 and report['passed'] is False and report['constructionCompleted'] is True,'Actual worker rejects the known-bad candidate after construction')
check(not (job/'output.obj').exists() and not (job/'mesh.json').exists(),'Rejected candidate cannot be exposed as a successful output')
check((job/'failed-output.obj').exists() and (job/'failed-mesh.json').exists() and (job/'quality.json').exists(),'Failed candidate geometry and explicit quality reasons are preserved')
result={'passed':True,'checks':checks,'injectedKnownBadGeometry':True,'successfulConstructionClaimed':False,'workerReturnCode':code,'rejectedJob':job.name,'report':report,'workerSha256':hashlib.sha256((ROOT/'worker.py').read_bytes()).hexdigest(),'scope':'Negative acceptance-gate control plus independent analytic element calibration. The injected mesh is the exact user-rejected 620-face fixture; no new successful construction is implied.'};(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'passed':True,'checks':len(checks),'job':job.name}))
