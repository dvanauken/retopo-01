"""Audit an exported feature result using the reference surface/contact paths."""
from pathlib import Path
import argparse,hashlib,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj
from surface_intersections import measure,measure_reference
from source_features import measure as features
import curved_quad as cq

ap=argparse.ArgumentParser();ap.add_argument('--job',type=Path,required=True);args=ap.parse_args()
job=args.job.resolve();start=time.monotonic()
meta=json.loads((job/'surface-solver.json').read_text())
curves=[np.asarray(c) for c in json.loads((job/'curves.json').read_text())['curves']]
source=job/'source.obj' if (job/'source.obj').exists() else ROOT/'assets/models/toilet.obj'
v,f=read_obj(source);p,q=read_obj(job/'output.obj');q=np.asarray(q);target=meta['target']
edges={tuple(e) for e in cq._edges(q)};paths=meta['guidePaths']
assert len(paths)==len(curves)
for path in paths:
    ids=path['vertices'];interior=ids[:-1] if path['closed'] else ids
    assert len(set(interior))==len(interior),'A guide path doubles back'
    assert not path['closed'] or ids[0]==ids[-1]
    assert all(tuple(sorted((a,b))) in edges for a,b in zip(ids[:-1],ids[1:]))
fast=measure(p,q,both_quad_diagonals=True)
reference=measure_reference(p,q,both_quad_diagonals=True)
for key in ('passed','nonAdjacentIntersectingFacePairs','adjacentIntersectingFacePairs'):assert fast[key]==reference[key],key
print('Reference contacts checked',reference['passed'],flush=True)
surface=cq.validate_surface(v,np.asarray(f),p,q,target)
quality=cq.quad_quality(p,q,target);feature=features(v,f,p,q,target);fit=cq._guide_fit(p,paths,curves)
passed=quality['passed'] and feature['passed'] and surface['passed'] and reference['passed'] and cq.guides_pass(fit,surface['sampledSurfaceTolerance']*2)
report=dict(passed=passed,sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),outputSha256=hashlib.sha256((job/'output.obj').read_bytes()).hexdigest(),quality=quality,features=feature,surface=surface,referenceContacts=reference,guideFit=fit,seconds=time.monotonic()-start,scope='Re-read OBJ, original Python contact predicates and reference nearest-triangle surface bounds; actual connected guide edges. No fitting or substituted result.')
(job/'reference-export-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('EXPORT AUDIT',passed,'seconds',report['seconds'],flush=True)
assert passed
