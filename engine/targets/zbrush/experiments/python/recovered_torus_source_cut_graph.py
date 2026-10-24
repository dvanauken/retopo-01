"""Original guided field through closed ordinary source seeds and connector cut.

No symmetry, boundary spans, special source classes, or marked-face cost bias.
Default source-cut augmentation is checked independently against final mask.
"""
from collections import deque
import numpy as np
from recovered_torus_guide_field import prepare as field
from recovered_source_singular_seeds import prepare as seeds
from recovered_alternate_vertex_path import lengths
from recovered_index_sort import sort_indices
from recovered_closed_cut_augmentation import prepare as augment
from recovered_cyclic_cut_path_enumeration import enumerate_paths
F=np.float32


def prepare(source,faces,target,drawn,guide_mode=2):
    own=field(source,faces,target,drawn,guide_mode);g=own['geometry'];ef=own['edgeField'];top=ef['topology'];a=own['angular'];s=seeds(g['positions'],g['faces'],ef['normals'],top,a['angles'],a['connections'],a['quarterTransitions']);edges=top['edges'];cost=lengths(g['positions'],edges);selectedGuides=own['constraints']['selectedEdges'];cost[selectedGuides]=F(cost[selectedGuides]*np.frombuffer(bytes.fromhex('abaaaa3e'),'<f4')[0]);n=len(g['positions']);distance=np.full(n,np.finfo(F).max,dtype='<f4');owner=np.full(n,-1,dtype='<i4');root=owner.copy();parent=owner.copy();queue=deque();pending=set();vo=top['vertexEdgeOffsets'];ve=top['vertexEdges']
    for i,vertex in enumerate(s['seeds']):
        v=int(vertex);distance[v]=0;owner[v]=i;root[v]=v;queue.append(v);pending.add(v)
    while queue:
        v=queue.popleft();pending.remove(v)
        for edge in ve[vo[v]:vo[v+1]]:
            x,y=map(int,edges[edge]);u=y if x==v else x;candidate=F(cost[edge]+distance[v])
            if candidate<distance[u]:
                distance[u]=candidate;owner[u]=owner[v];root[u]=root[v];parent[u]=edge
                if u not in pending:queue.append(u);pending.add(u)
    table={}
    for edge,(x,y) in enumerate(edges):
        if owner[x]<0 or owner[y]<0 or owner[x]==owner[y]:continue
        pair=tuple(sorted([int(owner[x]),int(owner[y])]));weight=F(F(distance[y]+distance[x])+cost[edge])
        if pair not in table or weight<table[pair][1]:table[pair]=(edge,weight)
    pairs=np.asarray(list(table),dtype='<i4').reshape(-1,2);candidateEdges=np.asarray([x[0] for x in table.values()],dtype='<i4');candidateCosts=np.asarray([x[1] for x in table.values()],dtype='<f4');labels=np.arange(len(s['seeds']));selected=[];selectedPairs=[];selectedCosts=[]
    for index in sort_indices(candidateCosts):
        x,y=labels[pairs[index]]
        if x==y:continue
        labels[labels==max(x,y)]=min(x,y);selected.append(int(candidateEdges[index]));selectedPairs.append(pairs[index]);selectedCosts.append(candidateCosts[index])
    cut=np.zeros(len(edges),dtype=bool)
    for edge in selected:
        cut[edge]=True
        for v in edges[edge]:
            visited=set();v=int(v)
            while parent[v]>=0:
                if v in visited:raise ValueError('Cyclic parent forest')
                visited.add(v);p=int(parent[v]);cut[p]=True;x,y=map(int,edges[p]);v=y if x==v else x
    augmentation=None;singular=s
    if not len(s['seeds']):
        if np.any(cut):raise RuntimeError('Unexpected seeded connector output')
        augmentation=augment(len(g['positions']),g['faces'],selectedGuides);cut=augmentation['cut']
        _,nodes=enumerate_paths(np.flatnonzero(cut),edges,vo,ve,[],[])
        if not nodes:raise NotImplementedError('Cut node fallback requires a positive node')
        s=dict(s,seeds=np.asarray(nodes[:1],dtype='<i4'),types=np.asarray([0],dtype='<i4'),flags=np.asarray([2],dtype='u1'),origin='296050 first cut-path node fallback, after empty27c100 singular seeds')
    own['singularSourceSeeds']=singular;own['cutAugmentation']=augmentation
    own['sourceSeeds']=s;own['sourceCutGraph']=dict(cut=cut,cost=cost,distance=distance,owner=owner,root=root,parent=parent,candidatePairs=pairs,candidateEdges=candidateEdges,candidateCosts=candidateCosts,selectedEdges=np.asarray(selected,dtype='<i4'),selectedPairs=np.asarray(selectedPairs,dtype='<i4'),selectedCosts=np.asarray(selectedCosts,dtype='<f4'))
    return own
