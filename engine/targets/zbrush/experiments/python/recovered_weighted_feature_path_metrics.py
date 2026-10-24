"""Native25e830 numerical continuity corrections; stateful callers separate.

Literal constants transcribed from original engine instruction/data evidence.
No native files, caches or code are loaded here. Source geometry/angles/masks
are explicit numerical inputs. Per-pair branch labels are model diagnostics.
"""
import math
import numpy as np
from recovered_feature_path_metrics import turn,side_statistics
F=np.float32
TURN_TRIGGER = 0.13962634015954636
JUMP_TRIGGER = 0.08726646259971647
OFF_RATIO_TRIGGER = F(2.5)
RELATIVE_TURN_TRIGGER = 0.7
LOW_TURN_LIMIT = 0.4363323129985824
SECOND_TURN_LIMIT = 0.6283185307179586
SECOND_JUMP_LIMIT = 0.20943951023931956
ROLLING_ANGLE_LIMIT = 1.0471975511965976
OTHER_ANGLE_LIMIT = 0.4188790204786391
FULL_JUMP_LIMIT = 0.3490658503988659
BLEND_LIMIT = 0.17453292519943295
LINEAR_TURN_LIMIT = 0.5585053606381855
LINEAR_TURN_START = F(0.1745329201221466)
LINEAR_SLOPE = F(2.2918310165405273)
ONE_THIRD = F(0.3333333432674408)
TWO_THIRDS = F(0.6666666865348816)

def continuity_quality(bend,jump,ratio,average,rolling_angle,other):
    if not ((float(bend)>=TURN_TRIGGER or float(jump)>=JUMP_TRIGGER) and (ratio>=OFF_RATIO_TRIGGER or float(average)*RELATIVE_TURN_TRIGGER<=float(bend))):return F(1),'unit'
    if float(jump)>=JUMP_TRIGGER:
        if (float(bend)<LOW_TURN_LIMIT and float(jump)<FULL_JUMP_LIMIT) or (float(bend)<SECOND_TURN_LIMIT and float(jump)<SECOND_JUMP_LIMIT and ROLLING_ANGLE_LIMIT<float(rolling_angle) and float(other)<OTHER_ANGLE_LIMIT):
            mixed=F(F(jump*TWO_THIRDS)+F(bend*ONE_THIRD))
            return (F(1),'blended-unit') if float(mixed)<BLEND_LIMIT else (F(.5),'blended-half')
        #Native appends this vertex to a temporary critical-node vector. Its
        #open/junction caller state is outside this numerical metric operator.
        return F(0),'critical-zero'
    if float(bend)<LINEAR_TURN_LIMIT:
        if LINEAR_TURN_START<=bend:return F(F(1)-F(F(bend-LINEAR_TURN_START)*LINEAR_SLOPE)),'linear'
        return F(1),'small-turn-unit'
    return F(0),'turn-zero'

def measure(positions,topology,edge_lengths,edge_angles,path,candidate,excluded=None):
    path=list(map(int,path));edges=topology['edges'];excluded=np.zeros(len(edges),bool) if excluded is None else np.asarray(excluded,dtype=bool)
    if not path or excluded.shape!=(len(edges),) or np.asarray(candidate).shape!=(len(edges),):raise ValueError('Nonempty source edge path and full candidate/excluded masks required')
    metrics=np.zeros(16,dtype='<f4');metrics[[1,3,9]]=np.finfo(F).max;first=path[0];metrics[0]=edge_lengths[first];metrics[12:15]=edge_angles[first];metrics[15]=F(edge_angles[first]*edge_lengths[first]);denominator=F(0);pairs=[]
    for previous,current in zip(path[:-1],path[1:]):
        shared=set(map(int,edges[previous]))&set(map(int,edges[current]))
        if len(shared)!=1:raise ValueError('Unambiguous consecutive edge path required')
        vertex=next(iter(shared));bend=turn(positions,edges,previous,current,vertex);a=edge_angles[previous];b=edge_angles[current];difference=abs(F(a-b));metrics[12]=max(metrics[12],b);metrics[13]=min(metrics[13],b);metrics[14]=F(b+metrics[14]);metrics[15]=F(F(b*edge_lengths[current])+metrics[15]);metrics[0]=F(metrics[0]+edge_lengths[current]);metrics[1]=min(metrics[1],bend);metrics[2]=max(metrics[2],bend);metrics[3]=min(metrics[3],difference);metrics[4]=max(metrics[4],difference);other,total=side_statistics(vertex,topology,edge_angles,candidate,excluded);average=F(F(a+b)*F(.5))
        if average==0:raise NotImplementedError('Zero mean feature angle continuity ratio')
        ratio=F(other/average);metrics[5]=max(metrics[5],other);metrics[6]=max(metrics[6],ratio);metrics[7]=F(ratio+metrics[7]);quality,quality_branch=continuity_quality(bend,difference,ratio,average,metrics[14],other);pair_length=F(edge_lengths[previous]+edge_lengths[current]);metrics[8]=F(F(pair_length*quality)+metrics[8]);denominator=F(denominator+pair_length);metrics[9]=min(metrics[9],quality);metrics[10]=max(metrics[10],quality);pairs.append(dict(edgeA=previous,edgeB=current,vertex=vertex,turn=bend,otherMaximum=other,otherSum=total,ratio=ratio,quality=quality,qualityBranch=quality_branch))
    if denominator!=0:metrics[8]=F(metrics[8]/denominator)
    reciprocal=F(F(1)/F(len(path)));metrics[14]=F(reciprocal*metrics[14]);metrics[15]=F(metrics[15]/metrics[0]);metrics[7]=F(reciprocal*metrics[7])
    if len(path)==1:metrics[[1,3,9]]=0
    return dict(metrics=metrics,pairs=pairs,activeMetricIndices=list(range(11))+[12,13,14,15],unitContinuityDomain=all(p['quality']==F(1) for p in pairs),nonUnitContinuityImplemented=True)
