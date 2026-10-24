"""Ordinary24a900 triangle replacement from own24d0c0 midpoint marks."""
from collections import Counter
import numpy as np
from recovered_subdivision_points import produce
F=np.float32


def split(positions,faces,threshold):
    if any(len(row)!=3 for row in faces):raise NotImplementedError('Only ordinary triangle replacement')
    points=positions[np.asarray(faces)].astype(float);minAngle=float('inf')
    for k in range(3):
        a=points[:,(k+1)%3]-points[:,k];b=points[:,(k+2)%3]-points[:,k];den=np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1)
        if np.any(den==0):raise NotImplementedError('Degenerate triangle')
        minAngle=min(minAngle,float(np.min(np.arccos(np.clip(np.sum(a*b,axis=1)/den,-1,1)))))
    if minAngle<.21:raise NotImplementedError('Small corner exceptional midpoint adjustment')
    out,selected,mapping,topology=produce(positions,faces,threshold)
    if not len(selected):return out,[list(map(int,row)) for row in faces],dict(splitCounts={'0':len(faces)},minAngle=minAngle,selected=selected)
    result=[];counts=Counter();faceEdges=topology['faceEdges'].reshape(-1,3)
    def square(a):return F(F(F(a[0]*a[0])+F(a[1]*a[1]))+F(a[2]*a[2]))
    for row,es in zip(faces,faceEdges):
        v=list(map(int,row));m=list(map(int,mapping[es]));count=sum(x>=0 for x in m);counts[count]+=1
        if count==0:result.append(v)
        elif count==3:result.extend([[v[0],m[0],m[2]],[v[1],m[1],m[0]],[v[2],m[2],m[1]],[m[0],m[1],m[2]]])
        elif count==1:
            k=next(k for k in range(3) if m[k]>=0);result.extend([[m[k],v[(k+1)%3],v[(k+2)%3]],[m[k],v[(k+2)%3],v[k]]])
        else:
            k=2 if m[0]<0 else 0 if m[1]<0 else 1;n=(k+1)%3;p=(k+2)%3;result.append([v[k],m[k],m[p]]);d0=square(F(out[m[p]]-positions[v[n]]));d1=square(F(out[m[k]]-positions[v[p]]))
            if d1<=d0:result.extend([[m[k],v[n],v[p]],[m[k],v[p],m[p]]])
            else:result.extend([[m[p],m[k],v[n]],[m[p],v[n],v[p]]])
    return out,result,dict(splitCounts={str(k):v for k,v in counts.items()},minAngle=minAngle,selected=selected)
