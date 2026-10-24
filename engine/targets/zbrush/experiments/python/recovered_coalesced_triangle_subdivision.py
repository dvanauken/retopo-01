"""24d0c0 closed ordinary midpoint coalescing and triangle replacement.

Static candidate until actual native boundary qualification. No attributes,
external protected edges, boundary preservation or output allocation budget.
"""
from collections import Counter
import numpy as np
from recovered_conditioning_measures import produce
from recovered_quality_edge_eligibility import oriented_angle
from recovered_mesh_topology import packed
F=np.float32
SMALL_ANGLE=F(0.20943951606750488)
CREASE_ANGLE=F(0.0872664600610733)
LIMIT_PI=3.1415927410125732

def square(x):return F(F(F(x[0]*x[0])+F(x[1]*x[1]))+F(x[2]*x[2]))

def split(positions,faces,threshold):
    p=np.asarray(positions,dtype='<f4');tri=np.asarray(faces,dtype='<i4');g=produce(p,tri);top=g['topology'];edges=top['edges'];delta=F(p[edges[:,0]]-p[edges[:,1]]);sq=F(F(F(delta[:,0]*delta[:,0])+F(delta[:,1]*delta[:,1]))+F(delta[:,2]*delta[:,2]));selected=sq>F(F(threshold)*F(threshold));mapping=np.full(len(edges),-1,'<i4');points=[];contributors=[];reasons=Counter();fe=top['faceEdges'].reshape(-1,3);ve=top['vertexEdges'];vo=top['vertexEdgeOffsets'];co=top['vertexCornerOffsets']
    def other_corner(edge,current):
        a,b=top['edgeCornerOffsets'][edge:edge+2];cs=top['edgeCorners'][a:b]
        if len(cs)!=2 or current not in cs:raise NotImplementedError('Ordinary consistently oriented closed two-face edges required')
        return int(cs[1] if cs[0]==current else cs[0])
    for corner,angle in enumerate(g['corners']):
        if angle>SMALL_ANGLE:continue
        f,k=divmod(corner,3);e0,e1,e2=int(fe[f,k]),int(fe[f,(k+2)%3]),int(fe[f,(k+1)%3])
        if not(selected[e0] and selected[e1]) or selected[e2] or mapping[e0]>=0 or mapping[e1]>=0:continue
        ia,ib,ic=map(int,[tri[f,k],tri[f,(k+1)%3],tri[f,(k+2)%3]]);a,b,c=p[[ia,ib,ic]];incident=ve[vo[ia]:vo[ia+1]];degree=len(incident);count_corners=int(co[ia+1]-co[ia]);other=[int(e) for e in incident if e not in [e0,e1] and selected[e]]
        if degree<5 and degree==count_corners and (degree==3 and len(other)==1 or degree==4 and len(other)==2 and len(set(int(mapping[e]) for e in other))==1):reasons['low-valence']+=1;continue
        if g['edgeAngles'][e1]>=CREASE_ANGLE:reasons['protected-previous-crease']+=1;continue
        point=F(F(a+b)*F(.5)) if g['edgeAngles'][e0]>=CREASE_ANGLE else F(F(F(F(a*F(2))+b)+c)*F(.25));limit=F(LIMIT_PI-(float(angle)+1e-6));neighbor=other_corner(e0,corner);nf,nk=divmod(neighbor,3);x=p[tri[nf,(nk+2)%3]];normal=g['normals'][nf];angles=[oriented_angle(F(point-x),F(a-x),normal),oriented_angle(F(b-x),F(point-x),normal)]
        if any(value>limit for value in angles):reasons['following-neighbor-angle']+=1;continue
        previous_corner=f*3+(k+2)%3;neighbor=other_corner(e1,previous_corner);nf,nk=divmod(neighbor,3);x=p[tri[nf,(nk+2)%3]];normal=g['normals'][nf];angles=[oriented_angle(F(point-x),F(c-x),normal),oriented_angle(F(a-x),F(point-x),normal)]
        if any(value>limit for value in angles):reasons['previous-neighbor-angle']+=1;continue
        mapping[[e0,e1]]=len(p)+len(points);points.append(point);contributors.append([ia,ib,ic]);reasons['coalesced']+=1
    special=len(points)
    for edge in np.flatnonzero(selected):
        if mapping[edge]>=0:continue
        a,b=map(int,edges[edge]);mapping[edge]=len(p)+len(points);points.append(F(F(p[a]+p[b])*F(.5)));contributors.append([a,b])
    new=np.asarray(points,dtype='<f4').reshape(-1,3);out=np.concatenate([p,new]);result=[];counts=Counter();dropped=0
    for row,es in zip(tri,fe):
        v=list(map(int,row));m=list(map(int,mapping[es]));count=sum(x>=0 for x in m);counts[count]+=1
        if count==0:rows=[v]
        elif count==3:rows=[[v[0],m[0],m[2]],[v[1],m[1],m[0]],[v[2],m[2],m[1]],[m[0],m[1],m[2]]]
        elif count==1:
            k=next(k for k in range(3) if m[k]>=0);rows=[[m[k],v[(k+1)%3],v[(k+2)%3]],[m[k],v[(k+2)%3],v[k]]]
        else:
            k=2 if m[0]<0 else 0 if m[1]<0 else 1;n=(k+1)%3;q=(k+2)%3;rows=[[v[k],m[k],m[q]]];d0=square(F(out[m[q]]-p[v[n]]));d1=square(F(out[m[k]]-p[v[q]]));rows.extend([[m[k],v[n],v[q]],[m[k],v[q],m[q]]] if d1<=d0 else [[m[q],m[k],v[n]],[m[q],v[n],v[q]]])
        for row in rows:
            if len(set(row))!=3:dropped+=1;continue
            result.append(row)
    offsets,indices=packed(contributors)
    return out,np.asarray(result,'<i4'),dict(edgeMidpointMap=mapping,newPointPool=new,sourcePointOffsets=offsets,sourcePointIndices=indices,selectedEdges=np.flatnonzero(selected).astype('<i4'),specialPoints=special,droppedRepeatedIndexTriangles=dropped,mergeReasonCounts=dict(reasons),splitCounts=dict(counts),scope='Ordinary closed no external mask/attribute/budget midpoint coalescing candidate; exact conformance must be separately qualified.')
