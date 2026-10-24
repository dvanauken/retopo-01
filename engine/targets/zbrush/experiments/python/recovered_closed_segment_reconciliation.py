"""103060 closure for absent-attribute ordinary closed triangle-edge records."""
import numpy as np
F=np.float32

def reconcile(record,topology):
    out={k:v.copy() for k,v in record.items()}
    if len(out['edges'])<1:return out,dict(branch='empty')
    first,last=int(out['edges'][0]),int(out['edges'][-1]);start,end=out['parameters'][0],out['parameters'][-1]
    if first==last:
        if start!=end and float(abs(F(start-end)))<1e-6:
            out['parameters'][-1]=start;out['points'][-1]=out['points'][0];end=start
        if start==end:return out,dict(branch='same-edge-closed')
    if min(first,last)<0:return out,dict(branch='free-endpoint')
    off=topology['edgeCornerOffsets'];corn=topology['edgeCorners'];a=corn[off[first]:off[first+1]]//3;b=corn[off[last]:off[last+1]]//3
    if len(a)!=2 or len(b)!=2:raise NotImplementedError('Closed two-face triangle closure boundary')
    #1a9860 prefers matching second-edge face0 before second-edge face1.
    common=next((int(y) for y in b if y in a),None)
    if common is None:return out,dict(branch='no-common-face')
    if len(out['attributes']):raise NotImplementedError('Present closed endpoint attribute copying')
    out['faces']=np.r_[out['faces'],np.int32(common)].astype('<i4');out['edges']=np.r_[out['edges'],np.int32(first)].astype('<i4');out['parameters']=np.r_[out['parameters'],F(start)].astype('<f4');out['points']=np.vstack([out['points'],out['points'][0]]).astype('<f4')
    return out,dict(branch='append-first-record-through-common-face',face=common,firstEdge=first,lastEdge=last)
