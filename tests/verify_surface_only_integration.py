"""Link applied adaptive fitting bytes to numerical and acceptance evidence."""
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
OUT = ROOT / 'tests/surface-guide-joint/surface-only-integrated'
OUT.mkdir(parents=True, exist_ok=False)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
checks = []
for relative in (
    'tests/surface-guide-joint/surface-only-long-control',
    'tests/surface-guide-joint/surface-only-perturbed',
    'tests/surface-guide-refine/surface-only-defaults',
):
    folder = ROOT / relative
    report = json.loads((folder / 'result.json').read_text())
    assert report['complete'] and report['passed']
    assert (folder / 'executed-fitter.py').read_bytes() == (ROOT / 'surface_guide_refine.py').read_bytes()
    if (folder / 'executed-joint.py').exists():
        assert (folder / 'executed-joint.py').read_bytes() == (ROOT / 'surface_guide_joint.py').read_bytes()
    checks.append(dict(name=relative, passed=True, reportSha256=sha(folder / 'result.json'),
                       numericalChecks=len(report['checks'])))

suite = unittest.defaultTestLoader.loadTestsFromNames(['test_surface_guide_repair', 'test_surface_guide_joint'])
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
(OUT / 'unit-tests.log').write_text(stream.getvalue(), encoding='utf-8')
checks.append(dict(name='Acceptance controls on applied modules', passed=result.wasSuccessful(), tests=result.testsRun))
files = ['surface_guide_refine.py', 'surface_guide_joint.py', 'surface_guide_repair.py',
         'surface_distance.py', 'surface_intersections.py', 'quad_quality.py', 'assets/models/toilet.obj',
         'tests/test_surface_guide_repair.py', 'tests/test_surface_guide_joint.py',
         'tests/verify_surface_only_integration.py']
report = dict(complete=True, passed=all(c['passed'] for c in checks), checks=checks, tests=result.testsRun,
              sourceHashes={name: sha(ROOT / name) for name in files},
              scope='Applied source is byte-identical to the tested adaptive modules. Separate numerical reports reproduce prior long/bowl/short coordinates and the qualified perturbed candidate; acceptance controls run on applied modules. Actual service and browser coverage are recorded separately.')
(OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
raise SystemExit(0 if report['passed'] else 1)
