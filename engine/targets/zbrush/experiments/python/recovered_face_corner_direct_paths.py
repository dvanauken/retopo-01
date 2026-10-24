"""10c0a0 absent-attribute face-to-corner append; other direct policies compose."""
import numpy as np
from recovered_fractional_direct_paths import direct as previous
F=np.float32

def direct(record,start_point,start,end_point,end,positions,faces,topology,allow_face_chord=True):
    kind,face=map(int,start);end_kind,vertex=map(int,end)
    if kind!=4 or end_kind!=1 or vertex not in faces[face]:return previous(record,start_point,start,end_point,end,positions,faces,topology,allow_face_chord)
    if len(record['attributes']):raise NotImplementedError('Face-corner direct attributes remain unqualified')
    corners=np.flatnonzero(np.asarray(faces[face])==vertex)
    if len(corners)!=1:raise NotImplementedError('Repeated-index face-corner direct policy')
    corner=int(corners[0]);edge=int(topology['faceEdges'].reshape(-1,3)[face,corner]);parameter=F(0 if int(topology['edges'][edge,0])==vertex else 1);out={k:v.copy() for k,v in record.items()}
    if len(out['edges']) and out['edges'][-1]==edge and out['parameters'][-1]==parameter:return True,out,dict(branch='duplicate-face-corner-endpoint',edge=edge,parameter=float(parameter))
    if len(out['edges']):out['faces']=np.r_[out['faces'],np.int32(face)].astype('<i4')
    out['edges']=np.r_[out['edges'],np.int32(edge)].astype('<i4');out['parameters']=np.r_[out['parameters'],parameter].astype('<f4');out['points']=np.vstack([out['points'],positions[vertex]]).astype('<f4')
    return True,out,dict(branch='face-to-corner-append',edge=edge,parameter=float(parameter),face=face,corner=corner)
