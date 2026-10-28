"""Prototype differentiable feature-preserving refinement; no production dispatch."""
from pathlib import Path
import argparse,json,os,sys,time
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import numpy as np
import trimesh
import torch
from scipy.optimize import minimize,linear_sum_assignment
from scipy.spatial import cKDTree
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'engine/targets/zbrush/clone'),str(ROOT/'engine/targets/zbrush/experiments/python')]
from measure_geometry import read_obj
from features import sharp_edges
from quad_quality import measure
import curved_quad as cq
from source_projection import OrientedSurface
from contact_constraints import planes
from source_features import detect
torch.set_num_threads(1)
ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);ap.add_argument('--passes',type=int,default=6);ap.add_argument('--variant',default='base');ap.add_argument('--start');args=ap.parse_args()
folder=ROOT/'runs/feature-layout'/args.label
data=json.loads((folder/'result.json').read_text());target=int(data['quality']['faces']/(1+data['quality']['targetRelativeError'])) if '7200' not in args.label else 7200
if '3600' in args.label:target=3600
if '12000' in args.label:target=12000
if '1800' in args.label:target=1800
v,f=read_obj(ROOT/'assets/models/toilet.obj');f=np.asarray(f,int);source=trimesh.Trimesh(v,f,process=False)
p,q=read_obj(folder/'layout.obj');q=np.asarray(q,int)
if args.start is not None:
    previous=json.loads((folder/f'feature-fit-{args.start}.json').read_text());p=np.asarray(previous['vertices']);q=np.asarray(previous['faces'])
edges=cq._edges(q);h=np.sqrt(source.area/target)
rawmesh=trimesh.Trimesh(p,np.r_[q[:,[0,1,2]],q[:,[0,2,3]]],process=False)
reference_normals=rawmesh.vertex_normals.copy();projector=OrientedSurface(source)
fe=np.asarray(sharp_edges(v,f,45),int)
if args.variant=='principal':fe,feature_detection=detect(v,f,h);print(feature_detection,flush=True)
degree=np.bincount(fe.ravel(),minlength=len(v));corners=np.flatnonzero((degree>=3) if args.variant!='base' else ((degree!=2)&(degree>0)))
feature_samples=np.concatenate([np.linspace(v[a],v[b],5) for a,b in fe]);feature_a=v[fe[:,0]];feature_b=v[fe[:,1]]
edge_lookup={tuple(e):i for i,e in enumerate(edges)}
edge_faces=[[] for e in edges]
for fi,face in enumerate(q):
    for a,b in zip(face,np.roll(face,-1)):edge_faces[edge_lookup[tuple(sorted((a,b)))]].append(fi)
edge_faces=np.asarray(edge_faces)
corner_dist=np.linalg.norm(v[corners,None,:]-p[None,:,:],axis=2)
if args.variant=='oriented':corner_dist+=np.maximum(.1-source.vertex_normals[corners]@reference_normals.T,0)*10
_,corner_ids=linear_sum_assignment(corner_dist)
paths=[]
for c in data['curves']:paths.append(cq._guide_path(p,edges,np.asarray(c),h)[0])
def segment_nearest(points,a,b,point_normals=None,edge_normals=None):
    centers=(a+b)*.5;k=min(24,len(a));_,near=cKDTree(centers).query(points,k=k)
    near=np.asarray(near).reshape(len(points),k);aa=a[near];d=b[near]-aa
    t=np.clip(((points[:,None]-aa)*d).sum(2)/np.maximum(1e-20,(d*d).sum(2)),0,1)
    delta=points[:,None]-aa-t[:,:,None]*d;distance=(delta*delta).sum(2)
    if point_normals is not None:
        aligned=(point_normals[:,None]*edge_normals[near]).sum(2)>.1
        aligned[~aligned.any(1)]=True
        distance=np.where(aligned,distance,np.inf)
    pick=distance.argmin(1)
    return near[np.arange(len(points)),pick]
def T(x):return torch.tensor(np.asarray(x).tolist(),dtype=torch.float64)
def I(x):return torch.tensor(np.asarray(x).tolist(),dtype=torch.int64)
Q=I(q);E=I(edges);C=I(corner_ids);corner_goal=T(v[corners]);FS=T(feature_samples)
start=time.perf_counter();history=[]
print(json.dumps(dict(torch=torch.__version__,vertices=len(p),features=len(fe),corners=len(corners),target=target)),flush=True)
for iteration in range(args.passes):
    if args.variant=='repair':
        _,corner_ids=linear_sum_assignment(np.linalg.norm(v[corners,None,:]-p[None,:,:],axis=2));C=I(corner_ids)
    tic=time.perf_counter();anchors,_,owners=projector.closest(p,reference_normals) if args.variant in ('oriented','stable') else trimesh.proximity.closest_point(source,p);A,N=T(anchors),T(source.face_normals[owners])
    faces_normal=T(source.face_normals[trimesh.proximity.closest_point(source,p[q].mean(1))[2]])
    feature_normals=np.repeat(source.vertex_normals[fe].mean(1),5,axis=0)
    chosen=segment_nearest(feature_samples,p[edges[:,0]],p[edges[:,1]],feature_normals if args.variant=='oriented' else None,reference_normals[edges].mean(1));FE=I(edges[chosen])
    CF=I(edge_faces[np.unique(chosen)])
    near_feature=segment_nearest(p,feature_a,feature_b);aa,dd=feature_a[near_feature],feature_b[near_feature]-feature_a[near_feature]
    tt=np.clip(((p-aa)*dd).sum(1)/np.maximum(1e-20,(dd*dd).sum(1)),0,1);feature_anchors=aa+tt[:,None]*dd
    ids=np.flatnonzero(np.linalg.norm(p-feature_anchors,axis=1)<h*.45);FI=I(ids);FA=T(feature_anchors[ids])
    tri=np.r_[q[:,[0,1,2]],q[:,[0,2,3]]];mesh=trimesh.Trimesh(p,tri,process=False)
    alltri=np.r_[q[:,[0,1,2]],q[:,[0,2,3]],q[:,[1,2,3]],q[:,[1,3,0]]]
    centers=p[alltri].mean(1)
    interior_goal=trimesh.proximity.closest_point(source,centers)[0]
    if args.variant=='stable':
        directions=np.cross(p[alltri[:,1]]-p[alltri[:,0]],p[alltri[:,2]]-p[alltri[:,0]])
        directions/=np.maximum(1e-12,np.linalg.norm(directions,axis=1))[:,None]
        interior_goal=projector.closest(centers,directions)[0]
    AT=I(alltri);IG=T(interior_goal)
    contact_terms=[]
    witness_terms=[]
    if args.variant in ('contact','creases','repair','principal'):
        audits=[json.loads((folder/('validation-field-3.json' if args.variant=='principal' else 'validation-flipped.json')).read_text())]
        if args.variant=='repair':audits.append(json.loads((folder/'validation-contact-3.json').read_text()))
        pairs=[pair for audit in audits for key in ('nonAdjacentIntersectingFacePairs','adjacentIntersectingFacePairs') for pair in audit['contacts'][key]]
        contact_terms=[(I(a),I(b),I(c),T(n)) for a,b,c,n in planes(p,q,pairs)]
        if args.variant=='repair':
            witnesses=np.asarray([item['witness'] for audit in audits for bound in audit['surface']['wholeSurfaceDiagonals'].values() for item in (bound['sourceToOutput'],bound['outputToSource']) if item.get('witness') is not None])
            near,_,owner=trimesh.proximity.closest_point(mesh,witnesses)
            ids=tri[owner];bary=trimesh.triangles.points_to_barycentric(p[ids],near)
            witness_terms=[(I(ids),T(bary),T(trimesh.proximity.closest_point(source,witnesses)[0]))]
    near,dist,owner=OrientedSurface(mesh).closest(v,source.vertex_normals) if args.variant=='oriented' else trimesh.proximity.closest_point(mesh,v)
    select=dist>h*.15;support=tri[owner[select]]
    S=I(support);B=T(trimesh.triangles.points_to_barycentric(p[support],near[select]));SG=T(v[select])
    guide_terms=[]
    for path,curve in zip(paths,data['curves']):
        samples=cq._sample(np.asarray(curve),401);tangent=np.gradient(samples,axis=0);tangent/=np.maximum(1e-12,np.linalg.norm(tangent,axis=1))[:,None]
        path_edges=np.array(list(zip(path['vertices'][:-1],path['vertices'][1:])))
        selected=segment_nearest(samples,p[path_edges[:,0]],p[path_edges[:,1]])
        guide_terms.append((I(path_edges[selected]),T(samples),T(tangent)))
    def value_gradient(x):
        X=T(x.reshape(-1,3)).requires_grad_(True);P=X[Q];D=torch.roll(P,-1,1)-P;L=torch.linalg.vector_norm(D,dim=2).clamp_min(1e-10)
        previous=-torch.roll(D,1,1);den=L*torch.roll(L,1,1)
        cosine=(previous*D).sum(2)/den
        normal=torch.linalg.cross(P[:,1]-P[:,0],P[:,2]-P[:,0])+torch.linalg.cross(P[:,2]-P[:,0],P[:,3]-P[:,0]);normal=normal/torch.linalg.vector_norm(normal,dim=1).clamp_min(1e-10)[:,None]
        jac=(torch.linalg.cross(D,previous)*normal[:,None]).sum(2)/den
        alignment=(torch.linalg.cross(D,previous)*faces_normal[:,None]).sum(2)/den
        length=torch.linalg.vector_norm(X[E[:,1]]-X[E[:,0]],dim=1)
        delta=(X-A)/h
        a=X[FE[:,0]];d=X[FE[:,1]]-a;t=((FS-a)*d).sum(1)/(d*d).sum(1).clamp_min(1e-15);near=a+t.clamp(0,1)[:,None]*d
        plane=torch.linalg.cross(P[:,1]-P[:,0],P[:,2]-P[:,0]);plane=plane/torch.linalg.vector_norm(plane,dim=1).clamp_min(1e-12)[:,None]
        warpage=((P[:,3]-P[:,0])*plane).sum(1)/h
        pn=torch.stack([torch.linalg.cross(P[:,b]-P[:,a],P[:,c]-P[:,a]) for a,b,c in ((0,1,2),(0,2,3),(1,2,3),(1,3,0))],dim=1)
        pn=pn/torch.linalg.vector_norm(pn,dim=2).clamp_min(1e-12)[:,:,None]
        projected=torch.einsum('fci,fni->fcn',torch.linalg.cross(D,previous)/den[:,:,None],pn)
        balance=3 if args.variant!='base' else 1
        terms=[torch.relu(.60-jac).ravel()*45*balance,torch.relu(.35-alignment).ravel()*30,
               torch.relu(torch.abs(cosine)-.78).ravel()*15*balance,cosine.ravel()*.2,
               torch.relu(L.max(1).values/L.min(1).values-3.2)*12,
               (delta*N).sum(1)*18,delta.ravel()*4,torch.relu(torch.linalg.vector_norm(delta,dim=1)-.2)*50,warpage*25,
               torch.relu(.35-length/h)*5,torch.relu(length/h-1.8)*2,
               ((near-FS)/h*55).ravel(),((X[C]-corner_goal)/h*65).ravel(),
               ((X[FI]-FA)/h*12).ravel(),((X[S]*B[:,:,None]).sum(1)-SG).ravel()/h*6]
        if args.variant in ('strict','contact','creases','repair','stable','field','ridge','principal'):
            terms.extend([torch.relu(.58-projected).ravel()*180,((X[AT].mean(1)-IG)/h).ravel()*20])
        if args.variant in ('creases','repair','stable','field','ridge','principal'):
            cosine_crease=(normal[CF[:,0]]*normal[CF[:,1]]).sum(1)
            terms.append(torch.relu(cosine_crease-(.70710678 if args.variant in ('ridge','principal') else .8660254))*45)
        for CA,CB,CC,CN in contact_terms:
            if len(CC)==2:
                edge=X[CC[1]]-X[CC[0]];edge=edge/torch.linalg.vector_norm(edge).clamp_min(1e-12)
                CN=CN-(CN@edge)*edge;CN=CN/torch.linalg.vector_norm(CN).clamp_min(1e-12)
            lo=(X[CA]@CN).min();hi=(X[CB]@CN).max()
            if len(CC):
                middle=(X[CC]@CN).mean()
                terms.extend([torch.relu(.003-(lo-middle)/h)*2500,torch.relu(.003-(middle-hi)/h)*2500])
            else:terms.append(torch.relu(.005-(lo-hi)/h)*2500)
        for WI,WB,WG in witness_terms:terms.append(((X[WI]*WB[:,:,None]).sum(1)-WG).ravel()/h*300)
        for GE,GS,GT in guide_terms:
            a=X[GE[:,0]];d=X[GE[:,1]]-a;length=torch.linalg.vector_norm(d,dim=1).clamp_min(1e-12)
            t=((GS-a)*d).sum(1)/(length*length);near=a+t.clamp(0,1)[:,None]*d
            terms.extend([((near-GS)/h*40).ravel(),(torch.linalg.cross(d/length[:,None],GT)*8).ravel()])
        value=sum((r*r).sum() for r in terms);value.backward()
        return float(value.detach()),np.asarray(X.grad.tolist()).ravel()
    opt=minimize(value_gradient,p.ravel(),jac=True,method='L-BFGS-B',options=dict(maxiter=250,ftol=1e-10,gtol=1e-5,maxls=25,maxcor=15))
    p=opt.x.reshape(-1,3);quality=measure(p,q,target)
    chosen=segment_nearest(feature_samples,p[edges[:,0]],p[edges[:,1]])
    a=p[edges[chosen,0]];d=p[edges[chosen,1]]-a;t=np.clip(((feature_samples-a)*d).sum(1)/(d*d).sum(1),0,1)
    distance=np.linalg.norm(a+t[:,None]*d-feature_samples,axis=1)
    fit=cq._guide_fit(p,paths,[np.asarray(c) for c in data['curves']])
    row=dict(iteration=iteration,seconds=time.perf_counter()-tic,quality=quality,featureEdgeDistanceP95=float(np.percentile(distance,95)),featureEdgeDistanceMax=float(distance.max()),cornerMax=float(np.linalg.norm(p[corner_ids]-v[corners],axis=1).max()),guides=fit,evaluations=opt.nfev)
    history.append(row)
    (folder/f'feature-fit-history-{args.variant}.json').write_text(json.dumps(history,indent=2)+'\n')
    (folder/f'feature-fit-{args.variant}-{iteration}.json').write_text(json.dumps(dict(vertices=p.tolist(),faces=q.tolist(),guidePaths=paths)))
    print(json.dumps({k:row[k] for k in ('iteration','seconds','featureEdgeDistanceP95','featureEdgeDistanceMax','cornerMax','evaluations')}|dict(angle=quality['minimumAngleDegrees'],jacobian=quality['scaledJacobianMin'],guideAngles=[f['p95TangentAngleDegrees'] for f in fit])),flush=True)
