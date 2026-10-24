"""Ordinary direct shared-face/chord handling; other positive branches guarded."""
import numpy as np
from probe_guide_walk_math import reference,norm
F=np.float32
PARALLEL=np.frombuffer(bytes.fromhex('f168e388b5f8e43e'),'<f8')[0]


def direct(record,start_point,start,end_point,end,positions,faces,topology,allow_face_chord=True):
    out={key:value.copy() for key,value in record.items()};kind,index=map(int,start);endKind,target=map(int,end);edges=topology['edges'];faceEdges=topology['faceEdges'].reshape(-1,3)
    if kind==endKind==4:
        if index==target:return True,out,dict(branch='same-face')
        common=[int(e) for e in faceEdges[index] if e in faceEdges[target]]
        if not allow_face_chord or not common:return False,out,dict(branch='not-shared-face-edge')
        if len(common)!=1:raise NotImplementedError('Multiple common face edges')
        edge=common[0];a,b=positions[edges[edge]].astype(float);startPoint=F(start_point).astype(float);delta=F(end_point).astype(float)-startPoint;size=norm(delta)
        if size==0:raise NotImplementedError('Coincident direct endpoints')
        direction=delta*(1/size);distance,s,t,parallel=reference(np.r_[startPoint,direction],np.r_[a,b],PARALLEL)
        if parallel:raise NotImplementedError('Direct parallel common-edge midpoint policy')
        #11a220 casts t and1-t independently from double before float products.
        point=F(F(F(b)*F(t))+F(F(a)*F(1-t)))
        if len(out['edges']):out['faces']=np.r_[out['faces'],np.int32(index)].astype('<i4')
        out['edges']=np.r_[out['edges'],np.int32(edge)].astype('<i4');out['parameters']=np.r_[out['parameters'],F(t)].astype('<f4');out['points']=np.vstack([out['points'],point]).astype('<f4')
        if len(out['attributes']):raise NotImplementedError('Present direct point attributes')
        return True,out,dict(branch='shared-face-edge',edge=edge,parameter=t,lineParameter=s)
    # Reject unqualified positive policies rather than treating them as a generic
    # negative. The actual original fixture exercises none of these positives.
    if kind==endKind==1:
        connected=any(target in edges[e] for e in topology['vertexEdges'][topology['vertexEdgeOffsets'][index]:topology['vertexEdgeOffsets'][index+1]])
        if connected:raise NotImplementedError('Direct vertex-neighbor append')
    if kind==4 and endKind==1 and target in faces[index]:raise NotImplementedError('Direct face-to-corner append')
    if kind==1 and endKind==2 and index in edges[target]:raise NotImplementedError('Direct vertex-to-edge append')
    if kind==2 and endKind==1 and target in edges[index]:raise NotImplementedError('Direct edge-to-vertex append')
    return False,out,dict(branch='no-default-direct-path')
