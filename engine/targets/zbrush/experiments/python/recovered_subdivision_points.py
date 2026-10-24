"""Ordinary24d0c0 strict long-edge marks and ordered float midpoint vertices."""
import numpy as np
from recovered_mesh_topology import build
F=np.float32


def produce(positions,faces,threshold):
    topology=build(len(positions),faces);edges=topology['edges'];delta=F(positions[edges[:,0]]-positions[edges[:,1]]);square=F(F(F(delta[:,0]*delta[:,0])+F(delta[:,1]*delta[:,1]))+F(delta[:,2]*delta[:,2]));selected=np.flatnonzero(square>F(F(threshold)*F(threshold))).astype('<i4');points=F(F(positions[edges[selected,0]]+positions[edges[selected,1]])*F(.5));mapping=np.full(len(edges),-1,dtype='<i4');mapping[selected]=np.arange(len(positions),len(positions)+len(selected),dtype='<i4');result=np.concatenate([positions,points],axis=0)
    return result,selected,mapping,topology
