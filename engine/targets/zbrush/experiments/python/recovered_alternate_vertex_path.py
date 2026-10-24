"""Ordinary0fd6f0 sentinel/FIFO source-vertex fallback, literal native policies."""
from collections import deque
import numpy as np
from recovered_index_sort import sort_indices
F=np.float32


def distance(a,b):
    d=F(a-b);return F(np.sqrt(F(F(d[1]*d[1]+d[0]*d[0])+d[2]*d[2])))


def lengths(positions,edges):
    d=positions[edges[:,0]].astype(float)-positions[edges[:,1]].astype(float)
    return np.sqrt((d[:,0]*d[:,0]+d[:,1]*d[:,1])+d[:,2]*d[:,2]).astype('<f4')


def fallback(positions,faces,topology,start_point,start_pair,end_point,end_pair,edge_lengths=None):
    kind,index=map(int,start_pair);endKind,endIndex=map(int,end_pair);edges=topology['edges'];vo=topology['vertexEdgeOffsets'];ve=topology['vertexEdges'];count=len(positions);edge_lengths=lengths(positions,edges) if edge_lengths is None else edge_lengths
    def attached_vertices(k,i):
        if k==1:return [i]
        if k==2:return list(map(int,edges[i]))
        if k==4:return list(map(int,faces[i]))
        raise NotImplementedError('Unknown alternate path attachment kind')
    seeds=attached_vertices(endKind,endIndex);targets=attached_vertices(kind,index);cost=np.full(count,np.finfo(np.float32).max,dtype='<f4');previous=np.full(count,-1,dtype='<i4');queued=np.zeros(count,dtype=bool);queue=deque();limit=F(distance(F(start_point),F(end_point))*F(20));popped=0;relaxed=0
    for seed in seeds:
        if not queued[seed]:queue.append(seed);queued[seed]=True
        previous[seed]=-2;cost[seed]=F(0) if endKind==1 else distance(F(start_point),positions[seed])
    for target in targets:previous[target]=-3
    while queue:
        vertex=queue.popleft();queued[vertex]=False;popped+=1
        incident=ve[vo[vertex]:vo[vertex+1]];neighbors=[int(edges[e,1] if edges[e,0]==vertex else edges[e,0]) for e in incident];keys=[]
        for neighbor in neighbors:
            d=F(F(start_point)-positions[neighbor]);keys.append(F(F(d[1]*d[1]+d[0]*d[0])+d[2]*d[2]))
        for offset in sort_indices(keys):
            edge=int(incident[offset]);neighbor=neighbors[offset];candidate=F(edge_lengths[edge]+cost[vertex])
            if previous[neighbor]==-3:
                # Native target encounter replaces the current pruning limit.
                limit=candidate;continue
            if candidate<cost[neighbor] and candidate<limit:
                cost[neighbor]=candidate;previous[neighbor]=vertex;relaxed+=1
                if F(distance(F(start_point),positions[neighbor])+candidate)<limit and not queued[neighbor]:queue.append(neighbor);queued[neighbor]=True
        if popped>1000000:raise RuntimeError('Alternate graph traversal guard')
    for target in targets:
        for edge in ve[vo[target]:vo[target+1]]:
            neighbor=int(edges[edge,1] if edges[edge,0]==target else edges[edge,0])
            if previous[neighbor]==-2 or previous[neighbor]>=0:
                candidate=F(edge_lengths[edge]+cost[neighbor])
                if candidate<cost[target]:cost[target]=candidate;previous[target]=neighbor
    selected=-1
    if len(targets)==1:selected=targets[0]
    else:
        best=F(np.finfo(np.float32).max)
        for target in targets:
            if previous[target]>=0:
                candidate=F(distance(F(start_point),positions[target])+cost[target])
                if candidate<best:best=candidate;selected=target
    ids=[]
    if selected>=0:
        if kind!=1:ids.append(selected)
        cursor=int(previous[selected])
        while cursor!=-2:
            if cursor<0 or len(ids)>count:ids=[];selected=-1;break
            ids.append(cursor);cursor=int(previous[cursor])
    outEdges=[];parameters=[]
    for vertex in ids:
        edge=int(ve[vo[vertex]]);outEdges.append(edge);parameters.append(F(0 if edges[edge,0]==vertex else 1))
    return dict(status=int(selected>=0),edges=np.asarray(outEdges,dtype='<i4'),faces=np.full(len(ids),-1,dtype='<i4'),parameters=np.asarray(parameters,dtype='<f4'),points=positions[ids].copy().reshape(-1,3),diagnostic=dict(poppedVertices=popped,relaxedEdges=relaxed,finalLimit=float(limit),seeds=seeds,targets=targets,selected=selected,vertexPath=ids))
