"""Candidate12db90 ordinary triangle walk; unsupported sharp turns fail closed."""
import math,struct
import numpy as np
from recovered_reflex_hexagon import norm
F=np.float32
MIN_STEP=np.frombuffer(bytes.fromhex('acc52737'),'<f4')[0]
TURN_LIMIT=struct.unpack('<d',bytes.fromhex('fca9f1d24d62503f'))[0]
LINE_MIN=struct.unpack('<d',bytes.fromhex('1fb8d44a7aee8d35'))[0]


def dot_xyz(a,b):return (float(a[0])*float(b[0])+float(a[1])*float(b[1]))+float(a[2])*float(b[2])


def dot_yxz(a,b):return (float(a[1])*float(b[1])+float(a[0])*float(b[0]))+float(a[2])*float(b[2])


def normalize(a):
    length=math.sqrt(dot_xyz(a,a))
    if length==0:return a.copy(),length
    return a*(1/length),length


def line_edge(point,direction,a,b):
    w=a.astype(float)-point;e=F(b-a).astype(float);c=dot_xyz(e,direction);length2=dot_yxz(e,e);we=dot_yxz(w,e);wd=dot_xyz(w,direction);den=length2-c*c
    if den<LINE_MIN:raise NotImplementedError('Nearly parallel305ee0 stale output branch')
    inv=1/den;return (wd*length2-we*c)*inv,(wd*c-we)*inv


def move(source,tri,topology,normals,guides,attachment,point,displacement):
    kind,index=map(int,attachment);original=F(point).copy();delta=F(displacement);current=original.astype(float);edges=topology['edges'];face_edges=topology['faceEdges'].reshape(-1,3);previous=-1;steps=[]
    if not np.any(delta!=0):return original,np.asarray([kind,index],dtype='<i4'),steps
    def edge_corners(e):return topology['edgeCorners'][topology['edgeCornerOffsets'][e]:topology['edgeCornerOffsets'][e+1]]
    def vertex_corners(v):return topology['vertexCorners'][topology['vertexCornerOffsets'][v]:topology['vertexCornerOffsets'][v+1]]
    def incident_edges(v):return topology['vertexEdges'][topology['vertexEdgeOffsets'][v]:topology['vertexEdgeOffsets'][v+1]]
    if kind==4:normal=normals[index]
    elif kind in [1,2]:
        cs=vertex_corners(index) if kind==1 else edge_corners(index);normal=np.zeros(3,dtype='<f4')
        for c in cs:normal=F(normal+normals[int(c)//3])
        normal=norm(normal)
    else:raise NotImplementedError('Unsupported attachment kind')
    direction,budget=normalize(delta.astype(float)-normal.astype(float)*dot_xyz(normal,delta))
    if budget==0:return original,np.asarray([kind,index],dtype='<i4'),steps
    def enter_other_face(corner,direction):
        edge=int(face_edges.flat[corner]);cs=edge_corners(edge)
        if len(cs)!=2:return None,direction
        other=next(int(c) for c in cs if int(c)!=corner);face=other//3;n=normals[face].astype(float);q,length=normalize(direction-n*dot_yxz(n,direction))
        if length<TURN_LIMIT:raise NotImplementedError('Sharp turn quaternion branch')
        return face,q
    for iteration in range(300):
        steps.append(dict(kind=kind,index=index,budget=budget));corner=-1;target=None;target_kind=0;target_index=-1
        if kind==4:
            selected=-1;best=F(np.frombuffer(bytes.fromhex('bd3786b5'),'<f4')[0]);fraction=F(0)
            for k in range(3):
                e=int(face_edges[index,k])
                if e==previous:continue
                a,b=source[tri[index,k]],source[tri[index,(k+1)%3]];s,t=line_edge(current,direction,a,b)
                if 0<=t<=1 and float(best)<=s:selected=3*index+k;best=F(s);fraction=F(t);target=F(F(F(b-a)*fraction)+a)
            if selected<0:return F(current),np.asarray([kind,index],dtype='<i4'),steps
            if best<=0:
                vertex=next((int(v) for v in tri[index] if np.array_equal(source[v],target)),None)
                if vertex is None:kind,index=2,int(face_edges.flat[selected])
                else:kind,index=1,vertex
                continue
            if budget<=float(best):return F(current+direction*budget),np.asarray([kind,index],dtype='<i4'),steps
            budget-=float(max(best,MIN_STEP));current=target.astype(float);previous=int(face_edges.flat[selected]);face,direction=enter_other_face(selected,direction)
            if face is None:return F(current),np.asarray([kind,index],dtype='<i4'),steps
            index=face
            if budget<=0:return F(current),np.asarray([kind,index],dtype='<i4'),steps
            continue
        if kind==1:
            marked=[int(e) for e in incident_edges(index) if guides[e]]
            if marked:
                if len(marked)!=2:return F(current),np.asarray([kind,index],dtype='<i4'),steps
                best=F(-1)
                for e in marked:
                    a,b=map(int,edges[e]);neighbor=b if a==index else a;v=F(source[neighbor]-F(current));unit=norm(v);score=F(dot_yxz(unit,direction))
                    if best<score:best=score;target=source[neighbor].copy();target_kind=2;target_index=e
                if target is None:return F(current),np.asarray([kind,index],dtype='<i4'),steps
            else:
                best=F(-100)
                for c in vertex_corners(index):
                    f,k=divmod(int(c),3);k0=(k+1)%3;k1=(k+2)%3;a,b=source[tri[f,k0]],source[tri[f,k1]];s,t=line_edge(current,direction,a,b)
                    if 0<=t<=1 and s>0 and float(best)<s:best=F(s);fraction=F(t);target=F(F(F(b-a)*fraction)+a);corner=3*f+k0
        elif kind==2:
            if guides[index]:
                a,b=map(int,edges[index]);unit=norm(F(source[b]-source[a]));score=F(dot_yxz(unit,direction));budget*=float(abs(score));target_index=b if score>=0 else a;target=source[target_index].copy();target_kind=1
            else:
                best=F(-1)
                for c in edge_corners(index):
                    f,k=divmod(int(c),3)
                    for j in [(k+1)%3,(k+2)%3]:
                        a,b=source[tri[f,j]],source[tri[f,(j+1)%3]];s,t=line_edge(current,direction,a,b)
                        if 0<=t<=1 and s>0 and float(best)<s:best=F(s);fraction=F(t);target=F(F(F(b-a)*fraction)+a);corner=3*f+j
        else:raise NotImplementedError('Unsupported evolving attachment')
        if target is None:return F(current),np.asarray([kind,index],dtype='<i4'),steps
        length=F(math.sqrt(dot_yxz(current-target.astype(float),current-target.astype(float))))
        if budget<=float(length):
            if length==0:return F(current),np.asarray([kind,index],dtype='<i4'),steps
            weight=F(budget/float(length));out=F(F(F(target-F(current))*weight)+F(current));return out,np.asarray([kind,index],dtype='<i4'),steps
        budget-=float(max(length,MIN_STEP));current=target.astype(float)
        if corner<0:kind,index=target_kind,target_index
        else:
            previous=int(face_edges.flat[corner]);face,direction=enter_other_face(corner,direction)
            if face is None:return F(current),np.asarray([kind,index],dtype='<i4'),steps
            kind,index=4,face
        if budget<=0:return F(current),np.asarray([kind,index],dtype='<i4'),steps
    return F(current),np.asarray([kind,index],dtype='<i4'),steps
