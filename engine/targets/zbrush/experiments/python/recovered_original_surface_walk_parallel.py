"""Ordinary10d2e0 loop including close parallel candidate endpoint selection."""
import struct
import numpy as np
from recovered_surface_walk_candidates import choose
from probe_guide_walk_math import dot,norm,reference
F=np.float32
PARALLEL=struct.unpack('<d',bytes.fromhex('f168e388b5f8e43e'))[0]


def walk(positions,faces,topology,normals,start_point,start_pair,end_point,end_pair,fraction=F(1e-5),absolute=F(0)):
    current=F(start_point).astype(float);target=F(end_point).astype(float);pair=tuple(map(int,start_pair));end=tuple(map(int,end_pair));previous=(0,-1);rows=[];steps=[];edges=topology['edges'];faceEdges=topology['faceEdges'].reshape(-1,3);absolute2=float(F(absolute*absolute))
    def finish(status):
        return dict(status=status,repair=0,edges=np.asarray([r[0] for r in rows],dtype='<i4'),faces=np.asarray([r[1] for r in rows],dtype='<i4'),parameters=np.asarray([r[2] for r in rows],dtype='<f4'),points=np.asarray([r[3] for r in rows],dtype='<f4').reshape(-1,3),steps=steps)
    for iteration in range(1001):
        selection=choose(pair,end,positions,faces,topology)
        if selection['terminal']:
            append=selection['append']
            if append is not None:rows.append((append['edge'],append['face'],append['parameter'],append['point']))
            return finish(1)
        delta=target-current
        if not np.any(delta):return finish(0)
        direction=delta*(1/norm(delta));choice=None
        for expanded in [False,True]:
            best=-1e6;choice=None;tolerance=F(fraction*F(10)) if expanded else fraction;margin=F(fraction*F(100 if expanded else 3));threshold=.05 if expanded else .3
            for corner in selection['candidates']:
                edge=int(faceEdges.ravel()[corner]);normal=normals[corner//3].astype(float);tangent=direction-normal*dot(direction,normal);size=norm(tangent)
                if size<threshold:continue
                tangent*=1/size;a,b=positions[edges[edge]].astype(float);distance,s,t,parallel=reference(np.r_[current,tangent],np.r_[a,b],PARALLEL)
                if not parallel and t>.98:
                    _,s,reverse,parallel=reference(np.r_[current,tangent],np.r_[b,a],PARALLEL);t=1-reverse
                if parallel:
                    if float(F(distance))>1e-6:continue
                    first=dot(a-current,tangent);second=dot(b-current,tangent)
                    if first<=second:t=1.;s=second
                    else:t=0.;s=first
                else:
                    if -float(margin)<=t<=float(tolerance):t=0.
                    if 1-float(tolerance)<=t<=1+float(margin):t=1.
                if 0<=t<=1 and s>best:best=s;choice=(corner,edge,t,a*(1-t)+b*t,expanded,s,parallel)
            if choice is not None and best>=0:break
        if choice is None or best<0:raise NotImplementedError('Negative/no-forward endpoint fallback')
        corner,edge,t,point,expanded,s,parallel=choice;a,b=positions[edges[edge]].astype(float);da=dot(point-a,point-a);db=dot(point-b,point-b)
        if da<absolute2 and t<.1:t=0.
        elif not (da>=absolute2 and db>=absolute2):t=1. if (db<absolute2 and t>.9) or da>=absolute2 else 0.
        newPair=(1,int(edges[edge,int(t)])) if t in (0,1) else (2,edge)
        if newPair==previous and previous[0]!=0:rows.clear();return finish(0)
        rows.append((edge,corner//3,F(t),F(point)));steps.append(dict(corner=corner,edge=edge,parameter=t,lineParameter=s,expanded=expanded,parallelEndpoint=parallel,pair=list(newPair)));previous,pair=pair,newPair;current=point
        if pair==end:return finish(1)
    rows.clear();return finish(0)
