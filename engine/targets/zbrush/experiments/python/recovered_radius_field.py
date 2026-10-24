"""Literal26faf0 radius-clipped signed edge-tensor integration.

Numba accelerates the scalar traversal; fastmath is disabled. Source topology,
edge tensors and marks are explicit supplied arrays, not native cache handles.
"""
import numpy as np
from numba import njit


def guide_marks(vertex_count,edges,angles,embedded_pairs,mode=2,active=True):
    marks=np.zeros(vertex_count,dtype=np.bool_)
    if mode!=2 or not active:return marks
    if np.any(embedded_pairs[:,0]!=1):raise NotImplementedError('Nonvertex embedded guide mark policy')
    lookup={tuple(map(int,row)):i for i,row in enumerate(edges)}
    threshold=np.frombuffer(bytes.fromhex('8744e74a1857d63f'),'<f8')[0]
    for a,b in zip(embedded_pairs[:-1,1],embedded_pairs[1:,1]):
        edge=lookup.get(tuple(sorted((int(a),int(b)))))
        if edge is not None and abs(float(angles[edge]))>=threshold:marks[a]=True;marks[b]=True
    return marks


@njit(cache=False,fastmath=False)
def distance2(points,a,b):
    x=np.float32(points[a,0]-points[b,0]);y=np.float32(points[a,1]-points[b,1]);z=np.float32(points[a,2]-points[b,2])
    return np.float32(np.float32(np.float32(y*y)+np.float32(x*x))+np.float32(z*z))


@njit(cache=False,fastmath=False)
def integrate(points,edges,offsets,adjacency,tensors,angles,marks,radius):
    count=len(points);out=np.zeros((count,6),dtype=np.float64);discovered=np.zeros(count,dtype=np.int32)
    seen_vertices=np.full(count,-1,dtype=np.int64);seen_edges=np.full(len(edges),-1,dtype=np.int64);stack=np.empty(count,dtype=np.int32)
    r=np.float32(radius);r2=np.float32(r*r);factor=np.float32(np.float32(.31830987334251404)/r2)
    for seed in range(count):
        if marks[seed]:continue
        seen_vertices[seed]=seed;stack[0]=seed;size=1;accum=np.zeros(6,dtype=np.float64)
        while size:
            size-=1;a=stack[size]
            for k in range(offsets[a],offsets[a+1]):
                edge=adjacency[k]
                if seen_edges[edge]==seed:continue
                seen_edges[edge]=seed
                if distance2(points,edges[edge,0],edges[edge,1])==0:continue
                b=edges[edge,1] if edges[edge,0]==a else edges[edge,0];d2=distance2(points,seed,b);weight=np.float32(1)
                if d2<r2:
                    if seen_vertices[b]!=seed:
                        seen_vertices[b]=seed;discovered[seed]+=1
                        if not marks[b]:stack[size]=b;size+=1
                else:
                    da=np.float32(np.sqrt(distance2(points,seed,a)));db=np.float32(np.sqrt(d2))
                    weight=np.float32(np.float32(r-da)/np.float32(db-da))
                if angles[edge]!=0:
                    for channel in range(6):accum[channel]=accum[channel]+float(weight)*tensors[edge,channel]
        for channel in range(6):out[seed,channel]=accum[channel]*float(factor)
    return out,discovered


def prepare(geometry,edge_field,radii):
    topology=edge_field['topology'];marks=guide_marks(len(geometry['positions']),topology['edges'],edge_field['angles'],geometry['embeddedPairs'])
    values=[];counts=[]
    for radius in radii:
        if not np.isfinite(radius) or radius<=0:raise ValueError('Positive finite radius required')
        tensors,n=integrate(geometry['positions'],topology['edges'],topology['vertexEdgeOffsets'],topology['vertexEdges'],edge_field['tensors'],edge_field['angles'],marks,np.float32(radius));values.append(tensors);counts.append(n)
    return dict(tensors=np.asarray(values,dtype='<f8'),counts=np.asarray(counts,dtype='<i4'),marks=marks)
