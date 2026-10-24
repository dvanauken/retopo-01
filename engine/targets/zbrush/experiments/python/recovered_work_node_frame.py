"""Ordinary triangle frame transport including ordered split vertex fans."""
import numpy as np


def vertex_fan(start,backward,tri,face_edges,edge_corners):
    vertex=int(tri.flat[start]);current=start;corners=[start];edges=[]
    for _ in range(2001):
        face,k=divmod(current,3);cross=3*face+(k+2)%3 if backward else current
        edge=int(face_edges.flat[cross]);cs=edge_corners[edge]
        if len(cs)!=2:return corners,edges
        other=cs[-1] if cs[0]==cross else cs[0] if cs[-1]==cross else -1
        if other<0:return corners,edges
        backward=int(tri.flat[other])==vertex
        if not backward:other=3*(other//3)+(other%3+1)%3
        if other==start:return corners,edges
        if len(corners)>2000:raise ValueError('Native oversized fan fallback needs qualification')
        edges.append(edge);corners.append(other);current=other
    raise ValueError('Fan guard')


def folded(face,uv,parameter_triangles):
    f=np.float32;t=uv[parameter_triangles[face]];a=f(t[1]-t[0]);b=f(t[2]-t[0])
    return f(f(a[0]*b[1])-f(a[1]*b[0]))<0


def transport(target,attachment,direction,source,tri,pt,uv,face_edges,edge_corners,quarters):
    if target==source:return True,direction,'same'
    ps=set(map(int,pt[target]))&set(map(int,pt[source]))
    if len(ps)>=2:kind='parameter-adjacent'
    else:
        edge=next((int(e) for e in face_edges[target] if any(c//3==source for c in edge_corners[int(e)])),None)
        if edge is not None:
            signed=int(quarters[edge])*(1 if edge_corners[edge][0]//3==source else -1)
            direction=(direction-signed)%4;kind='source-adjacent'
        else:
            common=[int(v) for v in tri[target] if v in tri[source]]
            vertex=int(attachment[1]) if int(attachment[0])==1 else common[0] if common else -1
            if vertex<0:return False,direction,'disjoint'
            a=[int(pt[target,k]) for k in range(3) if int(tri[target,k])==vertex]
            b=[int(pt[source,k]) for k in range(3) if int(tri[source,k])==vertex]
            if a and b and a[0]==b[0]:return True,direction,'same-parameter-fan'
            starts=[3*source+k for k in range(3) if int(tri[source,k])==vertex]
            targets=[3*target+k for k in range(3) if int(tri[target,k])==vertex]
            if not starts or not targets:return False,direction,'missing-attachment-vertex'
            for backward in [True,False]:
                corners,edges=vertex_fan(starts[0],backward,tri,face_edges,edge_corners)
                for i,edge in enumerate(edges):
                    departing=corners[i]//3
                    signed=int(quarters[edge])*(1 if edge_corners[edge][0]//3==departing else -1)
                    direction=(direction-signed)%4
                    if corners[i+1]==targets[0]:return True,direction,'split-source-vertex-fan'
            return False,direction,'unreachable-source-vertex-fan'
    if folded(target,uv,pt)!=folded(source,uv,pt):direction=(direction+2)%4
    return True,direction,kind
