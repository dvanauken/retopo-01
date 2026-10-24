"""15c020 ordinary disjoint two-triangle flips without duplicate new edges.

Geometry/index subset only. Attribute/corner-transfer tables, conflicting or
duplicate-edge repair and optional changed-vertex outputs remain separate.
"""
import numpy as np
from recovered_mesh_topology import build

def flip(vertex_count,triangles,selected_edges):
    tri=np.asarray(triangles,dtype='<i4');selected=np.asarray(selected_edges,dtype='<i4')
    if tri.ndim!=2 or tri.shape[1]!=3 or selected.ndim!=1 or len(set(map(int,selected)))!=len(selected):raise ValueError('Triangles and unique ordered selected edge IDs required')
    top=build(vertex_count,tri);ne=len(top['edges']);known={tuple(map(int,row)) for row in top['edges']};used=set();new=set();out=tri.copy();rows=[]
    for edge in selected:
        if not 0<=edge<ne:raise ValueError('Selected edge outside topology')
        begin,end=top['edgeCornerOffsets'][edge:edge+2];corners=top['edgeCorners'][begin:end]
        if len(corners)!=2:raise NotImplementedError('Ordinary two-face interior edges only')
        c0,c1=map(int,corners);f0,k0=divmod(c0,3);f1,k1=divmod(c1,3)
        if f0 in used or f1 in used:raise NotImplementedError('Shared-face/conflicting batch policies')
        a,b=int(tri[f0,(k0+2)%3]),int(tri[f1,(k1+2)%3]);key=tuple(sorted((a,b)))
        if a==b or key in known or key in new:raise NotImplementedError('Existing/duplicate new diagonal policy')
        if tri[f0,k0]!=tri[f1,(k1+1)%3] or tri[f1,k1]!=tri[f0,(k0+1)%3]:raise ValueError('Consistent oriented interior edge required')
        out[f0,k0]=b;out[f1,k1]=a;used.update([f0,f1]);new.add(key);rows.append(dict(edge=int(edge),corners=[c0,c1],newVertices=[b,a]))
    return out,rows
