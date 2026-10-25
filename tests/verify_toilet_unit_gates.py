"""Retain current numerical/lifecycle unit evidence with implementation hashes."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(); parser.add_argument('--label',default='current'); args=parser.parse_args()
out=ROOT/'tests/toilet-unit-gates'/args.label; out.mkdir(parents=True,exist_ok=True)
paths=['server.py','curved_quad.py','surface_distance.py','surface_intersections.py']+[str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'tests').glob('test_*.py')]
hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py')
stream=io.StringIO(); result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(out/'output.txt').write_text(stream.getvalue(),encoding='utf-8')
report=dict(passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),sourceHashes=hashes)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report),flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
