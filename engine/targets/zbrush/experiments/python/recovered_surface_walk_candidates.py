"""Reviewed11a470 candidate corners and direct endpoint append policy."""
import numpy as np


def choose(start,end,positions,faces,topology):
    kind,index=map(int,start);endKind,target=map(int,end);flat=np.asarray(faces,dtype='<i4').ravel();edges=topology['edges'];corners=[]
    def nxt(corner):return corner+1 if corner%3!=2 else corner-2
    def first_vertex_edge(vertex):return int(topology['vertexEdges'][topology['vertexEdgeOffsets'][vertex]])
    def emit(edge,face,vertex):return dict(terminal=True,candidates=corners,append=dict(edge=int(edge),face=int(face),parameter=np.float32(0 if edges[edge,0]==vertex else 1),point=positions[vertex].copy()))
    def done():return dict(terminal=True,candidates=corners,append=None)
    if kind==4:
        if endKind==4 and index==target:return done()
        corners.extend([index*3+i for i in range(3)])
    elif kind==2:
        if endKind==1 and target in edges[index]:
            # The native direct branch indexes this incidence span with target;
            # preserve the reviewed indexing rather than substitute another face.
            face=int(topology['edgeCorners'][topology['edgeCornerOffsets'][target]])//3
            return emit(index,face,target)
        for corner in topology['edgeCorners'][topology['edgeCornerOffsets'][index]:topology['edgeCornerOffsets'][index+1]]:
            corner=int(corner);face=corner//3
            if endKind==4 and target==face:return done()
            a=nxt(corner);b=nxt(a);corners.extend([a,b])
            if endKind==1 and target==flat[b]:return emit(first_vertex_edge(target),face,target)
    elif kind==1:
        for corner in topology['vertexCorners'][topology['vertexCornerOffsets'][index]:topology['vertexCornerOffsets'][index+1]]:
            corner=int(corner);face=corner//3
            if endKind==4 and target==face:return done()
            candidate=nxt(corner);corners.append(candidate)
            if endKind==1 and target==flat[candidate]:return emit(first_vertex_edge(target),-1,target)
    else:raise NotImplementedError('Unknown surface attachment kind')
    return dict(terminal=False,candidates=corners,append=None)
