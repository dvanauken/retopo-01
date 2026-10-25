"""Fresh nearby layout counts, fitted and accepted at the original target."""
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
from retopo import read_obj, write_obj
from process_ownership import protect_service_tree

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--target', type=int, required=True)
parser.add_argument('--layout-targets', type=int, nargs='+', required=True)
parser.add_argument('--guides', choices=['none', 'short'], default='none')
args = parser.parse_args()
if not args.label.replace('-', '').isalnum() or not 150 <= args.target <= 1800:
    raise ValueError('Invalid label or requested target')
if any(abs(t / args.target - 1) > .15 for t in args.layout_targets):
    raise ValueError('Keep layout-count experiments within fifteen percent of the requested target')
protect_service_tree()
OUT = ROOT / 'tests/toilet-target-neighborhood' / args.label
OUT.mkdir(parents=True, exist_ok=False)
(OUT / 'executed-probe.py').write_bytes(Path(__file__).read_bytes())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
files = ['curved_quad.py', 'surface_guide_refine.py', 'surface_guide_repair.py', 'surface_guide_joint.py',
         'surface_distance.py', 'surface_intersections.py', 'quad_quality.py', 'assets/models/toilet.obj',
         'scripts/quadriflow_mesh.py', 'tests/probe_toilet_target_neighborhood.py']
hashes = {name: sha(ROOT / name) for name in files}
vertices, triangles = read_obj(ROOT / 'assets/models/toilet.obj')
source = trimesh.Trimesh(vertices, triangles, process=False)
curves = [] if args.guides == 'none' else json.loads((ROOT / 'tests/toilet-stress/two-guides-short-1800/curves.json').read_text())['curves']
cases, errors = [], []
started = time.monotonic()

def save(complete):
    report = dict(complete=complete, productionResult=False, cases=cases, errors=errors,
                  generationPassed=complete and not errors and all(c['state'] == 'complete' for c in cases),
                  sourceHashes=hashes, implementationUnchanged=all(sha(ROOT / name) == digest for name, digest in hashes.items()),
                  elapsedSeconds=time.monotonic() - started,
                  scope='Fresh original-source seed2 layouts at nearby generator counts. Detached driver changes only the Blender target argument. Fitting, all acceptance limits and reported requested target use the original target. No production dispatch change; every accepted experimental export requires independent audits.')
    (OUT / 'result.json').write_text(json.dumps(report, indent=2) + '\n')

try:
    blender = cq.find_blender()
    definition = (ROOT / 'surface_guide_repair.py').read_text()
    marker = "str(target), '--seed'"
    explicit_layout = 'def _construct_layout(' in definition
    assert explicit_layout or definition.count(marker) == 1
    for layout_target in args.layout_targets:
        name = f'{args.guides}-{args.target}-layout-{layout_target}'
        folder = OUT / name
        folder.mkdir()
        driver_path = folder / 'executed-driver.py'
        driver_path.write_text(definition if explicit_layout else definition.replace(marker, f"str({layout_target}), '--seed'"))
        spec = importlib.util.spec_from_file_location(f'neighborhood_driver_{layout_target}', driver_path)
        driver = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = driver
        spec.loader.exec_module(driver)
        source_file = folder / 'source.json'
        source_file.write_text(json.dumps(dict(vertices=source.vertices.tolist(), faces=source.faces.tolist())))
        (folder / 'settings.json').write_text(json.dumps(dict(meshId='toilet', target=args.target)))
        (folder / 'curves.json').write_text(json.dumps(dict(coordinateFrame='source', curves=curves)))
        history = []
        case = dict(name=name, target=args.target, layoutTarget=layout_target, state='running', job=None,
                    producerKind='isolated-nearby-layout-count', driverSha256=sha(driver_path))
        cases.append(case)
        save(False)
        begin = time.monotonic()
        constructor = driver._construct_layout if explicit_layout else driver.construct
        options = dict(layout_target=layout_target) if explicit_layout else {}
        result = constructor(source, curves, target=args.target, job=folder, blender=blender,
                             input_path=source_file, history=history, **options)
        case.update(state='complete' if result is not None else 'failed', attempts=len(history),
                    elapsedSeconds=time.monotonic() - begin)
        if result is not None:
            positions, faces, metadata = result
            write_obj(folder / 'output.obj', positions, faces)
            (folder / 'mesh.json').write_text(json.dumps(dict(vertices=positions.tolist(), faces=faces, guidePaths=metadata['guidePaths'])))
            case.update(faces=len(faces), outputSha256=sha(folder / 'output.obj'))
            (folder / 'report.json').write_text(json.dumps(dict(producerKind=case['producerKind'], outputSha256=case['outputSha256'],
                sourceSha256=hashes['assets/models/toilet.obj'], requestedTarget=args.target, layoutTarget=layout_target, metadata=metadata)))
        print(name, case['state'], round(case['elapsedSeconds'], 1), flush=True)
        save(False)
except Exception:
    if cases and cases[-1]['state'] == 'running':
        cases[-1]['state'] = 'probe-error'
    errors.append(traceback.format_exc())
    print(errors[-1], flush=True)
finally:
    save(True)
raise SystemExit(0 if not errors and all(c['state'] == 'complete' for c in cases) else 1)
