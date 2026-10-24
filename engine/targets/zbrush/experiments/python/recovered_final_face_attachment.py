"""103060 retain a final type4 point with source-face interval and edge sentinel."""
import numpy as np

def retain(record,projected_point,face):
    if len(record['attributes']):raise NotImplementedError('Final face attachment attributes remain unqualified')
    out={k:v.copy() for k,v in record.items()};point=np.asarray(projected_point,dtype='<f4')
    if not len(out['edges']):raise NotImplementedError('Final face attachment needs nonempty accumulated record')
    #005190 is coordinatewise float equality, including signed-zero equality.
    append=len(out['faces'])>0 and (int(out['faces'][-1])!=int(face) or not bool(np.all(out['points'][-1]==point)))
    if append:
        out['faces']=np.r_[out['faces'],np.int32(face)].astype('<i4');out['edges']=np.r_[out['edges'],np.int32(-1)].astype('<i4');out['parameters']=np.r_[out['parameters'],np.float32(0)].astype('<f4');out['points']=np.vstack([out['points'],point]).astype('<f4')
    return out,dict(appended=bool(append),face=int(face),scope='103060 nonempty/no-attribute final type4 attachment; copy projected endpoint, face interval, edge-1 and parameter0.')
