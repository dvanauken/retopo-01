"""Ordinary nonvertex parameter-isoline advance; exceptional rules unimplemented."""
import math
import numpy as np
F=np.float32

def rounded(x):return math.floor(x+.5) if x>=0 else math.ceil(x-.5)

def position(q,uv,xyz):
    a=F(uv[1]-uv[0]);b=F(uv[2]-uv[0]);c=F(q-uv[0]);det=float(b[1])*float(a[0])-float(b[0])*float(a[1])
    if det==0:raise ValueError('Degenerate UV triangle')
    beta=(float(b[1])*float(c[0])-float(b[0])*float(c[1]))/det;gamma=(float(a[0])*float(c[1])-float(a[1])*float(c[0]))/det
    return F(xyz[0].astype(float)+beta*F(xyz[1]-xyz[0]).astype(float)+gamma*F(xyz[2]-xyz[0]).astype(float))

def advance(face,q,direction,positions,tri,uv,uvtri,faceEdges,edgeOffsets,edgeCorners,quarters,source_vertex=None):
    q=F(q).copy();origin=float(q[direction&1]);previous=-1;path=[];states=[]
    for _ in range(1000):
        states.append(dict(face=face,uv=q.copy(),direction=direction))
        active=direction&1;companion=1-active;sign=1 if direction<2 else -1;triangle=uv[uvtri[face]];choices=[]
        for k in range(3):
            corner=3*face+k
            if corner==previous:continue
            if not path and source_vertex is not None and source_vertex in [int(tri[face,k]),int(tri[face,(k+1)%3])]:continue
            a,b=triangle[k],triangle[(k+1)%3];denom=float(b[companion])-float(a[companion])
            if denom==0:continue
            t=(float(q[companion])-float(a[companion]))/denom
            if not 0<=t<=1:continue
            cross=float(F(b[active]-a[active]))*t+float(a[active]);choices.append((cross,k,t))
        if not choices:raise ValueError('No ordinary isoline exit')
        cross,k,t=(max(choices,key=lambda x:(x[0],x[1])) if sign>0 else min(choices,key=lambda x:(x[0],-x[1])))
        target=origin+sign
        if sign*(cross-target)>=0:
            q[active]=F(target)
            return dict(face=face,uv=q,direction=direction,position=position(q,triangle,positions[tri[face]]),path=path,states=states)
        if t==0 or t==1:raise ValueError('Vertex crossing requires native fan policy')
        if sign*(cross-float(q[active]))<0:raise ValueError('No forward ordinary exit')
        edge=int(faceEdges[face,k]);corners=edgeCorners[edgeOffsets[edge]:edgeOffsets[edge+1]]
        if len(corners)!=2:raise ValueError('Nonmanifold/boundary crossing')
        oldcorner=face*3+k;other=int(corners[1] if int(corners[0])==oldcorner else corners[0]);newface,nk=divmod(other,3);path.append(dict(face=face,edge=edge,corner=oldcorner,t=t))
        same=set(map(int,uvtri[face,[k,(k+1)%3]]))==set(map(int,uvtri[newface,[nk,(nk+1)%3]]))
        if same:q[active]=F(cross)
        else:
            nextTriangle=uv[uvtri[newface]];newq=F((1-t)*nextTriangle[(nk+1)%3].astype(float)+t*nextTriangle[nk].astype(float));quarter=int(quarters[edge])*(1 if int(corners[0])//3==face else -1);newdirection=(direction-quarter)%4;newactive=newdirection&1;newsign=1 if newdirection<2 else -1;progress=F(cross-origin);newo=F(newq[newactive]-F((newsign/sign)*progress));origin=float(rounded(float(newo)));newq[1-newactive]=F(math.trunc(float(F(newq[1-newactive]+F(.5 if newq[1-newactive]>=0 else -.5)))));q=newq;direction=newdirection
        face=newface;previous=other
    raise ValueError('Ordinary traversal guard')
