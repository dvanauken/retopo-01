"""164320 closed triangle fan circular-list splice and native duplicate order."""
import numpy as np


def prepare(vertex_count,triangles,topology,cut):
    edges=topology['edges'];eo=topology['edgeCornerOffsets'];ec=topology['edgeCorners'];vo=topology['vertexCornerOffsets'];vc=topology['vertexCorners'];veo=topology['vertexEdgeOffsets'];ve=topology['vertexEdges']
    if len(cut)!=len(edges) or np.any(np.diff(eo)!=2):raise NotImplementedError('Closed two-sided triangle fan branch only')
    counts=np.zeros(vertex_count,dtype=int);vertices=[]
    #164320 appends a split candidate when its second selected edge is seen.
    for edge in np.flatnonzero(cut):
        for vertex in edges[edge]:
            if counts[vertex]==1:vertices.append(int(vertex))
            counts[vertex]+=1
    out=triangles.copy().reshape(-1);duplicates=[];detail=[]
    for vertex in vertices:
        corners=vc[vo[vertex]:vo[vertex+1]];slot={int(c)//3:i for i,c in enumerate(corners)};count=len(corners);following=list(range(count));previous=list(range(count))
        for edge in ve[veo[vertex]:veo[vertex+1]]:
            if cut[edge]:continue
            a,b=map(int,ec[eo[edge]:eo[edge+1]]//3);i,j=slot[a],slot[b];pi,pj=previous[i],previous[j];following[pi]=j;previous[j]=pi;following[pj]=i;previous[i]=pj
        seen=set();fans=[]
        for seed in range(count):
            if seed in seen:continue
            walk=[];current=seed
            while current not in seen:
                seen.add(current);walk.append(current);current=following[current]
            if current!=seed:raise ValueError('Circular fan splice did not close at seed')
            fans.append(walk)
        for fan in fans[1:]:
            index=vertex_count+len(duplicates);duplicates.append(vertex)
            for i in fan:out[corners[i]]=index
        detail.append(dict(vertex=vertex,fanSizes=[len(f) for f in fans]))
    return dict(triangles=out.reshape(-1,3).astype('<i4'),sourceIds=np.r_[np.arange(vertex_count,dtype='<i4'),np.asarray(duplicates,dtype='<i4')],duplicates=np.asarray(duplicates,dtype='<i4'),splitVertices=np.asarray(vertices,dtype='<i4'),fans=detail)
