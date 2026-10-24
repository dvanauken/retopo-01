"""Source-produced primary mesh through the guarded live detail cap profile.

Simple unprotected loops, balanced four-loop handling, supported polygon/new
point rewrite and two Jacobi iterations. General boundary collapse/splitting,
protected vertices, cap paths/options and valence-two cleanup remain guarded.
"""
import numpy as np
from recovered_long_cycle_frontier import Driver
from recovered_materialization_metadata import build
from recovered_balanced_boundary_cap import cap
from recovered_polygon_replacement import rewrite
from recovered_cap_new_vertex_smoothing import smooth
from recovered_mesh_topology import build as topology
F=np.float32
def prepare(graph):
    driver=Driver(graph);vertices,faces=driver.run();metadata=build(graph);base=len(vertices)
    if metadata['protected'].any():raise NotImplementedError('Protected output topology')
    faces,loops,boundaryEvents=cap(vertices,faces,metadata['protected'])
    points,faces,provenance,events=rewrite(vertices,faces,1);cache=topology(len(points),faces);cornerFaces=np.repeat(np.arange(len(faces)),[len(row) for row in faces])
    for vertex in range(len(points)):
        a,b=map(int,cache['vertexEdgeOffsets'][vertex:vertex+2]);c,d=map(int,cache['vertexCornerOffsets'][vertex:vertex+2]);edges=cache['vertexEdges'][a:b]
        if b-a==2 and d-c==2 and all(cache['edgeCornerOffsets'][e+1]-cache['edgeCornerOffsets'][e]==2 for e in edges) and all(len(faces[cornerFaces[k]])==4 for k in cache['vertexCorners'][c:d]):raise NotImplementedError('General valence-two cleanup composition')
    points,history,_=smooth(points,faces,base,2,.5);count=len(points)-base
    if len(provenance['offsets'])!=count+1:raise ValueError('One provenance interval per new point required')
    # Actual root2ad950 appends scalars, zero-initializes new attachment pairs
    # through0ecfe0, and fills new face/neighbor IDs with-1. This does not assign
    # an invented source attachment to a cap-created point.
    weights=list(metadata['relaxationWeights'])
    for a,b in zip(provenance['offsets'][:-1],provenance['offsets'][1:]):
        denominator=F(0);last=F(0)
        for j in range(a,b):
            index=int(provenance['indices'][j]);w=provenance['weights'][j]
            if not 0<=index<len(weights):raise ValueError('Unavailable provenance scalar dependency')
            denominator=F(denominator+w);last=F(w*weights[index])
        weights.append(F(last/denominator) if denominator!=0 else F(0))
    metadata['relaxationWeights']=np.asarray(weights,dtype='<f4')
    if count:
        metadata['attachments']=np.concatenate([metadata['attachments'],np.zeros((count,2),dtype='<i4')])
        metadata['sourceFaces']=np.r_[metadata['sourceFaces'],np.full(count,-1,dtype='<i4')]
        metadata['neighbors']=np.concatenate([metadata['neighbors'],np.full((4,count),-1,dtype='<i4')],axis=1)
        for key in ['protected','boundary']:metadata[key]=np.r_[metadata[key],np.zeros(count,dtype=bool)]
    trace=dict(longCycleRejections=driver.longCycleRejections,rejected=False,boundaryLoops=loops,boundaryEvents=boundaryEvents,operations=events,originalCount=base,newPointCount=count,globalProvenance=provenance,smoothingIterations=len(history),scope='Guarded simple/balanced-loop detail cap geometry and root metadata resizing; not all cap/boundary/attribute options.')
    return points,faces,metadata,trace
