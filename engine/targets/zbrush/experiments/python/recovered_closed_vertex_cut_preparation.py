"""Bounded255b10 identity branch for one simple closed existing-vertex loop.

No fractional points/face intervals/attributes/repeated interior vertices are
accepted on the closed branch. Open paths use the earlier guarded policy.
"""
import numpy as np
from recovered_open_cut_preparation import prepare as open_prepare
def prepare(vertices,edges,paths,fraction=np.float32(.05),reset_positions=True):
    def endpoints(path):
        if any(int(e)<0 or int(e)>=len(edges) or t not in (0,1) for e,t in zip(path['edges'],path['parameters'])):return None
        return [int(edges[int(e),int(t)]) for e,t in zip(path['edges'],path['parameters'])]
    closed=[]
    for p in paths:
        ids=endpoints(p);closed.append(ids is not None and len(ids)>2 and ids[0]==ids[-1])
    if not any(closed):return open_prepare(vertices,edges,paths,fraction,reset_positions)
    if len(paths)!=1 or not closed[0]:raise NotImplementedError('Mixed closed/open or multiple closed cut preparation')
    p=paths[0];ids=endpoints(p);count=len(ids)
    if count<4 or len(set(ids[:-1]))!=count-1:raise NotImplementedError('Repeated/backtracking closed cut vertices')
    if any(len(p[k])!=count for k in ['points','edges','parameters']) or len(p['faces'])!=count-1:raise ValueError('Inconsistent closed path channels')
    if len(p['attributes']) or np.any(p['faces']!=-1):raise NotImplementedError('Closed face intervals or attributes')
    if np.asarray(p['points'],dtype='<f4').tobytes()!=np.asarray(vertices[ids],dtype='<f4').tobytes():raise NotImplementedError('Moved closed cut endpoints')
    lookup={tuple(map(int,e)) for e in edges}
    if any(tuple(sorted((a,b))) not in lookup for a,b in zip(ids[:-1],ids[1:])):raise NotImplementedError('Nonadjacent closed cut vertices')
    # All parameters already0/1; no fractional relocation, triple reduction or
    # propagation can change this simple existing-edge cycle.
    return vertices.copy(),[{k:v.copy() for k,v in p.items()}],[],[dict(points=count,requests=0,closedExistingVertexLoop=True,scope='Simple closed vertex identity subset only.')]
