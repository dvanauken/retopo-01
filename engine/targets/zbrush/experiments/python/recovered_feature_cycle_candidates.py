"""260290 initial angular candidates and disconnected degree-two cycles only.

This does NOT implement subsequent path-metric rejection/merging/classification.
Candidate vertex union is not a generally qualified final feature-lock mask.
"""
import math
import numpy as np
from recovered_conditioning_measures import produce
F=np.float32
def prepare(positions,faces,minimum_angle=F(math.pi/6),excluded_edges=None):
    g=produce(positions,faces);top=g['topology'];edges=top['edges'];ne=len(edges);excluded=np.zeros(ne,bool) if excluded_edges is None else np.asarray(excluded_edges,dtype=bool)
    if excluded.shape!=(ne,) or not np.isfinite(minimum_angle) or not 0<float(minimum_angle)<math.pi:raise ValueError('Finite angular threshold and full excluded-edge shape required')
    selected=(g['edgeAngles']>=F(minimum_angle))&~excluded;remaining=set(map(int,np.flatnonzero(selected)));degree=np.bincount(edges[selected].reshape(-1),minlength=len(positions));vo=top['vertexEdgeOffsets'];ve=top['vertexEdges'];paths=[]
    if np.any((degree!=0)&(degree!=2)):raise NotImplementedError('Initial feature graph is not a union of closed degree-two cycles')
    while remaining:
        first=min(remaining);start=int(edges[first,0]);vertex=start;path=[];vertices=[start]
        while True:
            edge=next((int(e) for e in ve[vo[vertex]:vo[vertex+1]] if int(e) in remaining),None)
            if edge is None:raise ValueError('Unexpected open feature candidate')
            remaining.remove(edge);path.append(edge);x,y=map(int,edges[edge]);vertex=y if x==vertex else x;vertices.append(vertex)
            if vertex==start:break
            if len(path)>ne:raise ValueError('Feature cycle traversal bound')
        paths.append((path,vertices))
    eo=[0];po=[0]
    for path,vertices in paths:eo.append(eo[-1]+len(path));po.append(po[-1]+len(vertices))
    return dict(candidateEdges=selected,candidateVertices=degree>0,edgeOffsets=np.asarray(eo,dtype='<i4'),edgeIds=np.asarray([e for p,v in paths for e in p],dtype='<i4'),vertexOffsets=np.asarray(po,dtype='<i4'),vertexIds=np.asarray([i for p,v in paths for i in v],dtype='<i4'),threshold=F(minimum_angle),admissionPolicyImplemented=False)
