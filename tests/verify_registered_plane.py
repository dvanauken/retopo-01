"""Exercise the complete registered-row pipeline on a generated planar guide."""
import argparse
import hashlib
import os
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from guided_layout import obj,write
from source_features import use_crease_angle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--engine',type=Path,default=ROOT/'engine/guided-quadriflow/development')
    args=parser.parse_args();job=args.out.resolve();engine=args.engine.resolve()
    if not job.is_relative_to(ROOT/'runs'):parser.error('Control output must be in this project runs directory')
    job.mkdir(parents=True,exist_ok=False)
    (job/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    os.environ['RETOPO_FEATURE_LAYOUT']='registered'
    os.environ['RETOPO_REGISTERED_ENGINE']=str(engine)
    os.environ['OMP_NUM_THREADS']='1'
    from open_surface import construct
    import curved_quad as cq
    use_crease_angle(30.)
    paths=list(ROOT.glob('*.py'))+[engine/'quadriflow.exe',engine/'manifest.json']
    def snapshot():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before=snapshot()
    vertices=np.array([[x/8,y/8,0] for y in range(9) for x in range(9)],float)
    triangles=[]
    for y in range(8):
        for x in range(8):
            a=y*9+x;triangles.extend([[a,a+1,a+10],[a,a+10,a+9]])
    triangles=np.asarray(triangles,int);curves=[np.array([[0,.5,0],[1,.5,0]])]
    obj(job/'source.obj',vertices,triangles)
    write(job/'curves.json',dict(coordinateFrame='source',curves=[c.tolist() for c in curves]))
    p,q,meta=construct(vertices,triangles,curves,target=200,job=job)
    obj(job/'output.obj',p,q)
    quality=cq.quad_quality(p,np.asarray(q,int),200)
    after=snapshot()
    result=dict(faces=len(q),target=200,codeBefore=before,codeAfter=after,codeStable=before==after,
                quality=quality,featureRows=meta['featureRows'],candidateSelection=meta['candidateSelection'],
                engine=meta['layoutEngine'],sourceValidation=meta['closedValidation'],
                boundaryValidation=meta['boundaryValidation'],featureValidation=meta['featureValidation'],
                intersectionValidation=meta['intersectionValidation'],guidePaths=meta['guidePaths'])
    result['passed']=bool(result['codeStable'] and quality['passed'] and
        all(meta[k]['passed'] for k in ('featureRows','closedValidation','boundaryValidation','featureValidation','intersectionValidation')))
    write(job/'result.json',result)
    print('PLANAR CONTROL',result['passed'],'faces',len(q),'codeStable',result['codeStable'])
    return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
