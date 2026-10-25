"""Compare owned code with the exercised shared runtime for empty guides."""
import ast
import copy
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OWNED=ROOT/'runs/owned-boundary-candidate'
FROZEN=ROOT/'runs/frozen-boundary-service'
OUT=ROOT/'tests/surface-boundary-repair/commit-scope'
OUT.mkdir(parents=True,exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
functions=lambda path:{n.name:n for n in ast.parse(path.read_bytes()).body if isinstance(n,ast.FunctionDef)}
old=functions(OWNED/'curved_quad.py');new=functions(FROZEN/'curved_quad.py')
checked=[]
for name in old.keys()-{'construct'}:
    assert ast.dump(old[name])==ast.dump(new[name]),name
    checked.append(name)
a,b=copy.deepcopy(old['construct']),copy.deepcopy(new['construct'])
if b.args.kwonlyargs[-1].arg=='guided_layout':
    assert b.args.kw_defaults[-1].value is False
    b.args.kwonlyargs.pop();b.args.kw_defaults.pop()
removed=[]
for node in list(b.body):
    if isinstance(node,ast.If) and isinstance(node.test,ast.BoolOp) and ast.dump(node.test)==ast.dump(ast.parse('curves and guided_layout',mode='eval').body):
        b.body.remove(node);removed.append('Empty curves bypass optional guided-layout branch')
assert len(removed)==1
old_guided=next(n for n in ast.walk(a) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='guided' for t in n.targets))
new_guided=next(n for n in ast.walk(b) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='guided' for t in n.targets))
assert ast.dump(new_guided.value)==ast.dump(ast.parse('guides_pass(fit, spacing)',mode='eval').body)
new_guided.value=copy.deepcopy(old_guided.value)
old_failure=next(n for n in ast.walk(a) if isinstance(n,ast.FunctionDef) and n.name=='failures')
new_failure=next(n for n in ast.walk(b) if isinstance(n,ast.FunctionDef) and n.name=='failures')
old_loop=next(n for n in old_failure.body if isinstance(n,ast.For))
new_loop=next(n for n in new_failure.body if isinstance(n,ast.For))
assert ast.dump(new_loop.iter)==ast.dump(ast.parse("zip(attempt['guideFit'], guide_tangent_limits(attempt['guideFit']))",mode='eval').body)
new_failure.body[new_failure.body.index(new_loop)]=copy.deepcopy(old_loop)
# The function documentation does not affect execution.
if isinstance(a.body[0],ast.Expr) and isinstance(a.body[0].value,ast.Constant) and isinstance(a.body[0].value.value,str):
    b.body[0]=copy.deepcopy(a.body[0])
assert ast.dump(a)==ast.dump(b),'Unexpected non-guide difference in construction'
repair_old=functions(OWNED/'surface_guide_repair.py');repair_new=functions(FROZEN/'surface_guide_repair.py')
for name in repair_old.keys()-{'_assess'}:
    assert ast.dump(repair_old[name])==ast.dump(repair_new[name]),name
for name in ('surface_boundary_repair.py','surface_guide_refine.py','quad_quality.py','surface_distance.py','surface_intersections.py','scripts/quadriflow_mesh.py'):
    assert (OWNED/name).read_bytes()==(FROZEN/name).read_bytes(),name
report=dict(complete=True,passed=True,helperFunctions=sorted(checked),
    ownedSourceHashes={name:sha(OWNED/name) for name in ('curved_quad.py','surface_guide_repair.py','surface_guide_refine.py','surface_boundary_repair.py')},
    exercisedSourceHashes={name:sha(FROZEN/name) for name in ('curved_quad.py','surface_guide_repair.py','surface_guide_refine.py','surface_boundary_repair.py')},
    scope='All pre-existing CQ numerical helpers are AST-identical. Construction differs only in optional guided dispatch and empty guide checks/diagnostics; those branches have no work for these unguided inputs. Owned and exercised boundary/refinement modules and complete geometric gate modules are byte-identical. Separate scoped acceptance verification covers the repair assessment helper. Shared guide policy is excluded from the owned candidate, not silently treated as unchanged for nonempty inputs.')
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,identicalNumericalHelpers=len(checked))))
