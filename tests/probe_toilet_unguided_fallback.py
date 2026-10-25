"""Try the source-surface fallback on fresh coarse layouts without guides.

Production currently invokes this fallback only for guided failures. This probe
tests the same explicit geometry function without changing that dispatch rule.
"""
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'): os.environ[key] = '1'
import argparse, hashlib, json, sys, time, traceback
from pathlib import Path
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'engine/targets/zbrush/clone'), str(ROOT / 'engine/targets/zbrush/experiments/python')]
import curved_quad as cq
import surface_guide_repair as repair
from retopo import read_obj, write_obj
from process_ownership import protect_service_tree

parser = argparse.ArgumentParser()
parser.add_argument('--label', required=True)
parser.add_argument('--targets', nargs='+', type=int, default=[150, 600])
args = parser.parse_args()
if not args.label.replace('-', '').isalnum() or any(t < 150 or t > 1800 for t in args.targets): raise ValueError('Invalid label or supported target')
protect_service_tree()
OUT = ROOT / 'tests/toilet-unguided-fallback' / args.label
OUT.mkdir(parents=True, exist_ok=False)
(OUT / 'executed-probe.py').write_bytes(Path(__file__).read_bytes())
files = ['curved_quad.py', 'surface_guide_refine.py', 'surface_guide_repair.py', 'surface_distance.py', 'surface_intersections.py',
         'quad_quality.py', 'assets/models/toilet.obj', 'scripts/quadriflow_mesh.py', 'tests/probe_toilet_unguided_fallback.py']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
hashes = {file: sha(ROOT / file) for file in files}
vertices, triangles = read_obj(ROOT / 'assets/models/toilet.obj')
source = trimesh.Trimesh(vertices, triangles, process=False)
assert source.is_watertight and source.is_winding_consistent and np.all(source.area_faces > 0)
cases, errors = [], []
started = time.monotonic()


def save(complete):
    (OUT / 'result.json').write_text(json.dumps(dict(complete=complete, productionResult=False,
        generationPassed=complete and not errors and all(c['state'] == 'complete' for c in cases), cases=cases, errors=errors,
        sourceHashes=hashes, implementationUnchanged=all(sha(ROOT / p) == h for p, h in hashes.items()),
        elapsedSeconds=time.monotonic() - started,
        scope='Original toilet source, fresh seed2 Blender layout at each requested target, and the actual explicit sampled/local-surface fallback with no guides. Production dispatch is unchanged. Rejected candidates remain unqualified; every accepted export still needs separate independent geometry audits.'), indent=2) + '\n', newline='\n')


try:
    blender = cq.find_blender()
    for target in args.targets:
        name = 'unguided-' + str(target)
        folder = OUT / name
        folder.mkdir()
        source_file = folder / 'source.json'
        source_file.write_text(json.dumps(dict(vertices=source.vertices.tolist(), faces=source.faces.tolist())))
        (folder / 'settings.json').write_text(json.dumps(dict(meshId='toilet', target=target)))
        (folder / 'curves.json').write_text(json.dumps(dict(coordinateFrame='source', curves=[])))
        begin = time.monotonic()
        history = []
        result = repair.construct(source, [], target=target, job=folder, blender=blender, input_path=source_file, history=history)
        case = dict(name=name, target=target, state='complete' if result is not None else 'failed', job=None,
                    producerKind='isolated-unguided-sampled-fallback', elapsedSeconds=time.monotonic()-begin, attempts=len(history))
        if result is not None:
            p, faces, metadata = result
            write_obj(folder / 'output.obj', p, faces)
            (folder / 'mesh.json').write_text(json.dumps(dict(vertices=p.tolist(), faces=faces, guidePaths=metadata['guidePaths'])))
            case.update(outputSha256=sha(folder / 'output.obj'), faces=len(faces))
            (folder / 'report.json').write_text(json.dumps(dict(producerKind=case['producerKind'], outputSha256=case['outputSha256'],
                sourceSha256=hashes['assets/models/toilet.obj'], metadata=metadata)))
        cases.append(case)
        print(name, case['state'], 'seconds', round(case['elapsedSeconds'], 1), flush=True)
        save(False)
except Exception:
    errors.append(traceback.format_exc())
    print(errors[-1], flush=True)
finally:
    save(True)
raise SystemExit(0 if not errors and all(c['state'] == 'complete' for c in cases) else 1)
