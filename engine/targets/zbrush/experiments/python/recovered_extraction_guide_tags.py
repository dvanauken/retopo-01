"""0x2a7cc0 mode-two source guide tags and ordinary disjoint source paths."""
import numpy as np
from recovered_embedded_guide_edges import collect

def build(curves,edges,vertex_offsets,vertex_edges,vertex_count):
    marked_vertices=np.zeros(vertex_count,dtype=bool);active=[]
    for curve in curves:
        if int(curve['mode'])!=2 or not curve['active']:continue
        pairs=curve['primaryPairs']
        for kind,index in pairs:
            if int(kind)==1 and int(index)!=-1:
                if not 0<=int(index)<vertex_count:raise ValueError('Invalid embedded vertex')
                marked_vertices[int(index)]=True
        active.append(dict(mode=2,active=True,primaryPairs=pairs,alternatePoints=[],alternatePairs=[]))
    sequence,_=collect(active,edges,vertex_offsets,vertex_edges);selected=sorted(set(sequence));marked_edges=np.zeros(len(edges),dtype=bool);marked_edges[selected]=True;degree={};encounter=[]
    for edge in selected:
        for v in edges[edge]:
            v=int(v)
            if v not in degree:degree[v]=0;encounter.append(v)
            degree[v]+=1
    if any(d>2 for d in degree.values()):raise ValueError('Branching extraction guide paths need separate qualification')
    remaining=set(selected);leaves=[v for v in encounter if degree[v]==1];paths=[]
    while leaves:
        vertex=leaves.pop();vs=[vertex];es=[]
        while True:
            edge=next((int(e) for e in vertex_edges[vertex_offsets[vertex]:vertex_offsets[vertex+1]] if int(e) in remaining),None)
            if edge is None:break
            remaining.remove(edge);es.append(edge);a,b=map(int,edges[edge]);vertex=b if a==vertex else a;vs.append(vertex)
            if degree[vertex]!=2:break
        if es:paths.append((es,vs))
    if remaining:raise ValueError('Closed extraction guide path policy remains unqualified')
    edge_offsets=[0];vertex_path_offsets=[0];edge_flat=[];vertex_flat=[];owner=np.full(len(edges),-1,dtype=np.int32);ordinal=np.full(len(edges),-1,dtype=np.int32);forward=np.zeros(len(edges),dtype=bool)
    for group,(es,vs) in enumerate(paths):
        edge_flat+=es;vertex_flat+=vs;edge_offsets.append(len(edge_flat));vertex_path_offsets.append(len(vertex_flat))
        for index,edge in enumerate(es):owner[edge]=group;ordinal[edge]=index;forward[edge]=vs[index]==int(edges[edge,0])
    return dict(vertices=marked_vertices,edges=marked_edges,selected=selected,edgeOffsets=edge_offsets,vertexOffsets=vertex_path_offsets,pathEdges=edge_flat,pathVertices=vertex_flat,owner=owner,ordinal=ordinal,forward=forward)
