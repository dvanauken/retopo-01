"""10c0a0 vertex-neighbor append plus previously reviewed direct policies.

Explicit absent source/record attribute channel; native qualification separate.
"""
import numpy as np
from recovered_original_direct_paths import direct as ordinary
F=np.float32
def direct(record,start_point,start,end_point,end,positions,faces,topology,allow_face_chord=True):
    kind,index=map(int,start);endKind,target=map(int,end)
    if kind!=1 or endKind!=1:return ordinary(record,start_point,start,end_point,end,positions,faces,topology,allow_face_chord)
    out={k:v.copy() for k,v in record.items()};edges=topology['edges']
    matches=[]
    if target!=index:
        for edge in topology['vertexEdges'][topology['vertexEdgeOffsets'][target]:topology['vertexEdgeOffsets'][target+1]]:
            if index in edges[edge]:matches.append(int(edge))
    if not matches:return False,out,dict(branch='no-vertex-neighbor-edge')
    if len(matches)!=1:raise NotImplementedError('Multiple parallel vertex-neighbor edges')
    if len(out['attributes']):raise NotImplementedError('Direct source/record attributes')
    edge=matches[0];parameter=F(0 if int(edges[edge,0])==target else 1)
    if len(out['edges']) and int(out['edges'][-1])==edge and out['parameters'][-1]==parameter:return True,out,dict(branch='duplicate-vertex-neighbor-endpoint',edge=edge,parameter=float(parameter))
    if len(out['edges']):out['faces']=np.r_[out['faces'],np.int32(-1)].astype('<i4')
    out['edges']=np.r_[out['edges'],np.int32(edge)].astype('<i4');out['parameters']=np.r_[out['parameters'],parameter].astype('<f4');out['points']=np.vstack([out['points'],positions[target]]).astype('<f4')
    return True,out,dict(branch='vertex-neighbor-append',edge=edge,parameter=float(parameter))
