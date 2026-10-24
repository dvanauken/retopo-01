"""Reviewed ordinary smooth closed mode3 subset of2ec0d0 weight production."""
import struct
import numpy as np
from recovered_conditioning_measures import produce
F=np.float32
TWO_DEGREES=struct.unpack('<d',bytes.fromhex('399d52a246dfa13f'))[0]
FIVE_DEGREES=struct.unpack('<d',bytes.fromhex('8744e74a1857b63f'))[0]
TWENTY_DEGREES=struct.unpack('<d',bytes.fromhex('8744e74a1857d63f'))[0]


def neighbors(topology,vertex):
    for edge in topology['vertexEdges'][topology['vertexEdgeOffsets'][vertex]:topology['vertexEdgeOffsets'][vertex+1]]:
        a,b=map(int,topology['edges'][edge]);yield int(edge),b if a==vertex else a


def diffuse(values,topology,average_weight,max_weight=None):
    out=values.copy();one=F(1);average_weight=F(average_weight)
    for vertex,value in enumerate(values):
        total=F(0);maximum=value;count=0
        for _,neighbor in neighbors(topology,vertex):total=F(total+values[neighbor]);maximum=max(maximum,values[neighbor]);count+=1
        if count==0:raise NotImplementedError('Unused source vertex')
        mean=F(total/F(count))
        if max_weight is None:out[vertex]=F(F(mean*average_weight)+F(value*F(one-average_weight)))
        else:
            maximum_weight=F(max_weight);center=F(F(one-average_weight)-maximum_weight);out[vertex]=F(F(F(mean*average_weight)+F(value*center))+F(maximum*maximum_weight))
    return out


def weights(positions,faces):
    geometry=produce(positions,faces);topology=geometry['topology'];deficit=geometry['deficit'];edge_angles=geometry['edgeAngles'];minimum=deficit.copy()
    if float(np.max(edge_angles))>TWENTY_DEGREES:raise NotImplementedError('Sharp-edge mode3 weight branches')
    for vertex in range(len(positions)):
        for _,neighbor in neighbors(topology,vertex):minimum[vertex]=min(minimum[vertex],deficit[neighbor])
    initial=np.zeros(len(positions),dtype='<f4');negative=[];positive=[];incidentAngles=[]
    for vertex in range(len(positions)):
        neg=F(0);pos=F(0);angleSum=F(0)
        for edge,neighbor in neighbors(topology,vertex):
            if deficit[neighbor]<=0:neg=F(neg-minimum[neighbor])
            else:pos=F(pos+deficit[neighbor])
            angleSum=F(angleSum+edge_angles[edge])
        if float(neg)>=FIVE_DEGREES:raise NotImplementedError('Large negative neighborhood deficit branch')
        initial[vertex]=F(.5) if float(angleSum)<TWO_DEGREES else F(0);negative.append(neg);positive.append(pos);incidentAngles.append(angleSum)
    mixed=diffuse(initial,topology,F(.4),F(.35));final=diffuse(mixed,topology,F(.6));diagnostic=dict(maxEdgeAngle=float(edge_angles.max()),maxNegativeNeighborhoodSum=float(max(negative)),maxPositiveNeighborhoodSum=float(max(positive)),twoDegreeThreshold=TWO_DEGREES,fiveDegreeThreshold=FIVE_DEGREES,initialZero=int(np.count_nonzero(initial==0)),initialHalf=int(np.count_nonzero(initial==F(.5))))
    return final,dict(initial=initial,maxMean=mixed,minimumDeficit=minimum,incidentAngleSum=np.asarray(incidentAngles,dtype='<f4'),geometry=geometry,diagnostic=diagnostic)
