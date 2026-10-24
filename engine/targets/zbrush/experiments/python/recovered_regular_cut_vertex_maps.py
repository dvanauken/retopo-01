"""Ordinary nonintersecting prepared paths: append fractional points, collapse runs.

This constructs positions/maps only; triangle replacement and prepass are separate.
Rejects interior/free attachments and repeated fractional edge positions.
"""
import numpy as np


def construct(positions,edges,paths):
    result=[p.copy() for p in positions];mapsA=[];mapsB=[];fractional=set()
    for path in paths:
        mapped=[];indices=[];previous=-1
        for index,(point,edge,t) in enumerate(zip(path['points'],path['edges'],path['parameters'])):
            if edge<0 or edge>=len(edges) or not 0<=t<=1:raise NotImplementedError('Unsupported free/interior/out-of-range cut attachment')
            if t in (0,1):vertex=int(edges[int(edge),int(t)])
            else:
                key=(int(edge),np.float32(t).tobytes())
                if key in fractional:raise NotImplementedError('Repeated fractional cut attachment requires shared-point policy')
                fractional.add(key);vertex=len(result);result.append(point.copy())
            if vertex!=previous:mapped.append(vertex);indices.append(index)
            previous=vertex
        mapsA.append(np.asarray(mapped,dtype='<i4'));mapsB.append(np.asarray(indices,dtype='<i4'))
    return np.asarray(result,dtype='<f4'),mapsA,mapsB
