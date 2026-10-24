"""Ordinary18eec0 accepted-candidate weighted neighbor stencil, no flip repair."""
import numpy as np
from recovered_mesh_topology import build
F=np.float32


def step(positions,faces,weights):
    if len(weights)!=len(positions):raise NotImplementedError('Full per-vertex weight channel required')
    topology=build(len(positions),faces);edges=topology['edges'];out=positions.copy()
    for vertex,point in enumerate(positions):
        es=topology['vertexEdges'][topology['vertexEdgeOffsets'][vertex]:topology['vertexEdgeOffsets'][vertex+1]];weight=weights[vertex]
        if weight==0 or not len(es):continue
        total=np.zeros(3,dtype='<f4')
        for edge in es:
            a,b=edges[edge];neighbor=int(b if a==vertex else a);total=F(total+positions[neighbor])
        fraction=F(weight/F(len(es)));out[vertex]=F(F(F(F(1)-weight)*point)+F(fraction*total))
    return out
