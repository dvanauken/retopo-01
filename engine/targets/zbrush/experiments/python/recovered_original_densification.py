"""Ordinary1c2630 original triangle geometry to pre-smoothing dense source."""
import math,struct
import numpy as np
from recovered_triangle_subdivision import split
F=np.float32


def threshold_from_geometry(positions,faces,target):
    if target<1:raise NotImplementedError('Nonpositive target allocation')
    budget=3000
    if target>=3000:
        if target<=7999:budget=int(target)
        elif target<15000:budget=int(F(F(F(target)-F(8000))*np.frombuffer(bytes.fromhex('2549123f'),'<f4')[0])+F(8000))
        else:budget=12000
    total=F(0)
    for row in faces:
        a,b,c=positions[row].astype(float);u=b-a;v=c-a;n=[u[1]*v[2]-v[1]*u[2],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];length=math.sqrt((n[0]*n[0]+n[1]*n[1])+n[2]*n[2]);total=F(total+F(length))
    area=F(total*F(.5));scale=F(np.sqrt(F(area/F(budget))));return area,budget,scale


def densify(positions,faces,target,max_rounds=4):
    area,budget,scale=threshold_from_geometry(positions,faces,target);history=[];positions=positions.copy();faces=[list(map(int,row)) for row in faces]
    for index in range(max_rounds):
        threshold=F(scale*F(2)) if index==0 else scale;before=len(positions);positions,faces,diagnostic=split(positions,faces,threshold);added=len(positions)-before;diagnostic['selectedEdges']=len(diagnostic.pop('selected'));history.append(dict(threshold=threshold,positions=positions.copy(),faces=[row.copy() for row in faces],addedVertices=added,diagnostic=diagnostic))
        if not added:break
    return positions,faces,dict(area=area,auxiliaryBudget=budget,baseScale=scale,history=history)
