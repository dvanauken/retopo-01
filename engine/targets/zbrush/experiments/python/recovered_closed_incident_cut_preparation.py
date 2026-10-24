"""255b10 closed existing-edge runs with interior fractional samples.

Only no-attribute/no-face-interval, no endpoint relocation, fully collapsed
simple loops are admitted. Open and endpoint-only paths use earlier policies.
"""
import numpy as np
from recovered_closed_vertex_cut_preparation import prepare as previous
from recovered_cyclic_fractional_cut_preparation import prepare as cyclic_prepare
from recovered_mixed_descriptor_cut_preparation import prepare as mixed_prepare
F=np.float32

def prepare(vertices,edges,paths,fraction=F(.05),reset_positions=True):
    def fractional_closed(path):
        ids=path['edges'];t=path['parameters']
        return len(ids)>2 and ids[0]>=0 and ids[0]==ids[-1] and t[0] not in (0,1) and t[0]==t[-1]
    if any(fractional_closed(path) for path in paths):
        if any(np.any(p['edges']<0) for p in paths):return mixed_prepare(vertices,edges,paths,fraction,reset_positions)
        return cyclic_prepare(vertices,edges,paths,fraction,reset_positions)
    if len(paths)>1:
        def closed_endpoint_record(path):
            ids=path['edges'];t=path['parameters']
            return len(ids)>2 and t[0] in (0,1) and t[-1] in (0,1) and 0<=ids[0]<len(edges) and 0<=ids[-1]<len(edges) and edges[int(ids[0]),int(t[0])]==edges[int(ids[-1]),int(t[-1])]
        if not all(closed_endpoint_record(p) for p in paths):return previous(vertices,edges,paths,fraction,reset_positions)
        prepared=[];details=[]
        for path in paths:
            updated,local,requests,diagnostic=prepare(vertices,edges,[path],fraction,reset_positions)
            if requests or updated.tobytes()!=vertices.tobytes() or len(local)!=1 or not all(d.get('closedIncidentEdgeLoop',d.get('closedExistingVertexLoop',False)) for d in diagnostic):raise NotImplementedError('Pooled closed paths require independently unchanged source and no relocation')
            prepared.extend(local);details.extend(dict(d,pooledNoRelocation=True) for d in diagnostic)
        return vertices.copy(),prepared,[],details
    if not any(np.any((p['parameters']!=0)&(p['parameters']!=1)) for p in paths):return previous(vertices,edges,paths,fraction,reset_positions)
    if len(paths)!=1:return previous(vertices,edges,paths,fraction,reset_positions)
    source=paths[0];ids=source['edges'];t=source['parameters'];count=len(t)
    def endpoint(i):return int(edges[int(ids[i]),int(t[i])]) if ids[i]>=0 and t[i] in (0,1) else -1
    if count<4 or endpoint(0)<0 or endpoint(0)!=endpoint(-1):return previous(vertices,edges,paths,fraction,reset_positions)
    if len(source['attributes']):raise NotImplementedError('Closed incident cut attributes')
    for i in np.flatnonzero(source['faces']!=-1):
        if int(source['faces'][i])<0 or i!=count-2 or endpoint(i)<0 or endpoint(i)!=endpoint(i+1) or source['points'][i].tobytes()!=source['points'][i+1].tobytes():raise NotImplementedError('Closed nondegenerate or nonterminal face interval')
    if len(source['points'])!=count or len(ids)!=count or len(source['faces'])!=count-1:raise ValueError('Inconsistent closed incident cut channels')
    if np.any(ids<0) or np.any(ids>=len(edges)) or np.any(t<0) or np.any(t>1):raise ValueError('Closed incident edge/parameter range')
    fractional=(t!=0)&(t!=1)
    if np.any(fractional&((t<fraction)|(t>F(F(1)-fraction)))):raise NotImplementedError('Closed fractional relocation request')
    path={k:v.copy() for k,v in source.items()};t=path['parameters'];lookup={tuple(sorted(map(int,e))):i for i,e in enumerate(edges)};last=-1;last_index=-1;collapses=[]
    #The native pass walks the repeated endpoint too, so closing intervals are
    #handled by the linear loop. Interior same-edge parameters become literal0.
    for i in range(count):
        vertex=endpoint(i)
        if vertex<0:continue
        shared=lookup.get(tuple(sorted((last,vertex)))) if last>=0 and last!=vertex else None
        if shared is not None and i>last_index+1 and bool((ids[last_index+1:i]==shared).all()):
            t[last_index+1:i]=0;collapses.append(dict(first=last_index,last=i,edge=shared))
        last,last_index=vertex,i
    if np.any((t!=0)&(t!=1)):raise NotImplementedError('Uncollapsed closed fractional guide requires cyclic propagation/triple policy')
    mapped=[int(edges[int(e),int(value)]) for e,value in zip(ids,t)];runs=[mapped[0]]
    for vertex in mapped[1:]:
        if vertex!=runs[-1]:runs.append(vertex)
    if len(runs)<4 or runs[0]!=runs[-1] or len(set(runs[:-1]))!=len(runs)-1:raise NotImplementedError('Non-simple closed collapsed vertex cycle')
    if any(tuple(sorted((a,b))) not in lookup for a,b in zip(runs[:-1],runs[1:])):raise NotImplementedError('Nonadjacent closed collapsed vertices')
    return vertices.copy(),[path],[],[dict(points=count,requests=0,closedIncidentEdgeLoop=True,sharedEdgeCollapses=collapses,remainingFractional=0,scope='No relocation/face intervals/attributes; complete existing-edge interior runs collapse, then no fractional propagation remains. Map compaction is a distinct downstream operator.')]
