"""Ordinary disconnected degree-two closed features with weighted continuity.

Reviewed 260290 closed retention and common low-continuity deletion only.
Open/junction/external preservation and critical-node consumers are separate.
An optional angle provider declares controlled numerical experiments; default
construction obtains every cache angle from the supplied source geometry.
"""
import math
import numpy as np
from recovered_conditioning_measures import produce
from recovered_feature_cycle_candidates import prepare as candidates
from recovered_weighted_feature_path_metrics import measure
from recovered_closed_feature_admission import minimum_length_from_original
from recovered_alternate_vertex_path import lengths
F=np.float32
CONTINUITY_LIMIT=F(0.800000011920929)
SMOOTH_JUMP_LIMIT=F(0.01745329238474369)
TURN_LIMIT=F(0.5235987901687622)
QUALITY_RANGE_LIMIT=F(0.15000000596046448)
MINIMUM_QUALITY_LIMIT=F(0.4000000059604645)
JUMP_LIMIT=F(0.06981316953897476)

def common_delete(metrics,iteration):
    m=np.asarray(metrics,dtype='<f4')
    if m.shape!=(16,) or not np.isfinite(m[list(range(11))+[12,13,14,15]]).all():raise ValueError('Finite active path metrics required')
    if not isinstance(iteration,int) or iteration<0:raise ValueError('Nonnegative integer iteration required')
    # COMISS threshold,mean followed by JBE skips equality as well as greater.
    if iteration>=3 or not m[8]<CONTINUITY_LIMIT:return False
    if m[4]<SMOOTH_JUMP_LIMIT and m[2]<TURN_LIMIT:return False
    return bool(QUALITY_RANGE_LIMIT<=F(m[10]-m[9]) or m[9]<=MINIMUM_QUALITY_LIMIT or JUMP_LIMIT<=m[4] or TURN_LIMIT<=m[2])

def keep_closed(metrics,minimum_length):
    m=np.asarray(metrics,dtype='<f4');s=F(minimum_length)
    if m.shape!=(16,) or not np.isfinite(m[list(range(11))+[12,13,14,15]]).all() or not np.isfinite(s) or s<=0:raise ValueError('Finite active metrics and positive ordinary length required')
    length=m[0];maximum_turn=m[2];maximum_jump=m[4];maximum_angle=m[12];minimum_angle=m[13]
    if s<=length:
        return bool((float(minimum_angle)<=math.radians(120) or F(s+s)<=length) and (math.radians(44.5)<=float(maximum_angle) or F(s*F(5))<=length or float(maximum_jump)<math.radians(2) or float(maximum_turn)<math.radians(2)))
    return bool(math.radians(50)<float(minimum_angle) and float(F(maximum_angle-minimum_angle))<math.radians(10) and float(maximum_jump)<math.radians(5) and float(maximum_turn)<math.radians(30))

def prepare(positions,faces,minimum_length,angle_provider=None):
    source=np.asarray(positions,dtype='<f4');tri=np.asarray(faces,dtype='<i4');g=produce(source,tri);top=g['topology'];edge_lengths=lengths(source,top['edges']);candidate=candidates(source,tri);selected=candidate['candidateEdges'].copy();history=[];excluded=np.zeros(len(selected),bool)
    for iteration in range(11):
        paths=candidates(source,tri,excluded_edges=candidate['candidateEdges']&~selected);remove=[];records=[]
        for start,end in zip(paths['edgeOffsets'][:-1],paths['edgeOffsets'][1:]):
            ids=paths['edgeIds'][start:end];angles=g['edgeAngles'] if angle_provider is None else np.asarray(angle_provider(ids,selected,excluded,top,g['edgeAngles']),dtype='<f4')
            if angles.shape!=g['edgeAngles'].shape or not np.isfinite(angles).all():raise ValueError('Complete finite controlled angle array required')
            result=measure(source,top,edge_lengths,angles,ids,selected,excluded);m=result['metrics'];closed=keep_closed(m,minimum_length);common=common_delete(m,iteration) if closed else False;keep=closed and not common
            records.append(dict(edges=ids.copy(),metrics=m,pairs=result['pairs'],closedRetention=closed,commonDeletion=common,accepted=keep,angles=angles.copy(),candidate=selected.copy(),excluded=excluded.copy()))
            if not keep:remove.extend(ids.tolist())
        history.append(records)
        if not remove:break
        selected[np.asarray(remove,dtype='<i4')]=False
    else:raise NotImplementedError('Feature change beyond reviewed eleven-round limit')
    accepted=candidates(source,tri,excluded_edges=candidate['candidateEdges']&~selected)
    accepted.update(initialCandidateEdges=candidate['candidateEdges'],acceptedEdges=selected,lockedVertices=accepted['candidateVertices'],modes=np.full(len(accepted['edgeOffsets'])-1,2,dtype='<i4'),history=history,minimumLength=F(minimum_length),controlledAngles=angle_provider is not None,admissionPolicyImplemented=True,scope='Ordinary closed disconnected degree-two cycles, no external exclusions/preservation. Weighted metrics, closed retention and common deletion; open/junction/critical-node state and general260290 remain separate.')
    return accepted
