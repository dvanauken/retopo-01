"""255b10 independent per-path preparation before pooled relocation assignment.

Physical stroke closure does not override the stored25a7e0 descriptor test.
Only ordinary free endpoints and previously qualified open/closed leaves apply.
"""
import numpy as np
from recovered_open_cut_preparation import prepare as open_prepare
from recovered_cyclic_fractional_cut_preparation import prepare as closed_prepare
F=np.float32

def prepare(vertices,edges,paths,fraction=F(.05),reset_positions=True):
    original=np.asarray(vertices,dtype='<f4');records=[];requests=[];details=[]
    for source in paths:
        ids=source['edges'];t=source['parameters'].copy();count=len(ids)
        if count<4 or len(t)!=count or len(source['points'])!=count or len(source['faces'])!=count-1:raise NotImplementedError('Ordinary nonempty descriptor layout required')
        if len(source['attributes']) or np.any(ids>=len(edges)) or np.any(ids < -1) or np.any(~np.isfinite(t)) or np.any(t<0) or np.any(t>1):raise NotImplementedError('Mixed descriptor attributes/range unsupported')
        if np.any(ids[1:-1]<0):raise NotImplementedError('Free interior path record remains unqualified')
        # Closure is tested after endpoint snapping but before collapse/propagation.
        upper=F(F(1)-fraction)
        t[(ids>=0)&(t>0)&(t<fraction)]=0
        t[(ids>=0)&(t>upper)&(t<1)]=1
        def endpoint(i):return int(edges[int(ids[i]),int(t[i])]) if ids[i]>=0 and t[i] in (0,1) else -1
        closed=(endpoint(0)>=0 and endpoint(0)==endpoint(-1)) or (ids[0]>=0 and ids[0]==ids[-1] and t[0] not in (0,1) and t[0]==t[-1])
        _,local,ordered,diagnostic=(closed_prepare if closed else open_prepare)(original,edges,[source],fraction,reset_positions)
        records.extend(local);requests.extend(ordered)
        details.extend(dict(d,descriptorClosed=bool(closed),pooledOriginalSource=True) for d in diagnostic)
    # Every request/reset was computed from the same original source, not the
    # previously relocated result. Last stored request wins, matching1703f0.
    updated=original.copy()
    for vertex,point in requests:updated[vertex]=point
    return updated,records,requests,details
