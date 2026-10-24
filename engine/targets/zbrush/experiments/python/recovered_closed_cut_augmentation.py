"""Reviewed300fd0 subset: closed identity parameter mesh, empty connector,
one nonseparating closed guide, no boundaries/symmetry/forced vertices.

Ordered dual-tree complement, primal leaf stripping and at most three ordered
triangle-shortcut passes. Multi-region/group admission remains guarded.
"""
from collections import deque
import numpy as np
from recovered_mesh_topology import build

def prepare(vertex_count,faces,guide_edges):
    tri=np.asarray(faces,dtype='<i4')
    if tri.ndim!=2 or tri.shape[1]!=3 or not len(tri):raise NotImplementedError('Nonempty triangle component required')
    top=build(vertex_count,tri);edges=top['edges'];off=top['edgeCornerOffsets'];corn=top['edgeCorners'];fe=top['faceEdges'].reshape(-1,3);vo=top['vertexEdgeOffsets'];ve=top['vertexEdges'];guide=np.zeros(len(edges),bool);ids=np.asarray(guide_edges,dtype='<i4')
    if not len(ids) or np.any(ids<0) or np.any(ids>=len(edges)) or len(set(ids.tolist()))!=len(ids):raise ValueError('Unique valid guide edge identities required')
    guide[ids]=True
    if not np.all(np.diff(off)==2):raise NotImplementedError('Closed manifold edges required')
    gd=np.bincount(edges[guide].ravel(),minlength=vertex_count)
    if not np.all((gd==0)|(gd==2)):raise NotImplementedError('Only simple closed guide groups')
    remaining=set(map(int,np.flatnonzero(gd)));queue=[min(remaining)];remaining.remove(queue[0])
    for v in queue:
        for e in ve[vo[v]:vo[v+1]]:
            if not guide[e]:continue
            a,b=edges[e];other=int(b if a==v else a)
            if other in remaining:remaining.remove(other);queue.append(other)
    if remaining:raise NotImplementedError('Only one guide group')
    # Unit float32 dual costs. FIFO insertion and local corner order break ties.
    parent=np.full(len(tri),-1,dtype='<i4');parent_edge=parent.copy();distance=np.full(len(tri),np.finfo('f4').max,dtype='<f4');parent[0]=0;distance[0]=0;queue=deque([0]);pending=np.zeros(len(tri),bool);pending[0]=True
    while queue:
        face=queue.popleft();pending[face]=False
        for e in fe[face]:
            if guide[e]:continue
            pair=corn[off[e]:off[e+1]]//3;other=int(pair[1] if pair[0]==face else pair[0]);value=np.float32(distance[face]+np.float32(1))
            if value<distance[other]:
                parent[other]=face;parent_edge[other]=e;distance[other]=value
                if not pending[other]:queue.append(other);pending[other]=True
    if np.any(parent<0):raise NotImplementedError('Guide-separated dual regions require group admission branch')
    mask=np.ones(len(edges),bool);mask[parent_edge[parent_edge>=0]]=False;tree_complement=mask.copy();degree=np.bincount(edges[mask].ravel(),minlength=vertex_count);queue=deque(np.flatnonzero(degree==1).tolist())
    while queue:
        vertex=queue.popleft()
        if degree[vertex]!=1:continue
        for edge in ve[vo[vertex]:vo[vertex+1]]:
            if not mask[edge]:continue
            a,b=edges[edge];other=int(b if a==vertex else a);mask[edge]=False;degree[vertex]=0;degree[other]-=1
            if degree[other]==1:queue.append(other)
            break
    pruned=mask.copy();passes=[];shortcuts=[]
    for iteration in range(3):
        changes=0
        # Native bit scan is dynamic: an inserted greater edge may run this pass.
        for edge in range(len(edges)):
            if not mask[edge]:continue
            for corner in corn[off[edge]:off[edge+1]]:
                face,k=divmod(int(corner),3);a=int(fe[face,(k+1)%3]);b=int(fe[face,(k+2)%3])
                if mask[a]==mask[b]:continue
                removed=a if mask[a] else b;added=b if mask[a] else a;shared=set(edges[edge].tolist())&set(edges[removed].tolist())
                if len(shared)!=1:raise ValueError('Triangle edge intersection')
                vertex=next(iter(shared))
                if degree[vertex]!=2:continue
                mask[edge]=False;mask[removed]=False;mask[added]=True;degree[vertex]=0;changes+=1;shortcuts.append([iteration,edge,removed,added,vertex]);break
        passes.append(mask.copy())
        if not changes:break
    return dict(cut=mask,parent=parent,parentEdge=parent_edge,distance=distance,treeComplement=tree_complement,pruned=pruned,shortcutPasses=np.asarray(passes),shortcuts=np.asarray(shortcuts,dtype='<i4').reshape(-1,5),guide=guide,topology=top)
