"""Closed manifold ordinary317430 candidate; explicit mobility/blend inputs."""
import math
import numpy as np
from recovered_mesh_topology import build
from recovered_relaxation_pairs import field_candidate,balanced_candidate,length_yxz
from recovered_reflex_hexagon import norm
F=np.float32


def dot_yxz(a,b):return F(F(F(a[1]*b[1])+F(a[0]*b[0]))+F(a[2]*b[2]))


def segment(point,a,b):
    delta=F(b-a)
    if dot_yxz(F(point-a),delta)<=0:return length_yxz(F(point-a)),a.copy()
    if dot_yxz(delta,F(point-b))>=0:return length_yxz(F(point-b)),b.copy()
    direction=F(delta*F(F(1)/length_yxz(delta)));offset=F(point-a);t=dot_yxz(offset,direction);perpendicular=F(offset-F(direction*t));return length_yxz(perpendicular),F(point-perpendicular)


def closest_two(point,current,a,b):
    d0,p0=segment(point,a,current);d1,p1=segment(point,b,current);return p0 if d0<d1 else p1


def polygon_normal(points):
    total=np.zeros(3,dtype='<f4')
    for a,b in zip(points,np.roll(points,-1,axis=0)):
        total=F(total+F([F(F(a[1]-b[1])*F(a[2]+b[2])),F(F(a[2]-b[2])*F(a[0]+b[0])),F(F(a[0]-b[0])*F(a[1]+b[1]))]))
    return norm(total)


def closed_star(vertex,faces,topology):
    offsets=np.cumsum([0]+[len(f) for f in faces]);corner_faces=np.repeat(np.arange(len(faces)),[len(f) for f in faces]);incident=topology['vertexCorners'][topology['vertexCornerOffsets'][vertex]:topology['vertexCornerOffsets'][vertex+1]]
    if not len(incident):return [],[]
    first=int(incident[0]);corner=first;corners=[];edges=[int(topology['faceEdges'][first])]
    for _ in range(len(incident)+1):
        corners.append(corner);face=int(corner_faces[corner]);k=corner-int(offsets[face]);previous=int(offsets[face]+(k-1)%len(faces[face]));edge=int(topology['faceEdges'][previous]);adjacent=topology['edgeCorners'][topology['edgeCornerOffsets'][edge]:topology['edgeCornerOffsets'][edge+1]]
        if len(adjacent)!=2:raise NotImplementedError('Only closed manifold stars')
        other=next(int(c) for c in adjacent if c!=previous);otherFace=int(corner_faces[other]);otherK=other-int(offsets[otherFace]);corner=other if faces[otherFace][otherK]==vertex else int(offsets[otherFace]+(otherK+1)%len(faces[otherFace]));edges.append(edge)
        if corner==first:break
    else:raise ValueError('Nonclosing vertex star')
    if len(corners)!=len(incident) or edges[0]!=edges[-1]:raise ValueError('Unsupported vertex star')
    return corners,edges


def requested(positions,faces,minimum,maximum,directions,guide_edges,mobility,blend):
    topology=build(len(positions),faces);edges=topology['edges'];normals=np.asarray([polygon_normal(positions[row]) for row in faces]);corner_faces=np.repeat(np.arange(len(faces)),[len(f) for f in faces]);angles=[]
    for e in range(len(edges)):
        cs=topology['edgeCorners'][topology['edgeCornerOffsets'][e]:topology['edgeCornerOffsets'][e+1]]
        if len(cs)!=2:raise NotImplementedError('Closed ordinary mesh required')
        value=float(dot_yxz(normals[corner_faces[cs[0]]],normals[corner_faces[cs[1]]]));angles.append(F(math.acos(max(-1.,min(1.,value)))))
    angles=np.asarray(angles,dtype='<f4');out=positions.copy();branches=[]
    for vertex,current in enumerate(positions):
        es=topology['vertexEdges'][topology['vertexEdgeOffsets'][vertex]:topology['vertexEdgeOffsets'][vertex+1]];degree=len(es);marked=[int(e) for e in es if guide_edges[e]]
        def neighbor(e):return int(edges[e,1] if edges[e,0]==vertex else edges[e,0])
        if mobility[vertex]==0 or degree==0:branches.append('frozen-mobility-or-unused');continue
        if degree!=4:
            if marked and len(marked)!=2:branches.append('frozen-irregular-guide-count');continue
            candidate=np.zeros(3,dtype='<f4')
            for e in es:candidate=F(candidate+positions[neighbor(e)])
            candidate=F(candidate*F(F(1)/F(degree)))
            if marked:candidate=closest_two(candidate,current,*[positions[neighbor(e)] for e in marked])
            step=F(mobility[vertex]*F(.4));branch='irregular-average'
        else:
            _,ring=closed_star(vertex,faces,topology);pairs=[np.asarray([ring[0],ring[2]],dtype='<i4'),np.asarray([ring[1],ring[3]],dtype='<i4')];counts=[int(np.count_nonzero(guide_edges[p])) for p in pairs]
            if tuple(counts) not in [(0,0),(2,0),(0,2)]:branches.append('frozen-regular-guide-count');continue
            mix=F(1) if any(counts) else blend[vertex];fc=[];bc=[]
            for k,pair in enumerate(pairs):
                ns=np.asarray([neighbor(e) for e in pair],dtype='<i4');other=1-k
                if counts[other]==2 and float(F(angles[pairs[other][0]]+angles[pairs[other][1]]))>math.pi/6:fc.append(current.copy())
                elif mix>0:fc.append(field_candidate(positions,edges,vertex,ns,pair,minimum,maximum,directions))
                else:fc.append(np.zeros(3,dtype='<f4'))
                bc.append(balanced_candidate(positions,vertex,ns,pair,minimum,maximum) if mix<1 else np.zeros(3,dtype='<f4'))
            field=F(F(fc[0]+fc[1])*F(.5));balanced=F(F(bc[0]+bc[1])*F(.5));candidate=F(F(field*mix)+F(balanced*F(F(1)-mix)))
            for count,pair in zip(counts,pairs):
                if count==2:candidate=closest_two(candidate,current,*[positions[neighbor(e)] for e in pair])
            step=F(mobility[vertex]*F(.33));branch='regular-guide' if any(counts) else 'regular-field-balance'
        out[vertex]=F(F(F(F(1)-step)*current)+F(candidate*step));branches.append(branch)
    return out,branches
