"""Ordinary open prepared paths: fractional queue, shared-edge collapse, propagation.

Closed paths and the face-conditioned triple reduction are explicitly unsupported.
"""
import numpy as np
F=np.float32


def prepare(vertices,edges,paths,fraction=F(.05),reset_positions=True):
    original=vertices.copy();result=[];requests=[];diagnostics=[];lookup={tuple(sorted(map(int,e))):i for i,e in enumerate(edges)}
    for source in paths:
        path={key:value.copy() for key,value in source.items()};points=path['points'];ids=path['edges'];t=path['parameters'];count=len(t)
        if count!=len(ids) or count!=len(points) or len(path['faces'])!=count-1:raise ValueError('Inconsistent open path channels')
        def endpoint(index):
            edge=int(ids[index]);value=t[index]
            return int(edges[edge,int(value)]) if edge>=0 and value in (0,1) else -1
        initialRequests=len(requests);upper=F(F(1)-fraction)
        for i,(edge,value) in enumerate(zip(ids,t)):
            if edge<0:continue
            if not edge<len(edges) or not 0<=value<=1:raise ValueError('Invalid source edge attachment')
            if 0<value<fraction:t[i]=0.;vertex=int(edges[edge,0])
            elif upper<value<1:t[i]=1.;vertex=int(edges[edge,1])
            else:continue
            requests.append((vertex,points[i].copy()))
            if reset_positions:points[i]=original[vertex]
        if count>2 and ((endpoint(0)>=0 and endpoint(0)==endpoint(-1)) or (ids[0]>=0 and ids[0]==ids[-1] and t[0]==t[-1])):raise NotImplementedError('Closed path preparation policy')
        previous=-1;previousIndex=-1;collapses=[]
        for i in range(count):
            vertex=endpoint(i)
            if vertex<0:continue
            shared=lookup.get(tuple(sorted((previous,vertex)))) if previous>=0 and previous!=vertex else None
            if shared is not None and i>previousIndex+1 and bool((ids[previousIndex+1:i]==shared).all()):
                # Native255b10 writes literal0, not an orientation-derived endpoint.
                t[previousIndex+1:i]=0.;collapses.append(dict(first=previousIndex,last=i,edge=shared))
            previous,previousIndex=vertex,i
        for i in range(1,count-1):
            if ids[i-1]>=0 and ids[i-1]==ids[i]==ids[i+1]:raise NotImplementedError('Face-conditioned triple-edge reduction must be qualified separately')
        passes=0;propagated=0
        for _ in range(5):
            changed=False;passes+=1
            for i in range(1,count-1):
                vertex=endpoint(i)
                if vertex<0 or min(ids[i-1],ids[i+1])<0:continue
                for j in (i-1,i+1):
                    if t[j] in (0,1):continue
                    a,b=edges[ids[j]]
                    if a==vertex:t[j]=0.;changed=True;propagated+=1
                    elif b==vertex:t[j]=1.;changed=True;propagated+=1
            if not changed:break
        result.append(path);diagnostics.append(dict(points=count,requests=len(requests)-initialRequests,sharedEdgeCollapses=collapses,propagationPasses=passes,propagatedParameters=propagated))
    updated=original.copy()
    for vertex,point in requests:updated[vertex]=point
    return updated,result,requests,diagnostics
