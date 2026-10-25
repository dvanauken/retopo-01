"""Verify unchanged fitting/acceptance bodies and bounded retry controls."""
import ast
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
OUT = ROOT / 'tests/surface-layout-retries/nearby-layouts'
OUT.mkdir(parents=True, exist_ok=False)
baseline_revision = 'ce8e0f233eadee16d644e81bc0bb3f96e4cfb70f'
baseline = subprocess.run(['git', '-c', 'safe.directory=C:/dbva/code/retopo-1', 'show',
                           baseline_revision + ':surface_guide_repair.py'], cwd=ROOT, check=True, capture_output=True).stdout
current = (ROOT / 'surface_guide_repair.py').read_bytes()
(OUT / 'baseline-repair.py').write_bytes(baseline)
(OUT / 'executed-repair.py').write_bytes(current)
(OUT / 'executed-test.py').write_bytes(Path(__file__).read_bytes())
old_functions = {n.name: n for n in ast.parse(baseline).body if isinstance(n, ast.FunctionDef)}
new_functions = {n.name: n for n in ast.parse(current).body if isinstance(n, ast.FunctionDef)}
checks = []
for name in ('_assess', '_repair'):
    assert ast.dump(old_functions[name]) == ast.dump(new_functions[name]), name
    checks.append(dict(name=name + ' is AST-identical to the previously qualified implementation', passed=True))

old = old_functions['construct']
new = copy.deepcopy(new_functions['_construct_layout'])
new.name = old.name
index = next(i for i, arg in enumerate(new.args.kwonlyargs) if arg.arg == 'layout_target')
new.args.kwonlyargs.pop(index)
new.args.kw_defaults.pop(index)
new.body[0] = copy.deepcopy(old.body[0])  # Only the explanatory docstring differs.
for node in ast.walk(new):
    if isinstance(node, ast.Call):
        node.keywords = [k for k in node.keywords if k.arg not in ('layoutTarget', 'targetFaces')]
        if isinstance(node.func, ast.Name) and node.func.id == 'str' and len(node.args) == 1:
            if isinstance(node.args[0], ast.Name) and node.args[0].id == 'layout_target':
                node.args[0].id = 'target'
    if isinstance(node, ast.Constant) and node.value == 'Bounded nearby layout search and refinement; general crease/attribute transfer is not implemented.':
        node.value = 'One additional layout and bounded refinement; general crease/attribute transfer is not implemented.'
assert ast.dump(old) == ast.dump(new)
checks.append(dict(name='Each layout keeps the prior numerical sequence and gates; changes are limited to layout count and explanatory metadata', passed=True))

suite = unittest.defaultTestLoader.loadTestsFromNames(['test_surface_guide_repair', 'test_surface_guide_joint', 'test_surface_layout_retries'])
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
(OUT / 'unit-tests.log').write_text(stream.getvalue())
checks.append(dict(name='Acceptance and retry invariant controls', passed=result.wasSuccessful(), tests=result.testsRun))
files = ['surface_guide_repair.py', 'surface_guide_refine.py', 'surface_guide_joint.py', 'surface_distance.py',
         'surface_intersections.py', 'quad_quality.py', 'tests/test_surface_layout_retries.py', 'tests/verify_surface_layout_retries.py']
sha = lambda content: hashlib.sha256(content).hexdigest()
report = dict(complete=True, passed=all(c['passed'] for c in checks), checks=checks,
              baselineRevision=baseline_revision, baselineSha256=sha(baseline),
              sourceHashes={name: sha((ROOT / name).read_bytes()) for name in files},
              scope='AST comparison of prior fitting/local-repair/acceptance bodies plus18 executable acceptance and retry controls. The full supported integer target range has at most4 unique nearby layouts. Actual source-to-worker generations and independent exported-geometry checks are separate evidence.')
(OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=report['passed'], tests=result.testsRun, checks=len(checks))))
raise SystemExit(0 if report['passed'] else 1)
