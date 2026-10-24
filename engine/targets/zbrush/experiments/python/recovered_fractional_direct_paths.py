"""10c0a0 vertex/incident-edge append, absent attributes; qualify separately."""
import numpy as np
from recovered_vertex_neighbor_direct_paths import direct as previous
F=np.float32

def length(v):return F(np.sqrt(F(F(F(v[0]*v[0])+F(v[1]*v[1]))+F(v[2]*v[2]))))

def direct(record,start_point,start,end_point,end,positions,faces,topology,allow_face_chord=True):
    kind,index=map(int,start);endKind,target=map(int,end);edges=topology['edges']
    if kind==1 and endKind==2 and index in edges[target]:
        edge=target;point=F(end_point);a,b=positions[edges[edge]];denominator=length(F(a-b))
        if not denominator>0:raise NotImplementedError('Zero-length incident guide edge')
        #0fbec0 is a ratio of float32 lengths, capped above at1. It is not
        #a dot projection or squared-distance ratio, and has no lower clamp.
        parameter=F(min(F(1),F(length(F(point-a))/denominator)));branch='vertex-to-edge-append'
    elif kind==2 and endKind==1 and target in edges[index]:
        edge=index;point=positions[target];parameter=F(0 if int(edges[edge,0])==target else 1);branch='edge-to-vertex-append'
        if len(record['edges']) and int(record['edges'][-1])==edge and record['parameters'][-1]==parameter:
            return True,{k:v.copy() for k,v in record.items()},dict(branch='duplicate-edge-to-vertex-endpoint',edge=edge,parameter=float(parameter))
    else:return previous(record,start_point,start,end_point,end,positions,faces,topology,allow_face_chord)
    if len(record['attributes']):raise NotImplementedError('Direct source/record attribute channel')
    out={k:v.copy() for k,v in record.items()}
    if len(out['edges']):out['faces']=np.r_[out['faces'],np.int32(-1)].astype('<i4')
    out['edges']=np.r_[out['edges'],np.int32(edge)].astype('<i4');out['parameters']=np.r_[out['parameters'],parameter].astype('<f4');out['points']=np.vstack([out['points'],point]).astype('<f4')
    return True,out,dict(branch=branch,edge=edge,parameter=float(parameter))
