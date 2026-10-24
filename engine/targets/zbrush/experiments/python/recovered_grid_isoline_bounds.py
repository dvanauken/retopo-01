"""Ordinary grid traversal with the reviewed strict corridor/status2 guard.
Based on the legacy recovered walker; additional positive/native-rejection
boundaries are qualified in713. Full integration and earlier fixture coverage
are separate measurements, not inherited from the legacy module docstring.
"""
import math
import numpy as np
from recovered_regular_grid_walk import rounded
from recovered_native_uv_position import position

def crosses_bound(current,cross,bound):
    return (current<bound<=cross) or (cross<=bound<current) or cross==bound
F=np.float32

def advance(face,q,direction,source_vertex,positions,tri,uv,uvtri,faceEdges,edgeOffsets,edgeCorners,quarters,ordinary_start=False):
    q=F(q).copy();initialq=q.copy();origin=float(q[direction&1]);previous=-1;path=[];states=[];fanvertex=None;fanstart=None;lastface=-1;forced=None
    for _ in range(1000):
        if forced is None:states.append(dict(face=face,uv=q.copy(),direction=direction))
        active=direction&1;companion=1-active;triangle=uv[uvtri[face]];choices=[];current=float(q[active]);direct=ordinary_start and np.array_equal(q,initialq)
        if forced is not None:
            k=next(k for k in range(3) if int(tri[face,k])==forced);t=0.;cross=current;forced=None;skip_vertex=None
        else:
            for k in range(3):
                if not direct and 3*face+k==previous:continue
                if (source_vertex if not path else None) in [int(tri[face,k]),int(tri[face,(k+1)%3])]:continue
                a,b=triangle[k],triangle[(k+1)%3];denom=float(b[companion])-float(a[companion])
                if denom==0:continue
                t=(float(q[companion])-float(a[companion]))/denom
                if 0<=t<=1:choices.append((float(F(b[active]-a[active]))*t+float(a[active]),k,t))
            if not choices:return dict(status=4,states=states,path=path)
            lo=min(choices,key=lambda x:(x[0],-x[1]));hi=max(choices,key=lambda x:(x[0],x[1]));cross,k,t=(hi if direction<2 else lo) if direct else lo if abs(hi[0]-current)<abs(lo[0]-current) else hi
            target=None;link=0;vertex=None
            if current!=origin and min(current,cross)<=origin<=max(current,cross):target=origin;link=1
            elif crosses_bound(current,cross,origin+1):target=origin+1
            elif crosses_bound(current,cross,origin-1):target=origin-1
            elif cross==origin and cross==current and (t==0 or t==1) and len({tuple(v) for v in triangle})<3:
                target=origin;link=1;vertex=int(tri[face,k if t==0 else (k+1)%3])
            if target is not None:
                if cross<current and direction<2:direction+=2
                elif cross>current and direction>=2:direction-=2
                q[active]=F(target)
                point=positions[vertex].copy() if vertex is not None else position(q,triangle,positions[tri[face]])
                return dict(status=0,face=face,uv=q,direction=direction,position=point,vertex=vertex,link=link,corner=k,expand=(target==cross or t==0 or t==1),path=path,states=states)
            #2aadc0 rejects a crossing outside the original double corridor
            #when float32 current already rounded onto a bound (native status2).
            if cross<origin-1 or origin+1<cross:return dict(status=2,states=states,path=path)
            if t==0 or t==1:
                oldfan=fanvertex
                vk=k if t==0 else (k+1)%3;fanvertex=int(tri[face,vk])
                if fanstart is None:fanstart=(fanvertex,face)
                elif fanstart==(fanvertex,face):return dict(status=3,states=states,path=path)
                skip_vertex=fanvertex if oldfan is None and triangle[(vk+1)%3,companion]==q[companion] else None
                k=vk;t=0.
            else:fanvertex=None;fanstart=None;skip_vertex=None
        edge=int(faceEdges[face,k]);corners=edgeCorners[edgeOffsets[edge]:edgeOffsets[edge+1]]
        if len(corners)!=2:raise ValueError('Unqualified boundary/nonmanifold seed walk')
        oldcorner=face*3+k;other=int(corners[1] if int(corners[0])==oldcorner else corners[0]);newface,nk=divmod(other,3);
        if newface==lastface:return dict(status=3,states=states,path=path)
        lastface=face;path.append(dict(face=face,edge=edge,corner=oldcorner,t=t));same=set(map(int,uvtri[face,[k,(k+1)%3]]))==set(map(int,uvtri[newface,[nk,(nk+1)%3]]))
        if same:q[active]=F(cross)
        else:
            nextTriangle=uv[uvtri[newface]];newq=F((1-t)*nextTriangle[(nk+1)%3].astype(float)+t*nextTriangle[nk].astype(float));quarter=int(quarters[edge])*(1 if int(corners[0])//3==face else -1);newdirection=(direction-quarter)%4;newactive=newdirection&1;ratio=(1 if newdirection<2 else -1)/(1 if direction<2 else -1);newo=F(newq[newactive]-F(ratio*F(cross-origin)));origin=float(rounded(float(newo)));newq[1-newactive]=F(math.trunc(float(F(newq[1-newactive]+F(.5 if newq[1-newactive]>=0 else -.5)))));q=newq;direction=newdirection
        face=newface;previous=other;forced=skip_vertex
    raise ValueError('Seed traversal guard')
