"""Reviewed132160 and132580 opposite-neighbor relaxation candidates."""
import numpy as np
F=np.float32


def length_yxz(vector):
    v=F(vector);return F(np.sqrt(F(F(F(v[1]*v[1])+F(v[0]*v[0]))+F(v[2]*v[2]))))


def clamped_lengths(positions,vertex,neighbors,edge_ids,minimum,maximum):
    return [F(max(minimum[e],min(maximum[e],length_yxz(F(positions[n]-positions[vertex]))))) for n,e in zip(neighbors,edge_ids)]


def field_candidate(positions,edges,vertex,neighbors,edge_ids,minimum,maximum,directions):
    if any(not np.any(directions[e]!=0) for e in edge_ids):return positions[vertex].copy()
    lengths=clamped_lengths(positions,vertex,neighbors,edge_ids,minimum,maximum);targets=[]
    for n,e,length in zip(neighbors,edge_ids,lengths):
        delta=F(directions[e]*length);targets.append(F(positions[n]-delta) if edges[e,0]==vertex else F(delta+positions[n]))
    return F(F(targets[0]+targets[1])*F(.5))


def balanced_candidate(positions,vertex,neighbors,edge_ids,minimum,maximum):
    a,b=clamped_lengths(positions,vertex,neighbors,edge_ids,minimum,maximum);weight=F(a/F(b+a));other=F(F(1)-weight)
    return F(F(positions[neighbors[0]]*other)+F(positions[neighbors[1]]*weight))
