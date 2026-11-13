"""Can the strict-count mode follow the corners? Run its whole search with the corner check enforced.

Usage: python strict-search.py OUT_FOLDER [--target 200] [--part skp-6]
The solver is the shipped one (open_surface.construct, extra_faces=False). Only the acceptance is
changed, in this process alone: a candidate that passes every shipped check is accepted only if its
corner zones also meet the corner limits (corner_zones). Every candidate that reaches the checks is
recorded with its corner numbers, so the best the strict count can do is on record whether or not
one is accepted. The job folder is written under OUT_FOLDER, never under runs/.
"""
import argparse
import json
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
for extra in (ROOT, ROOT / 'engine/targets/zbrush/experiments/python', ROOT / 'engine/targets/zbrush/clone'):
    sys.path.insert(0, str(extra))
import numpy as np
from measure_geometry import read_obj
from source_features import use_crease_angle, detect, spacing
from guided_layout import obj
import corner_zones
import open_surface

parser = argparse.ArgumentParser()
parser.add_argument('out', type=Path)
parser.add_argument('--target', type=int, default=200)
parser.add_argument('--source', type=Path, default=ROOT / 'tests/fixtures/crease_rows/island6-source.obj')
parser.add_argument('--curves', type=Path, default=ROOT / 'tests/fixtures/island6-guide-483afe83.json')
arguments = parser.parse_args()
out = arguments.out.resolve()
job = out / 'job'
job.mkdir(parents=True, exist_ok=False)
source, triangles = read_obj(arguments.source)
source, triangles = np.asarray(source, float), np.asarray(triangles, int)
curves = json.loads(arguments.curves.read_text())['curves']
use_crease_angle(30.)
h = spacing(source, triangles, arguments.target)
edges, _ = detect(source, triangles, h, target=arguments.target)
zone = source[:, 1] > .05
shipped = open_surface.measure_features
candidates = []


def enforced(src, tris, p, q, target, **keywords):
    """The shipped crease check, failed as well when a corner zone is over its limit."""
    report = shipped(src, tris, p, q, target, **keywords)
    corners = corner_zones.measure(src, tris, edges, p, q, h)
    fixed = corner_zones.measure_zone(src, p, q, h, zone)
    candidates.append(dict(faces=len(q), creaseCheckPassed=bool(report['passed']), creaseFailures=list(report['failures']), cornersPassed=bool(corners['passed']),
                           cornerFailures=corners['failures'], worstP95InFaces=corners['worstP95InFaces'], worstMaxInFaces=corners['worstMaxInFaces'],
                           fixedZoneP95InFaces=fixed['p95InFaces'], fixedZoneMaxInFaces=fixed['maxInFaces']))
    if not corners['passed']:
        report = dict(report, passed=False, failures=report['failures'] + ['cornerZones'])
    return report


open_surface.measure_features = enforced
started = time.monotonic()
result = dict(target=arguments.target, source=str(arguments.source), curves=str(arguments.curves), limits=dict(p95InFaces=corner_zones.ZONE_P95_FACES, maxInFaces=corner_zones.ZONE_MAX_FACES),
              scope='Shipped strict-count solver; acceptance additionally requires the corner zones, in this process only.')
try:
    p, q, meta = open_surface.construct(source, triangles, curves, target=arguments.target, job=job, extra_faces=False)
    obj(out / 'accepted.obj', p, q)
    result.update(accepted=True, faces=len(q), layoutSeed=meta.get('creaseRows', {}).get('layoutSeed'), layoutStyle=meta.get('layoutStyle'))
except open_surface.OpenSurfaceRejected as error:
    result.update(accepted=False, message=str(error))
history = json.loads((job / 'open-surface/history.json').read_text())
result.update(seconds=time.monotonic() - started, layoutsTried=len({row.get('attempt') for row in history}),
              candidatesChecked=len(candidates), candidates=candidates,
              candidatesPassingShippedChecks=sum(1 for row in history if all(k in row for k in ('feature', 'contacts', 'surface')) and row['contacts']['passed'] and row['surface']['passed'] and row.get('guidesPassed') and row['feature']['failures'] in ([], ['cornerZones'])))
(out / 'strict-search.json').write_text(json.dumps(result, indent=1))
print(json.dumps({k: v for k, v in result.items() if k != 'candidates'}, indent=1))
for row in candidates:
    print('candidate', row['faces'], 'faces; crease check', row['creaseCheckPassed'], '; corners worst P95 %.3f h, worst max %.3f h' % (row['worstP95InFaces'], row['worstMaxInFaces']), '; fixed zone %.3f / %.3f h' % (row['fixedZoneP95InFaces'], row['fixedZoneMaxInFaces']))
