from pathlib import Path
import argparse,json,sys,time
import numpy as np
import trimesh
from scipy.spatial import cKDTree
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj
from features import sharp_edges,output_creases
from quad_quality import measure
from surface_intersections import measure as contacts
import curved_quad as cq
from source_features import measure as feature_measure
ap=argparse.ArgumentParser();ap.add_argument('--label',default='bowl-7200');ap.add_argument('--candidate',default='balanced-4');args=ap.parse_args()
folder=ROOT/'runs/feature-layout'/args.label
data=json.loads((folder/f'feature-fit-{args.candidate}.json').read_text());p=np.asarray(data['vertices']);q=np.asarray(data['faces'])
v,f=read_obj(ROOT/'assets/models/toilet.obj');f=np.asarray(f,int)
start=time.perf_counter();result=dict(quality=measure(p,q,7200));print('quality',result['quality']['passed'],flush=True)
result['sourceFeatures']=feature_measure(v,f,p,q,7200);print('source features',result['sourceFeatures'],flush=True)
crease=output_creases(p,q.tolist(),angle_degrees=30)['edges'];e=np.asarray(crease,int)
samples=np.concatenate([np.linspace(v[a],v[b],5) for a,b in sharp_edges(v,f,45)])
a,b=p[e[:,0]],p[e[:,1]];_,near=cKDTree((a+b)*.5).query(samples,k=min(32,len(a)))
aa=a[near];d=b[near]-aa;t=np.clip(((samples[:,None]-aa)*d).sum(2)/np.maximum(1e-20,(d*d).sum(2)),0,1)
distance=np.linalg.norm(samples[:,None]-aa-t[:,:,None]*d,axis=2).min(1)
result['featureCreaseDistance']=dict(edges=len(e),p95=float(np.percentile(distance,95)),max=float(distance.max()))
print('features',result['featureCreaseDistance'],flush=True)
tic=time.perf_counter();result['contacts']=contacts(p,q,both_quad_diagonals=True);print('contacts',time.perf_counter()-tic,result['contacts']['passed'],len(result['contacts']['nonAdjacentIntersectingFacePairs']),len(result['contacts']['adjacentIntersectingFacePairs']),flush=True)
tic=time.perf_counter();result['surface']=cq.validate_surface(v,f,p,q,7200);print('surface',time.perf_counter()-tic,result['surface']['passed'],flush=True)
(folder/f'validation-{args.candidate}.json').write_text(json.dumps(result,indent=2)+'\n')
print('total',time.perf_counter()-start,flush=True)
