"""0x2a0c10 mark/weight preparation and0x2a02c0 source-path output ordering."""
import numpy as np
from recovered_index_sort import sort_indices
F=np.float32


def prepare(vertices,faces,metadata,tags):
    marked=np.zeros(len(vertices),dtype=bool)
    for i,(kind,index) in enumerate(metadata['attachments']):
        if kind==1:marked[i]=tags['vertices'][index]
        elif kind==2:marked[i]=tags['edges'][index]
    adjacent=[set() for _ in vertices]
    for row in faces:
        for a,b in zip(row,row[1:]+row[:1]):adjacent[a].add(b);adjacent[b].add(a)
    weights=metadata['relaxationWeights'].copy()
    for i in np.flatnonzero(marked):
        weight=weights[i];weights[i]=0
        if weight>0:
            for neighbor in adjacent[i]:
                if not marked[neighbor]:weights[neighbor]=min(F(1),F(F(weight/F(3))+weights[neighbor]))
    return marked,weights,adjacent


def length(vector):
    v=F(vector);return F(np.sqrt(F(F(v[0]*v[0]+v[1]*v[1])+v[2]*v[2])))


def collect(graph,vertices,metadata,marked,adjacent):
    g=graph;tags=g.tags;count=len(tags['edgeOffsets'])-1;ids=[[] for _ in range(count)];keys=[[] for _ in range(count)]
    edges=np.empty((len(g.cs),2),dtype='<i4')
    # Source edge stored endpoint orientation is part of the input topology.
    for face in range(len(g.tri)):
        for k,edge in enumerate(g.fe[face]):
            if g.cs[int(edge)][0]//3==face:edges[edge]=[g.tri[face,k],g.tri[face,(k+1)%3]]
    # Callers may supply canonical stored endpoints, distinct from first corner.
    if hasattr(g,'source_edges'):edges=g.source_edges
    vertex_edges=[[] for _ in g.xyz]
    for edge,(a,b) in enumerate(edges):vertex_edges[a].append(edge);vertex_edges[b].append(edge)
    if hasattr(g,'vertex_edges'):vertex_edges=g.vertex_edges
    for output in np.flatnonzero(marked):
        if not adjacent[output]:continue
        kind,index=metadata['attachments'][output]
        candidates=vertex_edges[index] if kind==1 else [int(index)] if kind==2 else []
        for edge in candidates:
            group=int(tags['owner'][edge])
            if group<0:continue
            a,b=edges[edge]
            if kind==1:fraction=F(0 if index==a else 1)
            else:fraction=min(F(1),F(length(F(vertices[output]-g.xyz[a]))/length(F(g.xyz[b]-g.xyz[a]))))
            if not tags['forward'][edge]:fraction=F(F(1)-fraction)
            ids[group].append(int(output));keys[group].append(F(F(tags['ordinal'][edge])+fraction))
    for group in range(count):
        order=sort_indices(keys[group]);ids[group]=[ids[group][i] for i in order];keys[group]=[keys[group][i] for i in order];a=tags['vertexOffsets'][group];b=tags['vertexOffsets'][group+1]
        if tags['pathVertices'][a]==tags['pathVertices'][b-1] and ids[group]:ids[group].append(ids[group][0]);keys[group].append(keys[group][0])
    return ids,keys
