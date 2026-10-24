"""2567b0 post-cut common-new-neighbor guide repair; general path fallback guarded."""
import numpy as np
from recovered_mesh_topology import build
from recovered_fractional_direct_paths import length
F=np.float32

def repair(positions,faces,maps,original_count):
    top=build(len(positions),np.asarray(faces,'<i4'));edges=top['edges'];lookup={tuple(sorted(map(int,e))) for e in edges};vo=top['vertexEdgeOffsets'];ve=top['vertexEdges'];result=[];insertions=[]
    for ci,source in enumerate(maps):
        path=list(map(int,source));i=1
        while i<len(path):
            a,b=path[i-1:i+1]
            if a==b:raise NotImplementedError('Repeated adjacent repaired guide point')
            if tuple(sorted((a,b))) not in lookup:
                chosen=-1;best=np.finfo(F).max
                for edge in ve[vo[a]:vo[a+1]]:
                    x,y=map(int,edges[edge]);v=y if x==a else x
                    if v<original_count or tuple(sorted((v,b))) not in lookup:continue
                    score=F(length(F(positions[b]-positions[v]))+length(F(positions[v]-positions[a])))
                    if score<best:chosen=v;best=score
                if chosen<0:raise NotImplementedError('2567b0 general2ea0e0 repaired guide path fallback remains unqualified')
                path.insert(i,chosen);insertions.append(dict(curve=ci,index=i,first=a,last=b,vertex=chosen,score=float(best)));i+=1
            i+=1
        result.append(np.asarray(path,'<i4'))
    return result,insertions
