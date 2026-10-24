"""2a7cc0 mode-two tags for one simple closed existing-vertex guide.

Other pools retain the qualified leaf/junction producer and its guards.
"""
import numpy as np
from recovered_embedded_guide_edges import collect
from recovered_cyclic_cut_path_enumeration import enumerate_paths
from recovered_leaf_terminated_guide_tags import build as leaves
from recovered_closed_network_path_enumeration import enumerate_stack

def build(curves,edges,vertex_offsets,vertex_edges,vertex_count):
    active=[c for c in curves if int(c['mode'])==2 and c['active']]
    if len(active)>1 and all(len(c['primaryPairs'])>=4 and np.array_equal(c['primaryPairs'][0],c['primaryPairs'][-1]) for c in active):return network(active,edges,vertex_offsets,vertex_edges,vertex_count)
    if len(active)!=1:return leaves(curves,edges,vertex_offsets,vertex_edges,vertex_count)
    curve=active[0];pairs=np.asarray(curve['primaryPairs'])
    if pairs.shape[1:]!=(2,) or len(pairs)<4 or not np.array_equal(pairs[0],pairs[-1]):return leaves(curves,edges,vertex_offsets,vertex_edges,vertex_count)
    if np.any(pairs[:,0]!=1) or np.any(pairs[:,1]<0) or np.any(pairs[:,1]>=vertex_count):raise NotImplementedError('Closed existing-vertex guide required')
    marked_vertices=np.zeros(vertex_count,bool);marked_vertices[pairs[:,1]]=True;selected,_=collect([dict(curve,alternatePoints=[],alternatePairs=[])],edges,vertex_offsets,vertex_edges);selected=sorted(set(selected));degree=np.bincount(edges[selected].ravel(),minlength=vertex_count)
    if not selected or np.any((degree!=0)&(degree!=2)):raise NotImplementedError('One simple closed degree-two path required')
    paths,_=enumerate_paths(selected,edges,vertex_offsets,vertex_edges,[],[])
    if len(paths)!=1 or paths[0][1][0]!=paths[0][1][-1]:raise NotImplementedError('Single closed path required')
    es,vs=paths[0];marked_edges=np.zeros(len(edges),bool);marked_edges[selected]=True;owner=np.full(len(edges),-1,dtype='<i4');ordinal=owner.copy();forward=np.zeros(len(edges),bool)
    for k,edge in enumerate(es):owner[edge]=0;ordinal[edge]=k;forward[edge]=vs[k]==int(edges[edge,0])
    return dict(vertices=marked_vertices,edges=marked_edges,selected=selected,edgeOffsets=[0,len(es)],vertexOffsets=[0,len(vs)],pathEdges=es,pathVertices=vs,owner=owner,ordinal=ordinal,forward=forward)


def network(curves,edges,vertex_offsets,vertex_edges,vertex_count):
    vertices=np.zeros(vertex_count,bool)
    for curve in curves:
        pairs=np.asarray(curve['primaryPairs'])
        if pairs.ndim!=2 or pairs.shape[1]!=2 or np.any(pairs[:,0]!=1) or np.any(pairs[:,1]<0) or np.any(pairs[:,1]>=vertex_count):raise NotImplementedError('Closed network existing-vertex pairs required')
        vertices[pairs[:,1]]=True
    selected,_=collect([dict(c,alternatePoints=[],alternatePairs=[]) for c in curves],edges,vertex_offsets,vertex_edges);selected=sorted(set(selected));paths,_=enumerate_stack(selected,edges,vertex_offsets,vertex_edges)
    if not paths:raise NotImplementedError('Positive closed network required')
    marked=np.zeros(len(edges),bool);marked[selected]=True;owner=np.full(len(edges),-1,'<i4');ordinal=owner.copy();forward=np.zeros(len(edges),bool);edgeOffsets=[0];vertexOffsets=[0];pathEdges=[];pathVertices=[]
    for i,(es,vs) in enumerate(paths):
        pathEdges.extend(es);pathVertices.extend(vs);edgeOffsets.append(len(pathEdges));vertexOffsets.append(len(pathVertices))
        for j,edge in enumerate(es):owner[edge]=i;ordinal[edge]=j;forward[edge]=vs[j]==int(edges[edge,0])
    return dict(vertices=vertices,edges=marked,selected=selected,edgeOffsets=edgeOffsets,vertexOffsets=vertexOffsets,pathEdges=pathEdges,pathVertices=pathVertices,owner=owner,ordinal=ordinal,forward=forward)
