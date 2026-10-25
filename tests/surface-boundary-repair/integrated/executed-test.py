"""Verify unchanged defaults, exact experimental objective and bridge invariants."""
import ast
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
OUT=ROOT/'tests/surface-boundary-repair/integrated'
OUT.mkdir(parents=True,exist_ok=False)
baseline_revision='425b1083bf8a9642bd4cf89c8a69c4563d50e7a3'
git=['git','-c','safe.directory=C:/dbva/code/retopo-1']
baseline=subprocess.run([*git,'show',baseline_revision+':surface_guide_refine.py'],cwd=ROOT,check=True,capture_output=True).stdout
current=(ROOT/'surface_guide_refine.py').read_bytes()
(OUT/'baseline-fitter.py').write_bytes(baseline)
(OUT/'executed-fitter.py').write_bytes(current)
(OUT/'executed-repair.py').write_bytes((ROOT/'surface_guide_repair.py').read_bytes())
(OUT/'executed-boundary.py').write_bytes((ROOT/'surface_boundary_repair.py').read_bytes())
(OUT/'executed-test.py').write_bytes(Path(__file__).read_bytes())

def specialized(content,value):
    tree=ast.parse(content)
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='refine')
    index=next(i for i,arg in enumerate(fn.args.kwonlyargs) if arg.arg=='edge_ratio_aim')
    assert fn.args.kw_defaults[index].value==3.5
    fn.args.kwonlyargs.pop(index);fn.args.kw_defaults.pop(index)
    class Replace(ast.NodeTransformer):
        def visit_Name(self,node):
            return ast.Constant(value=value) if node.id=='edge_ratio_aim' else node
    return ast.dump(Replace().visit(tree))

assert specialized(current,3.5)==ast.dump(ast.parse(baseline))
experiment=(ROOT/'tests/toilet-boundary-bridge/coarse150-seed4/executed-fitter.py').read_bytes()
assert specialized(current,3.4)==ast.dump(ast.parse(experiment))
old_repair=subprocess.run([*git,'show',baseline_revision+':surface_guide_repair.py'],cwd=ROOT,check=True,capture_output=True).stdout
old={n.name:n for n in ast.parse(old_repair).body if isinstance(n,ast.FunctionDef)}
new={n.name:n for n in ast.parse((ROOT/'surface_guide_repair.py').read_bytes()).body if isinstance(n,ast.FunctionDef)}
for name in ('_assess','_construct_layout','layout_targets'):
    assert ast.dump(old[name])==ast.dump(new[name]),name
local=copy.deepcopy(new['_repair'])
assert local.args.kwonlyargs[0].arg=='edge_ratio_aim' and local.args.kw_defaults[0].value==3.5
local.args.kwonlyargs=[];local.args.kw_defaults=[]
for node in ast.walk(local):
    if isinstance(node,ast.Call):node.keywords=[k for k in node.keywords if k.arg!='edge_ratio_aim']
assert ast.dump(local)==ast.dump(old['_repair'])

suite=unittest.defaultTestLoader.loadTestsFromNames(['test_surface_guide_repair','test_surface_guide_joint','test_surface_layout_retries','test_surface_boundary_repair'])
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(OUT/'unit-tests.log').write_text(stream.getvalue())
files=['surface_guide_refine.py','surface_guide_repair.py','surface_boundary_repair.py','surface_guide_joint.py',
       'surface_distance.py','surface_intersections.py','quad_quality.py','assets/models/toilet.obj',
       'tests/test_surface_layout_retries.py','tests/test_surface_boundary_repair.py','tests/verify_surface_boundary_integration.py']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=dict(complete=True,passed=result.wasSuccessful(),tests=result.testsRun,
    checks=[dict(name=name,passed=True) for name in ('Default fitting AST unchanged','Explicit3.4objective AST matches independently qualified experiment',
            'Existing assessment/layout/local-repair bodies unchanged except forwarding shape objective')],
    baselineRevision=baseline_revision,sourceHashes={name:sha(ROOT/name) for name in files},
    scope='Exact AST specialization proves prior defaults and the qualified detached3.4objective. Executable acceptance/retry/topology controls include all bounded loop sizes, winding/manifold rejection, Euler preservation and the actual152quad bridge. Fresh-source generation and independent export audits are separate.')
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=report['passed'],tests=result.testsRun,log=stream.getvalue() if not result.wasSuccessful() else None)))
raise SystemExit(0 if report['passed'] else 1)
