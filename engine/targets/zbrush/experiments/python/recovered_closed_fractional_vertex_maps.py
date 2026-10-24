"""2567b0 ordinary closed fractional point allocation and raw compacted maps.

Reuse the first allocated point only for the repeated closed final descriptor;
other repeated fractional positions remain guarded. Topological path repair is
separate and must consume independently produced final cut connectivity.
"""
import numpy as np
from recovered_regular_cut_vertex_maps import construct as previous

def fractional_closed(p):
    e=p['edges'];t=p['parameters']
    return len(e)>2 and e[0]>=0 and e[0]==e[-1] and t[0] not in (0,1) and t[0]==t[-1]

def construct(positions,edges,paths):
    if not any(fractional_closed(p) for p in paths):return previous(positions,edges,paths)
    result=[p.copy() for p in positions];maps=[];starts=[];fractional=set()
    for p in paths:
        ids=[];indices=[];first=None;last=-1;closed=fractional_closed(p)
        if len(p['attributes']):raise NotImplementedError('Closed fractional allocation attributes remain unqualified')
        for i,(point,edge,t) in enumerate(zip(p['points'],p['edges'],p['parameters'])):
            if not 0<=edge<len(edges) or not 0<=t<=1:raise NotImplementedError('Ordinary source-edge allocation only')
            if t in (0,1):vertex=int(edges[int(edge),int(t)])
            elif closed and i==len(p['parameters'])-1:vertex=first
            else:
                key=(int(edge),np.float32(t).tobytes())
                if key in fractional:raise NotImplementedError('Nonclosing repeated fractional allocation policy remains unqualified')
                fractional.add(key);vertex=len(result);result.append(point.copy())
            if i==0:first=vertex
            if vertex!=last:ids.append(vertex);indices.append(i)
            last=vertex
        maps.append(np.asarray(ids,'<i4'));starts.append(np.asarray(indices,'<i4'))
    return np.asarray(result,'<f4'),maps,starts
