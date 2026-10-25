"""Isolated fitting-objective changes on retained genuine toilet layouts.

Acceptance modules and production dispatch remain unchanged. Detached source
snapshots make the changed residual constants and joint settings reviewable.
"""
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
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
import surface_guide_refine as original_fitter
import surface_guide_repair as repair
from retopo import read_obj, write_obj

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--cases', nargs='+', choices=['coarse-150', 'coarse-600', 'short-perturbed', 'short-1799'], required=True)
parser.add_argument('--edge-ratio-aim', type=float, default=3.5)
parser.add_argument('--distance-weight', type=float, default=32.)
parser.add_argument('--tail-weight', type=float, default=80.)
parser.add_argument('--layout', type=Path)
args = parser.parse_args()
if args.layout and len(args.cases) != 1:
    raise ValueError('A layout override requires one explicit case')
if not args.label.replace('-', '').isalnum() or not 1 < args.edge_ratio_aim <= 3.5 or not 0 < args.distance_weight <= 256 or not 0 <= args.tail_weight <= 160:
    raise ValueError('Invalid experiment controls')
OUT = ROOT / 'tests/toilet-objective-controls' / args.label
OUT.mkdir(parents=True, exist_ok=False)
(OUT / 'executed-probe.py').write_bytes(Path(__file__).read_bytes())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
files = ['surface_guide_refine.py', 'surface_guide_repair.py', 'surface_guide_joint.py', 'curved_quad.py',
         'surface_distance.py', 'surface_intersections.py', 'quad_quality.py', 'assets/models/toilet.obj',
         'tests/probe_toilet_objective_controls.py']
hashes = {path: sha(ROOT / path) for path in files}


def detached(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


definition = (ROOT / 'surface_guide_refine.py').read_text()
if 'np.maximum(ratio - 3.5, 0) * 10' in definition:
    definition = definition.replace('np.maximum(ratio - 3.5, 0) * 10', f'np.maximum(ratio - {args.edge_ratio_aim!r}, 0) * 10')
else:
    assert definition.count('edge_ratio_aim=3.5') == 1
    definition = definition.replace('edge_ratio_aim=3.5', f'edge_ratio_aim={args.edge_ratio_aim!r}')
if definition.count('/ spacing * 32 * sample_weights[:, None]') == 2:
    definition = definition.replace('/ spacing * 32 * sample_weights[:, None]', f'/ spacing * {args.distance_weight!r} * sample_weights[:, None]')
else:
    assert definition.count('guide_distance_weight=32.') == 1
    assert definition.count('/ spacing * guide_distance_weight * sample_weights[:, None]') == 2
    definition = definition.replace('guide_distance_weight=32.', f'guide_distance_weight={args.distance_weight!r}')
fitter_file = OUT / 'executed-fitter.py'
fitter_file.write_text(definition, newline='\n')
fitter = detached(fitter_file, 'objective_experiment_fitter')
definition = (ROOT / 'surface_guide_joint.py').read_text()
if definition.count('tangent_tail_weight=80.') == 1:
    assert definition.count('tangentTailWeight=80.') == 1
    definition = definition.replace('tangent_tail_weight=80.', f'tangent_tail_weight={args.tail_weight!r}')
    definition = definition.replace('tangentTailWeight=80.', f'tangentTailWeight={args.tail_weight!r}')
else:
    selection = 'tail_weight, distance_weight = (80., 32.) if guide_repair else (0., 64.)'
    assert definition.count(selection) == 1
    definition = definition.replace(selection, f'tail_weight, distance_weight = {args.tail_weight!r}, {args.distance_weight!r}')
joint_file = OUT / 'executed-joint.py'
joint_file.write_text(definition, newline='\n')
joint = detached(joint_file, 'objective_experiment_joint')
joint.fitter = fitter
repair.fitter = fitter
vertices, triangles = read_obj(ROOT / 'assets/models/toilet.obj')
source = trimesh.Trimesh(vertices, triangles, process=False)
cases, errors = [], []
started = time.monotonic()


def save(complete):
    unchanged = all(sha(ROOT / path) == digest for path, digest in hashes.items())
    (OUT / 'result.json').write_text(json.dumps(dict(
        complete=complete, generationPassed=complete and not errors and all(c['state'] == 'complete' for c in cases),
        productionResult=False, cases=cases, errors=errors, sourceHashes=hashes, implementationUnchanged=unchanged,
        detachedModules={path.name: sha(path) for path in (fitter_file, joint_file)},
        controls=dict(edgeRatioAim=args.edge_ratio_aim, guideDistanceWeight=args.distance_weight, tangentTailWeight=args.tail_weight),
        elapsedSeconds=time.monotonic() - started,
        scope='Isolated real numerical fitting on retained genuine source layouts. Coarse cases use changed objective for global/local fitting; perturbed case reproduces five unchanged global passes before modified joint fitting. Original shape/topology/guide/contact/whole-surface acceptance is mandatory. Accepted experimental exports require separate independent audits; no production dispatch change.'
    ), indent=2) + '\n', newline='\n')


try:
    for name in args.cases:
        target = 1800 if name == 'short-perturbed' else int(name.split('-')[1])
        layout = (ROOT / 'runs/5dfcee62ddbd4af587c799220909463e/quadri-layout-2.json' if name == 'short-perturbed' else
                  ROOT / f'tests/toilet-unguided-fallback/coarse-seed2/unguided-{target}/quadri-layout-2.json')
        if name == 'short-1799':
            layout = ROOT / 'runs/664ee51b30de4125baacfc8b7708bfc4/quadri-layout-2.json'
        if args.layout:
            layout = args.layout.resolve()
        curves_file = ROOT / 'tests/toilet-paired-variants/joint-integrated/short-small-perturbation/curves.json'
        if name == 'short-1799':
            curves_file = ROOT / 'tests/toilet-paired-variants/joint-integrated/short-1799/curves.json'
        curves = json.loads(curves_file.read_text())['curves'] if name.startswith('short-') else []
        raw = json.loads(layout.read_text())
        positions, faces = np.asarray(raw['vertices']), np.asarray(raw['faces'])
        edges = cq._edges(faces)
        guides = original_fitter.prepare(positions, edges, curves, np.sqrt(source.area / target))
        folder = OUT / name
        folder.mkdir()
        (folder / 'layout.json').write_bytes(layout.read_bytes())
        (folder / 'settings.json').write_text(json.dumps(dict(meshId='toilet', target=target)))
        (folder / 'curves.json').write_text(json.dumps(dict(coordinateFrame='source', curves=curves)))
        begin = time.monotonic()
        case = dict(name=name, target=target, job=None, state='running', producerKind='isolated-objective-controls',
                    layoutSource=str(layout.relative_to(ROOT)), layoutSha256=sha(layout), attempts=[],
                    unusedLayoutVertices=len(positions) - len(np.unique(faces)))
        cases.append(case)

        def record(assessment, **details):
            case['attempts'].append(dict(assessment, **details))
            print(name, details.get('phase'), 'qualified', assessment['qualified'],
                  'shape', assessment['quality']['passed'], 'contacts', assessment['intersections']['passed'],
                  'score', assessment.get('violationScore'), 'surface', assessment['surface']['passed'], flush=True)
            save(False)

        for iteration in range(5):
            active_fitter = original_fitter if name == 'short-perturbed' else fitter
            positions, refinement = active_fitter.refine(source, positions, faces, edges, guides, target)
            (folder / f'global-{iteration}.json').write_text(json.dumps(dict(vertices=positions.tolist(), faces=faces.tolist())))
            current = repair._assess(source, positions, faces, guides, target)
            record(current, phase='global', iteration=iteration, refinement=refinement)
            if current['qualified']:
                break
        if name == 'short-perturbed':
            old = json.loads((ROOT / 'tests/toilet-paired-variants/joint-integrated/short-small-perturbation/sampled-guide-history.json').read_text())['attempts']
            expected = next(a for a in old if a.get('globalIteration') == 4)
            # JSON turns histogram integer keys into strings; compare the same
            # serialized representation while keeping every numeric value exact.
            assert json.loads(json.dumps(current['guideFit'])) == expected['guideFit'], 'Unchanged initial fitting must reproduce the captured guide metrics'
            case['initialGuideMetricsExactlyReproduced'] = True
        if curves and not current['qualified']:
            positions, current = joint.repair(source, positions, faces, edges, guides, target, job=folder, record=record)
        elif not curves and current['eligibleForRepair'] and not current['qualified']:
            positions, current = repair._repair(source, positions, faces, edges, guides, target, current, record, folder,
                                                edge_ratio_aim=args.edge_ratio_aim)
        (folder / 'final-candidate.json').write_text(json.dumps(dict(vertices=positions.tolist(), faces=faces.tolist())))
        case.update(state='complete' if current['qualified'] else 'failed', elapsedSeconds=time.monotonic() - begin)
        if current['qualified']:
            write_obj(folder / 'output.obj', positions, faces.tolist())
            case.update(faces=len(faces), outputSha256=sha(folder / 'output.obj'))
            (folder / 'mesh.json').write_text(json.dumps(dict(vertices=positions.tolist(), faces=faces.tolist(), guidePaths=current['guideFit'])))
            (folder / 'report.json').write_text(json.dumps(dict(producerKind=case['producerKind'], outputSha256=case['outputSha256'],
                sourceSha256=hashes['assets/models/toilet.obj'], assessment=current)))
        print(name, case['state'], round(case['elapsedSeconds'], 1), flush=True)
        save(False)
except Exception:
    if cases and cases[-1]['state'] == 'running':
        cases[-1]['state'] = 'probe-error'
    errors.append(traceback.format_exc())
    print(errors[-1], flush=True)
finally:
    save(True)
raise SystemExit(1 if errors or any(c['state'] != 'complete' for c in cases) else 0)
