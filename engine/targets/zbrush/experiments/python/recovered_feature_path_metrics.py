"""268430/25ee30 and15 active25e830 metrics for unit-continuity paths.

The native weighted continuity-score correction branches deliberately reject.
Reserved metric slot11 and subsequent caller classification flags are not
claimed as outputs of the metric helper. No native evidence is read here.
"""
import math
import numpy as np
F=np.float32
def turn(positions,edges,edge_a,edge_b,vertex):
    a,b=map(int,edges[edge_a]);c,d=map(int,edges[edge_b])
    if vertex not in [a,b] or vertex not in [c,d]:raise ValueError('Shared source vertex required')
    x=F(positions[b]-positions[a]) if a==vertex else F(positions[a]-positions[b]);y=F(positions[c]-positions[d]) if c==vertex else F(positions[d]-positions[c])
    def dot(u,v):return F(F(F(u[1]*v[1])+F(u[0]*v[0]))+F(u[2]*v[2]))
    denominator=math.sqrt(float(dot(x,x))*float(dot(y,y)))
    if denominator==0:return F(0)
    cosine=float(dot(x,y))/denominator
    return F(math.pi) if cosine<=-1 else F(math.acos(cosine)) if cosine<1 else F(0)
def side_statistics(vertex,topology,angles,candidate,excluded):
    maximum=F(0);total=F(0);vo=topology['vertexEdgeOffsets'];ve=topology['vertexEdges']
    for edge in ve[vo[vertex]:vo[vertex+1]]:
        if candidate[edge] or excluded[edge]:continue
        value=angles[edge];total=F(total+value)
        if value>maximum:maximum=value
    return maximum,total
def measure(positions,topology,edge_lengths,edge_angles,path,candidate,excluded=None):
    path=list(map(int,path));edges=topology['edges'];excluded=np.zeros(len(edges),bool) if excluded is None else np.asarray(excluded,dtype=bool)
    if not path or excluded.shape!=(len(edges),) or np.asarray(candidate).shape!=(len(edges),):raise ValueError('Nonempty source edge path and full candidate/excluded masks required')
    metrics=np.zeros(16,dtype='<f4');metrics[[1,3,9]]=np.finfo(F).max;first=path[0];metrics[0]=edge_lengths[first];metrics[12:15]=edge_angles[first];metrics[15]=F(edge_angles[first]*edge_lengths[first]);denominator=F(0);pairs=[]
    for previous,current in zip(path[:-1],path[1:]):
        shared=set(map(int,edges[previous]))&set(map(int,edges[current]))
        if len(shared)!=1:raise ValueError('Unambiguous consecutive edge path required')
        vertex=next(iter(shared));bend=turn(positions,edges,previous,current,vertex);a=edge_angles[previous];b=edge_angles[current];difference=abs(F(a-b));metrics[12]=max(metrics[12],b);metrics[13]=min(metrics[13],b);metrics[14]=F(b+metrics[14]);metrics[15]=F(F(b*edge_lengths[current])+metrics[15]);metrics[0]=F(metrics[0]+edge_lengths[current]);metrics[1]=min(metrics[1],bend);metrics[2]=max(metrics[2],bend);metrics[3]=min(metrics[3],difference);metrics[4]=max(metrics[4],difference);other,total=side_statistics(vertex,topology,edge_angles,candidate,excluded);average=F(F(a+b)*F(.5))
        if average==0:raise NotImplementedError('Zero mean feature angle continuity ratio')
        ratio=F(other/average);metrics[5]=max(metrics[5],other);metrics[6]=max(metrics[6],ratio);metrics[7]=F(ratio+metrics[7]);correction=(float(bend)>=math.radians(8) or float(difference)>=math.radians(5)) and (ratio>=F(2.5) or float(average)*.7<=float(bend))
        if correction:raise NotImplementedError('Native non-unit feature continuity score branches unqualified')
        quality=F(1);pair_length=F(edge_lengths[previous]+edge_lengths[current]);metrics[8]=F(F(pair_length*quality)+metrics[8]);denominator=F(denominator+pair_length);metrics[9]=min(metrics[9],quality);metrics[10]=max(metrics[10],quality);pairs.append(dict(edgeA=previous,edgeB=current,vertex=vertex,turn=bend,otherMaximum=other,otherSum=total,ratio=ratio,quality=quality))
    if denominator!=0:metrics[8]=F(metrics[8]/denominator)
    reciprocal=F(F(1)/F(len(path)));metrics[14]=F(reciprocal*metrics[14]);metrics[15]=F(metrics[15]/metrics[0]);metrics[7]=F(reciprocal*metrics[7])
    if len(path)==1:metrics[[1,3,9]]=0
    return dict(metrics=metrics,pairs=pairs,activeMetricIndices=list(range(11))+[12,13,14,15],unitContinuityDomain=True)
