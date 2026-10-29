"""Re-read accepted OBJ and check reference contacts plus open-surface gates."""
from pathlib import Path
import argparse, hashlib, json, sys, time
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
import numpy as np
from measure_geometry import read_obj
from source_features import measure as features, use_crease_angle
from surface_intersections import measure, measure_reference
from boundary_geometry import validate as boundary
import curved_quad as cq

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--job',type=Path,required=True);a=ap.parse_args()
    job=a.job.resolve()
    if not job.is_relative_to(ROOT):ap.error('Audit only workspace jobs')
    started=time.monotonic();settings=json.loads((job/'settings.json').read_text(encoding='utf-8'));use_crease_angle(settings['creaseAngle'])
    mesh=json.loads((job/'mesh.json').read_text(encoding='utf-8'));report=json.loads((job/'report.json').read_text(encoding='utf-8'))
    assert report['passed'],'Only accepted outputs are export-audited'
    v,f=read_obj(job/'source.obj');p,q=read_obj(job/'output.obj');f=np.asarray(f,int);q=np.asarray(q,int)
    assert np.array_equal(q,np.asarray(mesh['faces'],int)),'OBJ/JSON faces differ'
    assert np.array_equal(p,np.asarray(mesh['vertices'])),'OBJ/JSON positions differ despite round-trip .17g export'
    target=settings['target'];h=float(np.sqrt(np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1).sum()*.5/target))
    print('REFERENCE CONTACTS',job,flush=True)
    fast=measure(p,q,both_quad_diagonals=True);reference=measure_reference(p,q,both_quad_diagonals=True)
    for key in ('passed','nonAdjacentIntersectingFacePairs','adjacentIntersectingFacePairs'):
        assert fast[key]==reference[key],(key,fast[key],reference[key])
    surface=cq.validate_surface(v,f,p,q,target,accelerated=False,allow_boundary=True)
    quality=cq.quad_quality(p,q,target);feature=features(v,f,p,q,target);rim=boundary(v,f,p,q,.1*h)
    curves=[np.asarray(c) for c in json.loads((job/'curves.json').read_text(encoding='utf-8'))['curves']]
    paths=mesh['guidePaths'];edges={tuple(e) for e in cq._edges(q)}
    for path in paths:
        ids=path['vertices'];assert all(tuple(sorted((u,w))) in edges for u,w in zip(ids,ids[1:])), 'Guide path leaves output edges'
    guide=cq._guide_fit(p,paths,curves,h)
    passed=all(x['passed'] for x in (reference,surface,quality,feature,rim)) and cq.guides_pass(guide,h)
    out=dict(passed=bool(passed),sourceSha256=hashlib.sha256((job/'source.obj').read_bytes()).hexdigest(),
             outputSha256=hashlib.sha256((job/'output.obj').read_bytes()).hexdigest(),quality=quality,features=feature,
             surface=surface,boundary=rim,referenceContacts=reference,guideFit=guide,seconds=time.monotonic()-started,
             validatorHashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['tests/audit_registered_features.py','surface_intersections.py','surface_contacts_fast.py','curved_quad.py','source_features.py','boundary_geometry.py']},
             scope='Accepted OBJ re-read; independent original Python contact predicates vs fast path; reference surface search; actual connected guide edges. No fitting.')
    (job/'reference-export-audit.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('EXPORT AUDIT',passed,'seconds',out['seconds'],flush=True)
    return 0 if passed else 1

if __name__=='__main__':raise SystemExit(main())


