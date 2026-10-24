"""Integral source-seed face wedge / next-axis selection, engine0x2a9490."""
import math
import numpy as np
F=np.float32


def turn(vertex,face,direction,point,tri,pt,uv,face_edges,edge_corners,vertex_corners):
    original=face;initial_direction=direction;candidate=-1
    local=next((k for k in range(3) if int(tri[face,k])==vertex),None)
    if local is None:
        found=None
        for k,edge in enumerate(face_edges[face]):
            cs=edge_corners[int(edge)];current=3*face+k
            if len(cs)!=2:continue
            other=cs[-1] if cs[0]==current else cs[0] if cs[-1]==current else -1
            if other<0:continue
            corner=3*(other//3)+(other%3+2)%3
            if int(tri.flat[corner])==vertex:found=corner;break
        if found is None:return False,face,direction,point
        face,local=divmod(found,3)
    corner=3*face+local;iterations=0
    while True:
        if len(vertex_corners[vertex])+2<iterations:return False,face,direction,point
        f,k=divmod(corner,3);p=uv[pt[f,k]];n=uv[pt[f,(k+1)%3]];b=uv[pt[f,(k+2)%3]]
        if any(float(x)!=math.trunc(float(F(x+F(.5 if x>=0 else -.5)))) for x in p):return False,face,direction,point
        with np.errstate(invalid='ignore',divide='ignore'):
            rx=F(F(p[0]-n[0])/F(b[0]-n[0]));ry=F(F(p[1]-n[1])/F(b[1]-n[1]))
        if rx<0 or 1<rx:
            if 0<=ry<=1 and (face!=original or initial_direction&1):return True,face,0,p.copy()
        elif face!=original or rx!=ry:
            if ry<0 or 1<ry:
                if face!=original or initial_direction%2!=1:return True,face,1,p.copy()
            elif rx<=ry:
                if face!=original:return True,face,0,p.copy()
                if initial_direction&1==0:return True,face,1,p.copy()
                candidate=0
            else:
                if face!=original:return True,face,1,p.copy()
                if initial_direction&1:return True,face,0,p.copy()
                candidate=1
        edge=int(face_edges.flat[corner]);cs=edge_corners[edge]
        if len(cs)!=2:return True,-1,direction,point
        other=cs[-1] if cs[0]==corner else cs[0] if cs[-1]==corner else -1
        if other<0:return True,-1,direction,point
        corner=3*(other//3)+(other%3+1)%3;face=corner//3;iterations+=1
        if face==original:break
    if candidate!=-1:return True,original,candidate,point
    return False,face,(direction+1)%4,point
