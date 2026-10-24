"""Candidate29e080 directed edge targets from explicit operation inputs."""
import numpy as np
from recovered_work_node_frame import transport,folded
F=np.float32


def dot(a,b):
    p=F(a*b);return F(F(p[0]+p[1])+p[2])


def fallback(attachment,scales,default,vertex_corners,edge_corners):
    kind,index=map(int,attachment);face=-1
    if kind==1 and len(vertex_corners[index]):face=int(vertex_corners[index][0])//3
    elif kind==2 and len(edge_corners[index]):face=int(edge_corners[index][0])//3
    elif kind==4:face=index
    if face<0:return F(default*F(.6)),F(default*F(1.8))
    a,b=scales[face];average=F(F(a+b)*F(.5));minimum=F(average*F(.7));maximum=F(average*F(1.5))
    if a<minimum:minimum=F(a*F(.95))
    if b<minimum:minimum=F(b*F(.95))
    if maximum<a:maximum=F(a*F(1.1))
    if maximum<b:maximum=F(b*F(1.1))
    return minimum,maximum


def directed(g,vertex,neighbor,positions,attachments,source_faces,neighbors,bases,coefficients,scales,flags,default,vertex_corners,edge_corners):
    attachment=attachments[vertex];kind,index=map(int,attachment);face=int(source_faces[vertex]);direction=next((i for i in range(4) if neighbors[vertex,i]==neighbor),-1)
    def missing():
        lo,hi=fallback(attachment,scales,default,vertex_corners,edge_corners);return dict(minimum=lo,maximum=hi,gain=F(.2),direction=np.zeros(3,dtype='<f4'),valid=F(0),branch='fallback')
    if face<0 or direction<0:return missing()
    reversed_face=folded(face,g.uv,g.pt);edge_vector=F(positions[neighbor]-positions[vertex]);target=face
    if kind==2:
        incident=edge_corners[index];corner=next((int(c) for c in incident if c//3==face),-1)
        if corner>=0 and len(incident)==2:
            other=next((int(c) for c in incident if c!=corner),-1)
            if other>=0:
                a,b=g.source_edges[index];midpoint=F(F(g.xyz[a]+g.xyz[b])*F(.5));opposite0=int(g.tri.flat[3*(corner//3)+(corner%3+2)%3]);opposite1=int(g.tri.flat[3*(other//3)+(other%3+2)%3])
                if dot(edge_vector,F(g.xyz[opposite0]-midpoint))<dot(edge_vector,F(g.xyz[opposite1]-midpoint)):target=other//3
    elif kind==1:
        best=F(-np.finfo(np.float32).max);selected=-1
        for corner in vertex_corners[index]:
            f,k=divmod(int(corner),3);a=g.tri[f,(k+1)%3];b=g.tri[f,(k+2)%3];midpoint=F(F(g.xyz[a]+g.xyz[b])*F(.5));value=dot(edge_vector,F(midpoint-g.xyz[index]))
            if best<value:best=value;selected=f
        if selected>=0:target=selected
    if target!=face:
        ok,direction,_=transport(target,attachment,direction,face,*g.geometry)
        if not ok:return missing()
        face=target;reversed_face=reversed_face or folded(face,g.uv,g.pt)
    axis=direction%2;a,b=coefficients[face,axis];v=F(F(bases[face,0]*a)+F(bases[face,1]*b))
    if direction>=2:v=F(-v)
    if reversed_face and dot(edge_vector,v)<0:v=F(-v)
    scale=scales[face,axis];return dict(minimum=F(scale*F(.5)),maximum=F(scale*(F(1.2) if flags[face]&1 else F(2.5))),gain=F(1),direction=v,valid=F(1),branch='directed')
