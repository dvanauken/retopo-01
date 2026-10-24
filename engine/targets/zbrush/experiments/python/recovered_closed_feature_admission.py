"""260290 closed degree-two feature cycles in the unit-continuity domain.

Implements closed-loop length/angle admission and repeated deletion. Open paths,
junctions, external exclusions and non-unit continuity corrections reject.
No native paths, mask, metrics, threshold files or solutions are read here.
"""
import math
import numpy as np
from recovered_conditioning_measures import produce
from recovered_feature_cycle_candidates import prepare as candidates
from recovered_feature_path_metrics import measure
from recovered_alternate_vertex_path import lengths
from recovered_original_densification import threshold_from_geometry
F=np.float32
def minimum_length_from_original(source,faces,target):
    if not 1<=int(target)<=2147483647:raise ValueError('Positive int32 ordinary target required')
    area,_,_=threshold_from_geometry(source,faces,int(target));budget=max(1000,min(10000,int(target)));return F(np.sqrt(F(area/F(budget))))
def keep_closed(metrics,minimum_length):
    m=np.asarray(metrics,dtype='<f4');s=F(minimum_length)
    if m.shape!=(16,) or not np.isfinite(m).all() or not np.isfinite(s) or s<=0:raise ValueError('Finite active metric storage and positive ordinary length control required')
    if m[8]<=F(.8):raise NotImplementedError('Low weighted continuity common deletion/preservation branch')
    length=m[0];maximum_turn=m[2];maximum_jump=m[4];maximum_angle=m[12];minimum_angle=m[13]
    if s<=length:
        return bool((float(minimum_angle)<=math.radians(120) or F(s+s)<=length) and (math.radians(44.5)<=float(maximum_angle) or F(s*F(5))<=length or float(maximum_jump)<math.radians(2) or float(maximum_turn)<math.radians(2)))
    return bool(math.radians(50)<float(minimum_angle) and float(F(maximum_angle-minimum_angle))<math.radians(10) and float(maximum_jump)<math.radians(5) and float(maximum_turn)<math.radians(30))
def prepare(positions,faces,minimum_length):
    source=np.asarray(positions,dtype='<f4');tri=np.asarray(faces,dtype='<i4');g=produce(source,tri);top=g['topology'];edge_lengths=lengths(source,top['edges']);candidate=candidates(source,tri);selected=candidate['candidateEdges'].copy();history=[]
    for iteration in range(11):
        # Removing whole disjoint cycles preserves their incidence order. The
        # original angular candidate threshold remains fixed, so exclusions
        # express cycles removed by earlier admission rounds.
        paths=candidates(source,tri,excluded_edges=candidate['candidateEdges']&~selected);remove=[];records=[]
        for i,(start,end) in enumerate(zip(paths['edgeOffsets'][:-1],paths['edgeOffsets'][1:])):
            ids=paths['edgeIds'][start:end];m=measure(source,top,edge_lengths,g['edgeAngles'],ids,selected);keep=keep_closed(m['metrics'],minimum_length);records.append(dict(edges=ids.copy(),metrics=m['metrics'],accepted=keep))
            if not keep:remove.extend(ids.tolist())
        history.append(records)
        if not remove:break
        selected[np.asarray(remove,dtype='<i4')]=False
    else:raise NotImplementedError('Feature admission change beyond reviewed eleven-round limit')
    accepted=candidates(source,tri,excluded_edges=candidate['candidateEdges']&~selected);accepted.update(initialCandidateEdges=candidate['candidateEdges'],acceptedEdges=selected,lockedVertices=accepted['candidateVertices'],modes=np.full(len(accepted['edgeOffsets'])-1,2,dtype='<i4'),history=history,minimumLength=F(minimum_length),admissionPolicyImplemented=True,scope='Ordinary closed disconnected degree-two cycles, unit continuity, no initial exclusions/junctions/open paths. Closed-loop length/angle deletion and default accepted-mode2 only, not complete260290.')
    return accepted
