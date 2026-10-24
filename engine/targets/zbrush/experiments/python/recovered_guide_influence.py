"""Ordinary single active mode2 curve influence sizing and2fc8e0 propagation."""
from collections import deque
import numpy as np
F=np.float32


def distance(a,b):
    d=F(a-b);return F(np.sqrt(F(F(d[0]*d[0]+d[1]*d[1])+d[2]*d[2])))


def prepare(geometry,topology,maximum_radius):
    points=geometry['embeddedPoints'];pairs=geometry['embeddedPairs'];positions=geometry['positions'];triangles=geometry['faces']
    if np.any(pairs[:,0]!=1):raise NotImplementedError('Nonvertex or non-mode2 guide propagation')
    length=F(0)
    for a,b in zip(points,points[1:]):length=F(distance(a,b)+length)
    scale=F(min(F(length*F(.25)),F(maximum_radius))*F(.75))
    if not scale>0:raise NotImplementedError('Zero guide influence scale')
    values=np.full(len(positions),np.finfo('f4').max,dtype='<f4');association=np.full(len(positions),-1,dtype='<i4');seeds=[];queue=deque();queued=np.zeros(len(positions),dtype=bool)
    for sample,(_,vertex) in enumerate(pairs):
        if values[vertex]==0:continue
        values[vertex]=0;association[vertex]=len(seeds);seeds.append(sample);queue.append(int(vertex));queued[vertex]=True
    edges=topology['edges'];offset=topology['vertexEdgeOffsets'];incident=topology['vertexEdges'];updates=0;pops=0
    while queue:
        current=queue.popleft();queued[current]=False;pops+=1
        for edge in incident[offset[current]:offset[current+1]]:
            a,b=edges[edge];neighbor=int(b if a==current else a);sample=seeds[association[current]];candidate=distance(positions[neighbor],points[sample]);floor=F(values[current]*F(1.005))
            if candidate<=floor:candidate=floor
            if candidate<values[neighbor] and candidate<F(scale+scale):
                values[neighbor]=candidate;association[neighbor]=association[current];updates+=1
                if not queued[neighbor]:queue.append(neighbor);queued[neighbor]=True
    normalized=np.full(len(triangles),np.finfo('f4').max,dtype='<f4')
    for face,(a,b,c) in enumerate(triangles):
        if association[a]>=0 and association[b]>=0 and association[c]>=0:
            normalized[face]=F(F(F(F(values[b]/scale)+F(values[a]/scale))+F(values[c]/scale))*F(1/3))
    return dict(scale=scale,length=length,vertexDistance=values,association=association,seeds=np.asarray(seeds,dtype='<i4'),normalized=normalized,updates=updates,pops=pops)
