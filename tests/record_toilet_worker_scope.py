"""Record the scope of shared opt-in route edits versus the tested toilet route."""
import ast,hashlib,json,subprocess
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'tests/toilet-exhaustive-audit'
sha=lambda data:hashlib.sha256(data).hexdigest()
def old(file):
 return subprocess.run(['git','-c','safe.directory=C:/dbva/code/retopo-1','show','c8e5b83:'+file],cwd=ROOT,capture_output=True,check=True).stdout
def parsed(data):return ast.parse(data.decode('utf-8'))
def dump(tree):return ast.dump(tree,include_attributes=False)
baseline=parsed(old('curved_quad.py'));shared_bytes=(ROOT/'curved_quad.py').read_bytes();shared=parsed(shared_bytes)
# Compare the exact original AST after removing only the documented opt-in guard.
shared.body[0]=baseline.body[0]
function=next(node for node in shared.body if isinstance(node,ast.FunctionDef) and node.name=='construct')
idx=next(i for i,arg in enumerate(function.args.kwonlyargs) if arg.arg=='guided_layout')
assert isinstance(function.args.kw_defaults[idx],ast.Constant) and function.args.kw_defaults[idx].value is False
function.args.kwonlyargs.pop(idx);function.args.kw_defaults.pop(idx)
guards=[node for node in function.body if isinstance(node,ast.If) and ast.unparse(node.test)=='curves and guided_layout']
assert len(guards)==1
function.body.remove(guards[0])
assert dump(shared)==dump(baseline),'An additional fitter change requires separate regression coverage'
worker_bytes=(ROOT/'worker.py').read_bytes();worker=parsed(worker_bytes)
worker_baseline=parsed((OUT/'worker-nested-job-tested.py').read_bytes())
calls=[node for node in ast.walk(worker) if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='construct_curved_quads']
assert len(calls)==1
keyword=next(kw for kw in calls[0].keywords if kw.arg=='guided_layout')
assert ast.unparse(keyword.value)=="spec.get('guidedLayout', False)"
calls[0].keywords.remove(keyword)
assert dump(worker)==dump(worker_baseline),'An additional worker change requires separate regression coverage'
spec_file=ROOT/'assets/models/toilet.json';spec=json.loads(spec_file.read_text())
assert spec.get('guidedLayout',False) is False
assert hashlib.sha256((ROOT/'process_ownership.py').read_bytes()).hexdigest()=='61b00802d0c3c662e36e0ae99cf157cca1bac6fc46250d08237b40bd84f394b9'
crash_file=ROOT/'tests/toilet-worker-crash/shared-dispatch-worker-job/result.json';crash=json.loads(crash_file.read_text())
assert crash['passed'] and all(c['passed'] for c in crash['checks'])
for name,digest in crash['sourceHashes'].items():assert sha((ROOT/name).read_bytes())==digest,name
snapshot=OUT/'curved-quad-shared-during-probes.py';snapshot.write_bytes(shared_bytes)
report=dict(checkedAt=datetime.now(timezone.utc).isoformat(),passed=True,workerOnlyCrashChecks=len(crash['checks']),
 crashReport=str(crash_file.relative_to(ROOT)),crashReportSha256=sha(crash_file.read_bytes()),
 currentSourceHashes={file:sha((ROOT/file).read_bytes()) for file in ('worker.py','curved_quad.py','process_ownership.py','assets/models/toilet.json','assets/models/toilet.obj')},
 fitterSnapshot=str(snapshot.relative_to(ROOT)),
 staticFindings=['Current worker AST equals the 166-check worker except the opt-in guided_layout keyword.','Toilet metadata disables that opt-in route.','Current fitter AST equals c8e5b83 except the module description, false-default argument and guarded new route.','Current worker-only forced-exit test passes all 11 checks on exact current bytes.'],
 scope='Static component-scope reconciliation plus a real worker-crash rerun. This is not a fresh 166-check run or validation of the separate opt-in guided-layout solver.')
(OUT/'worker-lifetime-shared-scope.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
print(json.dumps(dict(passed=True,workerOnlyCrashChecks=11,toiletNumericalRouteUnchanged=True)))
