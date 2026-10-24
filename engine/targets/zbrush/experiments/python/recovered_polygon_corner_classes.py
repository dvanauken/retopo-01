"""30fe20 corner classes, optional edge directions and derived thresholds.

Native367/368 qualify derived range/record flags under the declared profile;
source metadata production and full mesh commit remain separate.
"""
import struct
import numpy as np
from recovered_reflex_hexagon import angles,constant
F=np.float32


def classify(points,edge_directions=None,derived_thresholds=None):
    a=angles(points,edge_directions);classes=np.full(len(a),3,dtype='<i4');ambiguous=0;score=0;wide=0;reflex=0;pi=constant(0x40490fdb);tau=constant(0x40c90fdb);lo=constant(0x3ef1463b);preferred=constant(0x3f71463b);high=constant(0x400cbe4c);wide_bound=constant(0x402ae714)
    for i,value in enumerate(a):
        corner_lo,corner_preferred,corner_high=(constant(0x3fb2b8c2),constant(0x3fbde44e),constant(0x3fd43b67)) if derived_thresholds is not None and derived_thresholds[i] else (lo,preferred,high)
        folded=F(tau-value) if value>pi else value
        if folded<corner_preferred or corner_high<folded:
            if folded<=corner_lo:classes[i]=0
            elif folded<wide_bound:ambiguous+=1
            else:classes[i]=2;wide+=1;score+=2
        else:
            classes[i]=1 if value<=pi else -1;score+=int(classes[i]);reflex+=int(classes[i]==-1)
    branches=[]
    if len(a)==6 and ambiguous:
        largest=int(np.argmax(a));nonreflex=a[a<pi]
        if a[largest]>constant(0x4071463b) and max(nonreflex,default=F(0))<constant(0x4024deec) and min(a)>constant(0x3f10c3bd):classes[:]=1;classes[largest]=-1;branches.append('six-gon-reflex-reclassification')
    if score==5:
        for i,value in enumerate(a):
            folded=F(tau-value) if value>pi else value
            if classes[i]==3 and lo<=folded<=wide_bound and value<0:classes[i]=-1;ambiguous-=1;score=4;branches.append('score-five-reflex');break
    elif score==3:
        best=np.finfo(F).max;chosen=-1
        for i,value in enumerate(a):
            folded=F(tau-value) if value>pi else value;distance=F(abs(F(folded-constant(0x3fc90fdb))))
            if classes[i]==3 and lo<=folded<=wide_bound and value>=0 and distance<best:best=distance;chosen=i
        if chosen>=0:classes[chosen]=1;ambiguous-=1;score=4;branches.append('score-three-nearest-right-angle')
    if wide==0 and reflex==0 and ambiguous<5:
        total=F(0);count=0
        for value,kind in zip(a,classes):
            if kind==3 and constant(0x3f490fdb)<=value<=constant(0x4016cbe4):total=F(total+value);count+=1
        tolerance=struct.unpack('<d',bytes.fromhex('8744e74a1857d63f'))[0]
        if count==ambiguous and float(abs(F(total-tau)))<tolerance:
            classes[classes==3]=1;score+=count;ambiguous-=count;branches.append('ambiguous-turn-sum-near-two-pi')
    if score%4==0 and ambiguous>0:
        for i,value in enumerate(a):
            folded=F(tau-value) if value>pi else value
            if classes[i]==3 and folded<=preferred:classes[i]=0;branches.append('small-ambiguous-to-flat')
    return a,classes,branches


def derived_threshold_mask(vertex_ids,original_count,derived_range,mapping,record_types,polygon_count):
    start,stop=map(int,derived_range);result=[]
    for vertex in vertex_ids:
        index=int(vertex)-int(original_count);eligible=start<=index<stop
        record=int(mapping[index-start]) if eligible else -1
        result.append(polygon_count==1 and eligible and (record<0 or int(record_types[record])!=1))
    return np.asarray(result,dtype=bool)
