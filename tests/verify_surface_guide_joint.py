"""Numerical parity and acceptance regression for joint guide/surface repair."""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'),
               str(ROOT / 'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
import surface_guide_joint as joint
from measure_geometry import read_obj

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--module', type=Path, default=ROOT / 'surface_guide_refine.py')
parser.add_argument('--joint-module', type=Path)
parser.add_argument('--case', choices=['long', 'perturbed'], default='long')
args = parser.parse_args()
if not args.label.replace('-', '').isalnum():
    raise ValueError('Use a plain label')
OUT = ROOT / 'tests/surface-guide-joint' / args.label
OUT.mkdir(parents=True, exist_ok=False)
module_path = args.module.resolve()
spec = importlib.util.spec_from_file_location('tested_joint_fitter', module_path)
fitter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fitter
spec.loader.exec_module(fitter)
if args.joint_module:
    joint_spec = importlib.util.spec_from_file_location('tested_joint_driver', args.joint_module.resolve())
    joint = importlib.util.module_from_spec(joint_spec)
    sys.modules[joint_spec.name] = joint
    joint_spec.loader.exec_module(joint)
joint.fitter = fitter
(OUT / 'executed-fitter.py').write_bytes(module_path.read_bytes())
(OUT / 'executed-joint.py').write_bytes(Path(joint.__file__).read_bytes())
(OUT / 'executed-test.py').write_bytes(Path(__file__).read_bytes())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
hashes = {str(p): sha(p) for p in (module_path, Path(joint.__file__), Path(cq.__file__),
                                  ROOT / 'surface_distance.py', ROOT / 'surface_intersections.py',
                                  ROOT / 'quad_quality.py', ROOT / 'assets/models/toilet.obj')}
checks, records, errors = [], [], []
started = time.monotonic()


def check(value, name, **details):
    checks.append(dict(passed=bool(value), name=name, **details))
    print(('PASS ' if value else 'FAIL ') + name, flush=True)


def save(complete):
    unchanged = all(sha(Path(p)) == h for p, h in hashes.items())
    (OUT / 'result.json').write_text(json.dumps(dict(
        complete=complete, passed=complete and not errors and unchanged and all(c['passed'] for c in checks),
        checks=checks, errors=errors, assessments=records, sourceHashes=hashes, implementationUnchanged=unchanged,
        elapsedSeconds=time.monotonic() - started, productionDispatchTest=False, case=args.case,
        scope='Real numerical calls and full acceptance gates, compared exactly with retained numerical experiments whose exports passed independent audits. Detached modules when supplied; fresh-source generation and service dispatch are tested separately.'
    ), indent=2) + '\n', newline='\n')


try:
    sv, sf = read_obj(ROOT / 'assets/models/toilet.obj')
    source = trimesh.Trimesh(sv, sf, process=False)
    base = ROOT / ('tests/toilet-constraint-memory/fresh-long-direct-tail80-repair' if args.case == 'long' else
                   'tests/toilet-objective-controls/perturb-distance64-tail0-serialized/short-perturbed')
    raw = json.loads((base / 'layout.json').read_text())
    initial = ROOT / 'tests/toilet-sampled-paths/fresh-long-direct-tail80-fit/two-guides-long-1800-4.json' if args.case == 'long' else base / 'global-4.json'
    positions = np.asarray(json.loads(initial.read_text())['vertices'])
    faces = np.asarray(raw['faces'])
    edges = cq._edges(faces)
    curve_path = ROOT / 'tests/toilet-stress/two-guides-long-1800/curves.json' if args.case == 'long' else base / 'curves.json'
    curves = json.loads(curve_path.read_text())['curves']
    guides = fitter.prepare(np.asarray(raw['vertices']), edges, curves, np.sqrt(source.area / 1800))
    frozen_positions, frozen_faces = positions.copy(), faces.copy()
    original_refine = fitter.refine
    calls = []

    def measured_refine(*positional, **kwargs):
        before = positional[1].copy()
        result, metadata = original_refine(*positional, **kwargs)
        if args.case == 'long':
            expected_path = base / f'two-guides-long-1800-{1 if not calls else 2}.json'
            expected = np.asarray(json.loads(expected_path.read_text())['vertices'])
            check(np.array_equal(result, expected), f'Joint full proposal {len(calls)} exactly matches audited experiment',
                  maximumCoordinateDifference=float(np.max(np.abs(result - expected))),
                  referenceFile=str(expected_path.relative_to(ROOT)), referenceSha256=sha(expected_path))
        if args.joint_module or args.case == 'perturbed':
            expected_weights = (80., 32.) if args.case == 'long' else (0., 64.)
            check((kwargs['tangent_tail_weight'], kwargs['guide_distance_weight']) == expected_weights,
                  f'Joint pass {len(calls)} uses weights for its actual failing constraints')
        check(np.array_equal(before, positional[1]), f'Joint pass {len(calls)} leaves input positions unchanged')
        outside = np.array(sorted(set(range(len(before))) - set(kwargs['patch_vertices'])), dtype=int)
        check(np.array_equal(before[outside], result[outside]), f'Joint pass {len(calls)} keeps vertices outside its patch fixed')
        calls.append(metadata)
        return result, metadata

    fitter.refine = measured_refine

    def record(assessment, **details):
        records.append(dict(assessment, **details))
        print('assessment', len(records) - 1, 'qualified', assessment['qualified'],
              'angles', [p['p95TangentAngleDegrees'] for p in assessment['guideFit']], flush=True)
        save(False)

    final, assessment = joint.repair(source, positions, faces, edges, guides, 1800, job=OUT, record=record)
    expected_path = base / ('two-guides-long-1800-3.json' if args.case == 'long' else 'final-candidate.json')
    expected = json.loads(expected_path.read_text())
    check(np.array_equal(final, expected['vertices']) and np.array_equal(faces, expected['faces']),
          'Final mesh exactly matches independently audited experimental export', referenceSha256=sha(expected_path))
    check(assessment['qualified'] and assessment['surface']['passed'] and assessment['quality']['passed']
          and assessment['intersections']['passed'], 'Joint driver requires every geometry acceptance gate')
    check(all(assessment['gatePassed'].values()), 'Every guide and directional full-surface bound passes')
    check(len(calls) == (2 if args.case == 'long' else 3) and len(records) == 4,
          'Same numerical passes and three assessed proposals as the independently audited experiment')
    check(np.array_equal(positions, frozen_positions) and np.array_equal(faces, frozen_faces),
          'Driver preserves original input positions and face connectivity')
    (OUT / 'final.json').write_text(json.dumps(dict(vertices=final.tolist(), faces=faces.tolist())))
except Exception:
    errors.append(traceback.format_exc())
    print(errors[-1], flush=True)
finally:
    save(True)
raise SystemExit(1 if errors or any(not c['passed'] for c in checks) else 0)
