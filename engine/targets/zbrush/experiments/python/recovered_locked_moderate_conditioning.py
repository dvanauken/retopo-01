"""Closed mode3 conditioning with an EXPLICIT precomputed feature-lock mask.

This does not produce the260290 paths/locks from source. It preserves locked
mobility through both diffusion stages and the four-iteration native budget.
"""
import math
import numpy as np
from recovered_original_densification import densify
from recovered_conditioning_measures import produce
from recovered_conditioning_weights import neighbors,TWO_DEGREES,FIVE_DEGREES,TWENTY_DEGREES
from recovered_ordered_conditioning_diffusion import diffuse
from recovered_weighted_fairing import step
F=np.float32
FORTY_DEGREES=float.fromhex('0x1.657184ae74487p-1');ONE_DEGREE=float.fromhex('0x1.1df46a2529d39p-6')
def weights(positions,faces,locked):
    g=produce(positions,faces);top=g['topology'];deficit=g['deficit'];angles=g['edgeAngles'];minimum=deficit.copy();locked=np.asarray(locked,dtype=bool)
    if locked.shape!=(len(positions),):raise ValueError('Explicit densified-vertex lock mask required')
    sharp=angles.astype(float)>FORTY_DEGREES;ends=top['edges']
    if np.any(sharp&~(locked[ends[:,0]]&locked[ends[:,1]])):raise NotImplementedError('Above40-degree edge incident to an unlocked conditioning vertex')
    for vertex in range(len(positions)):
        for _,neighbor in neighbors(top,vertex):minimum[vertex]=min(minimum[vertex],deficit[neighbor])
    initial=np.zeros(len(positions),dtype='<f4')
    for vertex in range(len(positions)):
        if locked[vertex]:continue
        neg=F(0);pos=F(0);total=F(0);count=0
        for edge,neighbor in neighbors(top,vertex):
            if deficit[neighbor]<=0:neg=F(neg-minimum[neighbor])
            else:pos=F(pos+deficit[neighbor])
            total=F(total+angles[edge]);count+=int(float(angles[edge])>TWENTY_DEGREES)
        if float(abs(deficit[vertex]))>=TWO_DEGREES and float(neg)>=FIVE_DEGREES and float(pos)>=FIVE_DEGREES:raise NotImplementedError('Large mixed-sign conditioning neighborhood')
        if float(total)<TWO_DEGREES:initial[vertex]=F(.5)
        elif count>1 or (deficit[vertex]>0 and float(pos)<ONE_DEGREE and FIVE_DEGREES<float(neg)) or (deficit[vertex]<0 and FIVE_DEGREES<float(pos) and float(neg)<ONE_DEGREE):initial[vertex]=F(.3)
    mixed=diffuse(initial,top,F(.4),F(.35));mixed[locked]=initial[locked];final=diffuse(mixed,top,F(.6));final[locked]=mixed[locked]
    return final,dict(initial=initial,maxMean=mixed,locked=locked.copy())
def smooth_prepared(positions,faces,locked):
    locked=np.asarray(locked,dtype=bool);history=[];termination='iteration-budget'
    if locked.shape!=(len(positions),):raise ValueError('Explicit lock mask must match independently densified vertices')
    for i in range(4):
        mobility,detail=weights(positions,faces,locked)
        if not np.any(detail['initial']):history.append(dict(applied=False,**detail));termination='no-active-seed';break
        passes=[]
        for _ in range(3):positions=step(positions,faces,mobility);passes.append(positions.copy())
        history.append(dict(applied=True,**detail,weights=mobility,passes=passes))
    return positions,faces,dict(smoothing=history,termination=termination,outerBudget=4,featureLockMaskIsExplicitInput=True)

def prepare(positions,faces,target,locked):
    positions,faces,dense=densify(positions,faces,target);positions,faces,result=smooth_prepared(positions,faces,locked);result['densification']=dense;return positions,faces,result
