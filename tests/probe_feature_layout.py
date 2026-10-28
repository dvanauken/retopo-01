"""Isolated feature/guide field experiments on the original toilet."""
from pathlib import Path
import argparse, json, os, subprocess, sys, time
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj
from features import sharp_edges, paths_from_edges
from quad_quality import measure
from guided_layout import runtime

ap=argparse.ArgumentParser();ap.add_argument('--target',type=int,required=True);ap.add_argument('--guides',default='bowl');ap.add_argument('--label',required=True);ap.add_argument('--embedded-features',action='store_true');ap.add_argument('--embedded-authored',action='store_true');ap.add_argument('--adaptive',action='store_true');args=ap.parse_args()
out=ROOT/'runs/feature-layout'/args.label;out.mkdir(parents=True,exist_ok=False)
v,f=read_obj(ROOT/'assets/models/toilet.obj');f=np.asarray(f,int);mesh=trimesh.Trimesh(v,f,process=False)
features=sharp_edges(v,f,45);chains=paths_from_edges(features)
print(json.dumps(dict(featureEdges=len(features),chains=len(chains),chainVertices=sorted([len(p) for _,p in chains],reverse=True)[:40])),flush=True)
curves=[] if args.guides=='none' else json.loads((ROOT/'tests/toilet-sampled-worker/integrated-fallback/bowl-only-1800/curves.json').read_text())['curves']
segments=[]
for ci,c in enumerate(curves):
    c=np.asarray(c,float);a,b=c[:-1],c[1:]
    owners=trimesh.proximity.closest_point(mesh,(a+b)*.5)[2]
    segments.extend([[ci,*x,*y,*n] for x,y,n in zip(a,b,mesh.face_normals[owners])])
input_path=ROOT/'assets/models/toilet.obj'
if args.embedded_features or args.embedded_authored:
    from guide_embedding import embed
    from guided_layout import obj
    vv,ff,embedding=embed(v,f,curves)
    input_path=out/'embedded.obj';obj(input_path,vv,ff)
    segments=[]
    for ci,ee in embedding['guideEdges'].items():
        ee=np.asarray(ee);a,b=vv[ee[:,0]],vv[ee[:,1]];owners=trimesh.proximity.closest_point(mesh,(a+b)*.5)[2]
        segments.extend([[int(ci),*x,*y,*n] for x,y,n in zip(a,b,mesh.face_normals[owners])])
    for ci,(_,chain) in enumerate(chains if args.embedded_features else [],len(curves)):
        for a,b in zip(chain[:-1],chain[1:]):
            normal=mesh.vertex_normals[[a,b]].mean(0);normal/=np.linalg.norm(normal)
            segments.append([ci,*v[a],*v[b],*normal])
with (out/'segments.txt').open('w') as stream:
    stream.write(str(len(segments))+'\n')
    for row in segments:stream.write(' '.join(map(str,row))+'\n')
exe,env,manifest=runtime();env['OMP_NUM_THREADS']='4'
command=[str(exe),'-i',str(input_path),'-o',str(out/'layout.obj'),'-f',str(args.target),'-seed','2','-sharp','-field',str(out/'field.csv')]
if args.adaptive:command+=['-adaptive']
if curves:command+=['-guides',str(out/'segments.txt'),'-guide-width','.75','-orientation-weight','1','-position-weight','0']
if args.embedded_features or args.embedded_authored:command+=['-embedded-guides','-project-guide-positions']
start=time.perf_counter()
with (out/'layout.log').open('w') as log:process=subprocess.run(command,env=env,stdout=log,stderr=log,timeout=150,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
elapsed=time.perf_counter()-start
if process.returncode:raise RuntimeError((out/'layout.log').read_text()[-2000:])
p,q=read_obj(out/'layout.obj');q=np.asarray(q,int);quality=measure(p,q,args.target)
output=trimesh.Trimesh(p,np.r_[q[:,[0,1,2]],q[:,[0,2,3]]],process=False)
points=np.concatenate([np.linspace(v[a],v[b],5) for a,b in features])
distance=trimesh.proximity.closest_point(output,points)[1]
result=dict(elapsedSeconds=elapsed,quality=quality,sourceFeatureSurfaceDistance=dict(p95=float(np.percentile(distance,95)),max=float(distance.max())),command=command,sourceFeatures=features,curves=curves)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(elapsedSeconds=elapsed,faces=len(q),minAngle=quality['minimumAngleDegrees'],jacobian=quality['scaledJacobianMin'],featureDistance=result['sourceFeatureSurfaceDistance'])),flush=True)
